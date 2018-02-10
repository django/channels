import asyncio
import logging
from functools import partial
from typing import Any, Dict

from channels.consumer import get_handler_name
from channels.exceptions import StopConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class AsyncJsonWebsocketDemultiplexer(AsyncJsonWebsocketConsumer):

    """
    JSON-understanding WebSocket consumer subclass that handles demultiplexing
    streams using a "stream" key in a top-level dict and the actual payload
    in a sub-dict called "payload". This lets you run multiple streams over
    a single WebSocket connection in a standardised way.
    Incoming messages on streams are dispatched to consumers so you can
    just tie in consumers the normal way.

    Set a mapping of streams to an application classes in the "applications"
    keyword.
    """

    # timeout in seconds after close used before killing child applications.
    application_close_timeout = 10

    # the mapping of applications by stream_name
    applications = {}  # type: Dict[str: 'typing.Type'[channels.consumer.AsyncConsumer]]

    def __init__(self, scope: Dict[str, Any]):
        super().__init__(scope)
        self.stream_upstream_queues = {}  # type: Dict[str, asyncio.Queue]
        self.accepted_upstream_stream = set()
        self.disconnecting = False
        self.sent_close = False
        self._task_monitors = None  # type: typing.Optional[asyncio.Task]

    # Methods to INTERCEPT Client -> Stream Applications

    async def websocket_connect(self, message):
        """
        Connect and then inform each stream application.
        """
        await super().websocket_connect(message)
        for queue in self.stream_upstream_queues.values():
            queue.put_nowait(message)

    async def websocket_disconnect(self, message):
        """
        Handle when the connection is lost.
        """

        # set the disconnecting so that we know to to send frames further down.
        self.disconnecting = True

        for stream_name, queue in self.stream_upstream_queues.items():
            # inform all upstream applications that the connection is going
            #  down (this includes ones that never accepted!)
            queue.put_nowait(message)

        if self._task_monitors is None:
            await super().websocket_disconnect(message)
            return

        try:
            # wait for all the upstream applications to close down
            await asyncio.wait_for(
                self._task_monitors,
                timeout=self.application_close_timeout
            )
        except asyncio.TimeoutError:
            # they did not close down fast enough!
            # not to worry they will be killed very soon.
            logger.warning(
                "One or more child application stream of %r took too long to "
                "shut down and was killed.",
                self,
            )
        # the `disconnect` method on the de-multiplexer is called after
        # all upstream applications have stopped or the timeout has passed
        #  (whatever is faster).
        await super().websocket_disconnect(message)

    async def receive_json(self, content, **kwargs):
        """
        Rout the message down the correct stream.
        """
        # Check the frame looks good
        if isinstance(content, dict) and "stream" in content and "payload" in content:
            # Match it to a channel
            stream_name = content["stream"]
            try:
                stream_queue = await self._get_stream_queue(stream_name)

            except ValueError:
                raise ValueError(
                    "Invalid multiplexed frame received (stream not mapped)"
                )

            payload = content["payload"]

            # send it on to the application that handles this stream
            stream_queue.put_nowait(
                {
                    "type": "websocket.receive",
                    "text": await self.encode_json(payload)
                }
            )
            return

        else:
            raise ValueError("Invalid multiplexed **frame received (no channel/payload key)")

    # Methods to INTERCEPT Stream Applications -> Client

    async def websocket_send(self, message: Dict[str, Any], stream_name: str):
        """
        Capture downstream websocket.send messages from the stream applications.
        """
        text = message.get("text")
        # todo what to do on binary!

        json = await self.decode_json(text)
        data = {
            "stream": stream_name,
            "payload": json
        }

        await self.send_json(data)

    async def websocket_accept(self, message: Dict[str, Any], stream_name: str):
        """
        Intercept streams accepting the websocket connection and add them to
        the set of accepted upstream streams.

        An upstream Application must accept before messages will be
        forwarded onto it.
        """
        self.accepted_upstream_stream.add(stream_name)

    async def websocket_close(self, message: Dict[str, Any], stream_name: str):
        """
        Handle the downstream websocket.close message from a stream
        application.
        """
        # just remove the stream from the set of open streams
        self.accepted_upstream_stream.remove(stream_name)
        # we don't cancel the task here, that will happen later.
        # (when the main connection is closed).
        # the application task could still send messages
        # if it sends `websocket.accept` it will also start to recived messages
        # again.
        await self.close(code=message.get("code", None))

    # De-multiplexing methods

    async def __call__(self, receive, send):
        """
        Set up applications for each stream and set up self.
        """
        self.stream_upstream_queues, stream_tasks = await self._init_stream_applications()

        # use gather here since we want to die as soon as any one raises
        # an exception.

        self._task_monitors = asyncio.gather(
            *[self._monitor_task(name, task) for name, task in
             stream_tasks.items()]
        )

        try:
            # TODO this results in `Task was destroyed but it is pending!` sometimes

            await asyncio.gather(
                super().__call__(receive=receive, send=send),
                self._task_monitors
            )

        finally:
            try:
                self._task_monitors.cancel()
            finally:
                # this might have raised an exception.
                # cleanup stream applications
                for task in stream_tasks.values():
                    task.cancel()

    async def _monitor_task(self, stream_name: str, task: asyncio.Task):
        """
        Monitor a stream application to detect if it raises an exception.
        We need to wrap the task in this _monitor method so that we do not exit
        on the first StopConsumer exception.
        """
        try:
            await task
        except StopConsumer:
            # unlikely to come here since this would only happen if
            # 'StopConsumer' is raised either before or after the
            # `await_many_dispatch` in the __call__ but might sometimes happen.
            if stream_name in self.stream_upstream_queues:
                # remove this stream from the possible upstream streams.
                if stream_name in self.accepted_upstream_stream:
                    self.accepted_upstream_stream.remove(stream_name)
                # remove queue as well the task is no longer running after all.
                del self.stream_upstream_queues[stream_name]

                await self.close()

        except asyncio.CancelledError:
            # the task was.
            if stream_name in self.accepted_upstream_stream:
                self.accepted_upstream_stream.remove(stream_name)

            del self.stream_upstream_queues[stream_name]

            await self.close()

        except Exception as e:

            # if we have already received a 'websocket.disconnect'
            if not self.disconnecting:
                # https://tools.ietf.org/html/rfc6455#section-7.1.5
                # 1011 indicates that a server is terminating the connection because
                # it encountered an unexpected condition that prevented it from
                # fulfilling the request.
                await self.close(1011, force=True)
            # re raise the exception this will kill everything!
            raise e
        else:
            # If an application ends with StopConsumer while inside of
            # `await_many_dispatch` this is not re-raised in __call__
            # so we end up here without any exception
            if stream_name in self.accepted_upstream_stream:
                self.accepted_upstream_stream.remove(stream_name)
            del self.stream_upstream_queues[stream_name]

            await self.close()

    async def _multiplexing_send(self,
                                 message: Dict[str, Any],
                                 stream_name: str):
        """
        Called by stream applications when they `base_send(message)`.

        if message.type matches a method of this De-multiplexer this method
        will be called otherwise message will be passed directly up the
        application stack.
        """
        handler = getattr(self, get_handler_name(message), None)

        if handler:
            await handler(message, stream_name=stream_name)
        else:
            await self.base_send(message)

    async def _init_stream_applications(self) -> (
            Dict[str, asyncio.Queue], Dict[str, asyncio.Task]):
        """
        Create instances for each stream application and return a mapped set of
         upstream queues/tasks.
        """
        queues = {}  # type: Dict[str, asyncio.Queue]
        tasks = {}  # type: Dict[str, asyncio.Task]

        for (stream_name, application_class) in self.applications.items():
            # Make an instance of the application

            queue = asyncio.Queue()
            application_instance = application_class(self.scope)

            # Run it, and stash the future for later checking
            stream_future = application_instance(
                receive=queue.get,
                send=partial(
                    self._multiplexing_send,
                    stream_name=stream_name
                ),
            )

            tasks[stream_name] = asyncio.ensure_future(stream_future)
            queues[stream_name] = queue

        return queues, tasks

    async def _get_stream_queue(self, stream_name: str) -> asyncio.Queue:
        """
        Get the queue for a given stream, so that one can send a message
         upstream.
        """

        if stream_name in self.stream_upstream_queues:
            if stream_name in self.accepted_upstream_stream:
                return self.stream_upstream_queues[stream_name]

        # do not include the `stream_name` in the exception to avoid the
        # injection of bad strings from users into logs, this could result in
        # a possible security issues depending on how logs are parsed later on.

        raise ValueError(
            "No child stream application for this lookup,"
        )

    async def close(self, code=None, force=False):
        """
        Send close command. This will not be sent if:
        a) we have already sent it
        b) we have already received a `websocket_disconnect` message
        c) there is at least one upstream stream that is still open.

        but if `force` is set it will still send the close command regardless.
        """

        if (len(self.accepted_upstream_stream) > 0 or self.sent_close or
                self.disconnecting) and not force:
            return

        self.sent_close = True

        await super().close(code=code)
