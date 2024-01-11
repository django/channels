from channels.utils import await_many_dispatch
import asyncio
import async_timeout
from unittest import mock
import pytest


# stub for python 3.7 support
class AsyncMock(mock.MagicMock):
    def __init__(self, *args, **kwargs):
        super(AsyncMock, self).__init__(*args, **kwargs)
        self.__bool__ = lambda x: True
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


async def sleep_task(*args):
    await asyncio.sleep(10)


@pytest.mark.asyncio
async def test_cancel_callback_called():
    # can replace with mock.AsyncMock after python 3.7 support is dropped
    cancel_callback = AsyncMock()
    with pytest.raises(asyncio.TimeoutError):
        # timeout raises asyncio.CancelledError, and await_many_dispatch should
        # call cancel_callback
        async with async_timeout.timeout(0):
            await await_many_dispatch([sleep_task], sleep_task, cancel_callback)
    assert cancel_callback.called
