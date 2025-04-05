import asyncio
import types


def name_that_thing(thing):
    """
    Returns either the function/class path or just the object's repr
    """
    # Instance method
    if hasattr(thing, "im_class"):
        # Mocks will recurse im_class forever
        if hasattr(thing, "mock_calls"):
            return "<mock>"
        return name_that_thing(thing.im_class) + "." + thing.im_func.func_name
    # Other named thing
    if hasattr(thing, "__name__"):
        if hasattr(thing, "__class__") and not isinstance(
            thing, (types.FunctionType, types.MethodType)
        ):
            if thing.__class__ is not type and not issubclass(thing.__class__, type):
                return name_that_thing(thing.__class__)
        if hasattr(thing, "__self__"):
            return "%s.%s" % (thing.__self__.__module__, thing.__self__.__name__)
        if hasattr(thing, "__module__"):
            return "%s.%s" % (thing.__module__, thing.__name__)
    # Generic instance of a class
    if hasattr(thing, "__class__"):
        return name_that_thing(thing.__class__)
    return repr(thing)


async def await_many_dispatch(_, consumer_callables, dispatch):
    """
    Given a set of consumer callables, awaits on them all and passes results
    from them to the dispatch awaitable as they come in.
    """
    # Call all callables, and ensure all return types are Futures
    tasks = [
        asyncio.ensure_future(consumer_callable())
        for consumer_callable in consumer_callables
    ]
    try:
        while True:
            # Wait for any of them to complete
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            # Find the completed one(s), yield results, and replace them
            for i, task in enumerate(tasks):
                if task.done():
                    result = task.result()
                    await dispatch(result)
                    tasks[i] = asyncio.ensure_future(consumer_callables[i]())
    finally:
        # Make sure we clean up tasks on exit
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


class PriorityTaskManager:
    def __init__(self, priority_message_types=None):
        self.current_task = None
        self.close_message_received = False
        self.priority_message_types = priority_message_types

    async def handle_message(self, message, dispatch):
        if self.close_message_received:
            return
        if message["type"] in self.priority_message_types:
            self.close_message_received = True

            if self.current_task and not self.current_task.done():
                self.current_task.cancel()
                try:
                    await self.current_task
                except asyncio.CancelledError:
                    pass
            await dispatch(message)
        else:
            if self.current_task is None or self.current_task.done():
                self.current_task = asyncio.create_task(dispatch(message))
            await self.current_task


async def await_many_dispatch_with_priority(self, consumer_callables, dispatch):
    """
    Given a set of consumer callables, awaits on them all and passes results
    from them to the dispatch awaitable as they come in.
    Separate the messages with type "websocket.disconnect" to a priority queue. 
    As they should be handled prior to shutdown by ASGI server(example: by daphne, if "websocket.disconnect" sent,
    daphne waits for application_close_timeout (10 s default)) and kills the Application,
    which may cause websocket.disconnect message not handled in consumer properly.
    """
    # Call all callables, and ensure all return types are Futures
    task_manager = PriorityTaskManager(priority_message_types=self.priority_message_types)
    queue = asyncio.Queue()
    priority_queue = asyncio.Queue()

    async def receive_messages(consumer_callable):        
        try:
            while True:
                message = await consumer_callable()
                if message.get("type") in self.priority_message_types:
                    priority_queue.put_nowait(message)
                else:
                    queue.put_nowait(message)
        except asyncio.CancelledError:
            pass
    
    async def process_messages(queue_to_process: asyncio.Queue):
        try:
            while True:
                message = await queue_to_process.get()
                await task_manager.handle_message(message, dispatch)
        except asyncio.CancelledError:
            pass

    producer_tasks = [
        asyncio.create_task(receive_messages(consumer_callable))
        for consumer_callable in consumer_callables
    ]

    processing_tasks = [
        asyncio.create_task(process_messages(queue)),
        asyncio.create_task(process_messages(priority_queue)),
    ]
    try:
        completed_tasks, pending = await asyncio.wait(
            processing_tasks, return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        exception = None
        for task in producer_tasks + processing_tasks:
            if task.done() and task.exception():
                exception = task.exception()
            if not task.done():
                task.cancel()
            
            
        # Wait for cancellation to complete
        await asyncio.gather(*producer_tasks, *processing_tasks, return_exceptions=True)
        if exception:
            raise exception