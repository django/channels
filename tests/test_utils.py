import asyncio
from unittest import mock

import async_timeout
import pytest

from channels.utils import await_many_dispatch


async def sleep_task(*args):
    await asyncio.sleep(10)


@pytest.mark.asyncio
async def test_cancel_callback_called():
    cancel_callback = mock.AsyncMock()
    with pytest.raises(asyncio.TimeoutError):
        async with async_timeout.timeout(0):
            await await_many_dispatch([sleep_task], sleep_task, cancel_callback)
    assert cancel_callback.called
