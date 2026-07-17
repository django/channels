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


async def await_many_dispatch(consumer_callables, dispatch):
    """
    Given a set of consumer callables, awaits on them all and passes results
    from them to the dispatch awaitable as they come in.
    If a dispatch awaitable raises an exception,
    this coroutine will fail with that exception.
    """
    # Call all callables, and ensure all return types are Futures
    tasks = [
        asyncio.ensure_future(consumer_callable())
        for consumer_callable in consumer_callables
    ]

    dispatch_tasks = []
    fut = asyncio.Future()  # For child task to report an exception
    tasks.append(fut)

    def on_dispatch_task_complete(task):
        dispatch_tasks.remove(task)
        exc = task.exception()
        if exc and not isinstance(exc, asyncio.CancelledError) and not fut.done():
            fut.set_exception(exc)

    try:
        while True:
            # Wait for any of them to complete
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            # Find the completed one(s), yield results, and replace them
            for i, task in enumerate(tasks):
                if task.done():
                    if task == fut:
                        exc = fut.exception()  # Child task has reported an exception
                        if exc:
                            raise exc
                    else:
                        result = task.result()
                        task = asyncio.create_task(dispatch(result))
                        dispatch_tasks.append(task)
                        task.add_done_callback(on_dispatch_task_complete)
                        tasks[i] = asyncio.ensure_future(consumer_callables[i]())
    finally:
        # Make sure we clean up tasks on exit
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if dispatch_tasks:
            """
            This may be needed if the consumer task running this coroutine
            is cancelled and one of the subtasks raises an exception after cancellation.
            """
            done, pending = await asyncio.wait(dispatch_tasks)
            for task in done:
                exc = task.exception()
                if exc and not isinstance(exc, asyncio.CancelledError):
                    raise exc
        if not fut.done():
            fut.set_result(None)
