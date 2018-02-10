import asyncio

import pytest

from channels.generic.multiplexer import AsyncJsonWebsocketDemultiplexer
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.testing import WebsocketCommunicator


class EchoTestConsumer(AsyncJsonWebsocketConsumer):

    async def receive_json(self, content=None, **kwargs):
        await self.send_json(content)


class AltEchoTestConsumer(AsyncJsonWebsocketConsumer):

    async def receive_json(self, content=None, **kwargs):
        await self.send_json({"received": content, "alt_value": 123})


class EchoCloseAfterFirstTestConsumer(AsyncJsonWebsocketConsumer):

    async def receive_json(self, content=None, **kwargs):
        await self.send_json(content)
        await self.close()


class NeverAcceptTestConsumer(AsyncJsonWebsocketConsumer):
    async def websocket_connect(self, message):
        pass


class RaiseInAcceptTestConsumer(AsyncJsonWebsocketConsumer):
    async def websocket_connect(self, message):
        raise ValueError("Test my error")


class EchoDemultiplexerAsyncJson(AsyncJsonWebsocketDemultiplexer):
    applications = {
        "echostream": EchoTestConsumer,
        "altechostream": AltEchoTestConsumer,
        "closeafterfirst": EchoCloseAfterFirstTestConsumer,
        "neveraccept": NeverAcceptTestConsumer,
    }


class RaiseInAcceptDemultiplexerAsyncJson(AsyncJsonWebsocketDemultiplexer):
    applications = {
        "raiseinaccept": RaiseInAcceptTestConsumer
    }


@pytest.mark.asyncio
async def test_stream_routing():

    communicator = WebsocketCommunicator(
        EchoDemultiplexerAsyncJson,
        "/"
    )

    connected, _ = await communicator.connect()
    assert connected

    # Test sending
    await communicator.send_json_to(
        {
            "stream": "echostream",
            "payload": {"hello": "world"}
        }
    )

    response = await communicator.receive_json_from()

    assert response == {
        "stream": "echostream",
        "payload": {"hello": "world"}
    }

    # Test sending
    await communicator.send_json_to(
        {
            "stream": "altechostream",
            "payload": {"hello": "world"}
        }
    )

    response = await communicator.receive_json_from()

    assert response == {
        "stream": "altechostream",
        "payload": {"alt_value": 123, "received": {"hello": "world"}}
    }

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_stream_routing_not_listed():

    communicator = WebsocketCommunicator(
        EchoDemultiplexerAsyncJson,
        "/"
    )

    connected, _ = await communicator.connect()
    assert connected

    # Test sending
    await communicator.send_json_to(
        {
            "stream": "notlisted",
            "payload": {"hello": "world"}
        }
    )

    message = await communicator.receive_output()

    assert message == {
        "type": "websocket.close"
    }

    with pytest.raises(ValueError, message="Invalid multiplexed frame received (stream not mapped)"):
        await communicator.wait()


@pytest.mark.asyncio
async def test_stream_no_payload():

    communicator = WebsocketCommunicator(
        EchoDemultiplexerAsyncJson,
        "/"
    )

    connected, _ = await communicator.connect()
    assert connected

    # Test sending
    await communicator.send_json_to(
        {
            "stream": "echostream",
            "no_payload": {"hello": "world"}
        }
    )

    message = await communicator.receive_output()

    assert message == {
        "type": "websocket.close"
    }

    with pytest.raises(ValueError, message="Invalid multiplexed **frame received (no channel/payload key)"):
        await communicator.wait()


@pytest.mark.asyncio
async def test_stream_close():

    communicator = WebsocketCommunicator(
        EchoDemultiplexerAsyncJson,
        "/"
    )

    connected, _ = await communicator.connect()
    assert connected

    # Test sending
    await communicator.send_json_to(
        {
            "stream": "echostream",
            "payload": {"hello": "world"}
        }
    )

    response = await communicator.receive_json_from()

    assert response == {
        "stream": "echostream",
        "payload": {"hello": "world"}
    }

    await communicator.send_json_to(
        {
            "stream": "closeafterfirst",
            "payload": {"hello": "world"}
        }
    )

    response = await communicator.receive_json_from()

    assert response == {
        "stream": "closeafterfirst",
        "payload": {"hello": "world"}
    }

    # Test to a non closed endpoint
    await communicator.send_json_to(
        {
            "stream": "echostream",
            "payload": {"hello": "world"}
        }
    )

    response = await communicator.receive_json_from()

    assert response == {
        "stream": "echostream",
        "payload": {"hello": "world"}
    }

    await communicator.send_json_to(
        {
            "stream": "closeafterfirst",
            "payload": {"hello": "world"}
        }
    )

    message = await communicator.receive_output()

    assert message == {
        "type": "websocket.close"
    }

    with pytest.raises(
            ValueError,
            message="Invalid multiplexed frame received (stream not mapped)"):
        await communicator.wait()


@pytest.mark.asyncio
async def test_stream_routing_neveraccept():

    communicator = WebsocketCommunicator(
        EchoDemultiplexerAsyncJson,
        "/"
    )

    connected, _ = await communicator.connect()
    assert connected

    # Test sending
    await communicator.send_json_to(
        {
            "stream": "neveraccept",
            "payload": {"hello": "world"}
        }
    )

    message = await communicator.receive_output()

    assert message == {
        "type": "websocket.close"
    }

    with pytest.raises(ValueError, message="Invalid multiplexed frame received (stream not mapped)"):
        await communicator.wait()


@pytest.mark.asyncio
async def test_stream_routing_raiseinaccept():

    communicator = WebsocketCommunicator(
        RaiseInAcceptDemultiplexerAsyncJson,
        "/"
    )

    connected, _ = await communicator.connect()
    assert connected

    message = await communicator.receive_output()

    assert message == {
        "type": "websocket.close", "code": 1011
    }

    with pytest.raises(ValueError, message="Test my error"):
        await communicator.wait()


@pytest.mark.asyncio
async def test_slow_disconnect():
    results = {}

    class TestConsumer(AsyncJsonWebsocketConsumer):
        async def disconnect(self, code):
            results["sleep_start"] = True
            await asyncio.sleep(1)
            results["sleep_end"] = True

    class DemultiplexerAsyncJson(AsyncJsonWebsocketDemultiplexer):

        # reduce timeout to make tests run faster.
        application_close_timeout = 0.1

        applications = {
            "mystream": TestConsumer,
        }

    communicator = WebsocketCommunicator(DemultiplexerAsyncJson, "/testws/")

    connected, _ = await communicator.connect()

    assert connected

    await communicator.disconnect()

    assert "sleep_start" in results
    assert "sleep_end" not in results
