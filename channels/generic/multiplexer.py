import asyncio
import logging
from functools import partial
from typing import Any, Callable, Dict, List, NamedTuple, Tuple

from channels.consumer import get_handler_name
from channels.exceptions import StopConsumer

logger = logging.getLogger(__name__)

ApplicationWrapper = NamedTuple(
    "ApplicationWrapper",
    [
        ("name", str),
        ("send_upstream", Callable),
        ("task", asyncio.Task),
    ]
)


class ApplicationWithChildren:
    """
    Base classes for an ASGI application to manage multiple children and close
     its observed tasks (when it is watching queues) correctly.
    """

    def __init__(self):
        # the asyncio.Task for each child application.
        # mapping based on a key.
        self._child_application_tasks = {}  # type: Dict[str, asyncio.Task]

    async def _observe_child_applications(self):
        """
        This runs its own little run-loop to detect if a child application
        closes / raises an exception.

        self._child_application_tasks should not be modified outside of this
         method while this run-loop is running.

        This run-loop will run until all tasks have stopped or one of them has
         raised an exception.

         :raises any exception raised within any of the children.
        """

        try:
            # loop until there are no more child applciations
            while len(self._child_application_tasks) > 0:
                # what for one of the to finish
                await asyncio.wait(
                    self._child_application_tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED
                )

                # find that finished task
                for key, task in list(self._child_application_tasks.items()):
                    if task.done():
                        try:
                            # raise any exceptions that might be there.
                            task.result()
                        except asyncio.CancelledError:
                            # TODO we should warn here these should not be
                            #  Cancelled
                            pass

                        # we need to be sure `_child_application_tasks` is not
                        # modifed outside of this loop
                        del self._child_application_tasks[key]

                        # call the delegate function
                        await self._child_application_closed(key)
            # call delegate function
            await self._last_child_application_closed()
        finally:
            # make sure we clean up all child applciations.
            await self._ensure_children_are_closed()

    async def _last_child_application_closed(self):
        """
        Called if all child applciations are closed
         (or there were non to start with)
        """
        pass

    async def _child_application_closed(self, application_key: str):
        """
        Called when a child application closes normally, without raising an
         exception.

         This is run as part of the the `_observe_child_applications` loop.
        """
        pass

    async def _start_observation(self, *args: Tuple[Callable, Callable]):
        """
        Start observing both the child applciations and the dispatch tasks.

        this creates the main loop.
        """

        # set up the tasks
        _observed_tasks = []
        for observed_callable, dispatch_callable in args:
            _observed_tasks.append(
                asyncio.ensure_future(observed_callable())
            )

        # start up
        observed_applications_run_loop = asyncio.ensure_future(
            self._observe_child_applications()
        )

        observe_dispatch_run_loop = asyncio.ensure_future(
            self._observe_dispatch(*args, tasks=_observed_tasks)
        )

        try:

            # as soon as either loop finishes we should exit.
            await asyncio.wait(
                [
                    observed_applications_run_loop,
                    observe_dispatch_run_loop
                ],
                return_when=asyncio.FIRST_COMPLETED
            )

            # raise any exception that might have been there.
            if observed_applications_run_loop.done():
                try:
                    observed_applications_run_loop.result()
                except asyncio.CancelledError:
                    # if it was cancelled then we dont need to raise this.
                    pass

            # raise any exception that might have been there.
            if observe_dispatch_run_loop.done():
                try:
                    observe_dispatch_run_loop.result()
                except asyncio.CancelledError:
                    pass

        finally:
            # lets just make sure that both loops are closed.
            observe_dispatch_run_loop.cancel()

            observed_applications_run_loop.cancel()

            # also ensure that we close all the child applciations
            await self._ensure_children_are_closed()

            # clean up all those tasks we are observing.
            for task in _observed_tasks:
                task.cancel()

    async def _ensure_children_are_closed(self):
        """
        Loop over all child applications tasks and cancel them.
        """
        for child_task in self._child_application_tasks.values():
            if not child_task.done():
                # stop it
                child_task.cancel()

    async def _observe_dispatch(self, *args: Tuple[Callable, Callable],
                                tasks: List[asyncio.Task]=[]):
        """
        Observe and dispatch all as part of one big loop.
        This helps maintain ordering.
        """
        while True:
            await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )

            # Find the completed one(s), yield results, and replace them
            for i, task in enumerate(tasks):
                if task.done():
                    observed, dispatch = args[i]
                    result = task.result()
                    await dispatch(result)
                    # replace that task
                    tasks[i] = asyncio.ensure_future(
                        observed()
                    )


class Demultiplexer(ApplicationWithChildren):

    # the mapping of applications by stream_name
    applications = {}  # type: Dict[str, Type[AsyncConsumer]]

    application_wrapper = ApplicationWrapper

    def __init__(self, scope: Dict[str, Any]):
        super().__init__()
        self.scope = scope

    async def __call__(self, receive, send):

        self.base_send = send

        # set up a queue that we read downstream messages from
        self.downstream_queue = asyncio.Queue()

        # create those upstream multiplexers that manage stuff :)
        self.upstream_applications = {
            name: self._init_application(name, cls)
            for name, cls in self.applications.items()
        }  # type: Dict[str, ApplicationWrapper]

        self._child_application_tasks = {
            name: app.task for name, app in
            self.upstream_applications.items()
        }

        try:

            await self._start_observation(
                (receive, self.upstream_dispatch),
                (self.downstream_queue.get, self.downstream_dispatch)
            )

        except StopConsumer:
            # Exit cleanly
            pass

    async def upstream_dispatch(self, message):
        """
        Works out what to do with a message.
        """
        handler = getattr(self, get_handler_name(message), None)
        if handler:
            await handler(message)
        else:
            # default to send to all if its not intercepted
            await self.send_to_all_upstream(message)

    async def downstream_dispatch(self, full_message: Dict[str, Any]):
        """
        Intercept downstream messages, messages captured here are scoped by
        the source stream.

        {
            "stream": <stream_name>,
            "message": <ASGI message>
        }


        """

        message = full_message.get("message", None)
        stream = full_message.get("stream", None)

        if stream is None:
            raise ValueError(
                "De-mulitplexer unable to multiplex downstream message that"
                " does not container a source stream"
            )

        handler = getattr(self, get_handler_name(message), None)

        if handler:
            await handler(message, stream_name=stream)
        else:
            # send further down if we dont have anything
            # configured to intercept.
            await self.base_send(message)

    async def send_upstream(self, stream: str, message: Dict[str, Any]):
        """
        Send a message upstream to a given stream.

        if target stream cant be found this will call the `handle_no_stream`
        method.
        """

        app = self.upstream_applications.get(stream, None)

        if app is not None:
            await app.send_upstream(message)
            return

        await self.handle_no_stream(stream)

    async def send_to_all_upstream(self, message: Dict[str, Any]):
        """
        Send a message to all upstream applciations.
        """
        for app in self.upstream_applications.values():
            await app.send_upstream(message)

    async def handle_no_stream(self, stream: str):
        """

        Optionally raise an exception here or send a message back?.
        """
        pass

    def _init_application(self, stream_name, application_class) -> ApplicationWrapper:
        """
        Start up the child applciations.

        """
        upstream_queue = asyncio.Queue()
        application_instance = application_class(self.scope)

        # Run it, and stash the task for later checking
        task = asyncio.ensure_future(
            application_instance(
                receive=upstream_queue.get,
                send=partial(self.receive_downstream, stream_name=stream_name),
            )
        )

        return self.application_wrapper(
            name=stream_name,
            send_upstream=upstream_queue.put,
            task=task
        )

    async def receive_downstream(self, message, stream_name):
        """
        put it into the queue so that it is all processed in the same Coroutine
         as the other messages.
        """

        await self.downstream_queue.put(
            {
                "stream": stream_name,
                "message": message
            }
        )
