import asyncio

import pytest
from django.conf.urls import url

from channels.generic.demultiplexer import AsyncJsonWebsocketDemultiplexer
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.routing import URLRouter
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
        "neveraccept": NeverAcceptTestConsumer
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

    # We do not expect a response so we will timeout waiting for one.
    with pytest.raises(ValueError, match="Invalid multiplexed frame received"):
        await communicator.receive_output()


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

    with pytest.raises(ValueError, match="Invalid multiplexed"):
        await communicator.wait()


@pytest.mark.asyncio
async def test_stream_close():
    """
    Test behavior when upstream application closes.
    """

    communicator = WebsocketCommunicator(
        EchoDemultiplexerAsyncJson,
        "/"
    )

    connected, _ = await communicator.connect()
    assert connected

    # Send to normal echoe server
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

    # send to consumer that will close after first message.
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

    # there should be no downstream message
    with pytest.raises(asyncio.TimeoutError):
        await communicator.receive_output()

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_stream_routing_raiseinaccept():

    communicator = WebsocketCommunicator(
        RaiseInAcceptDemultiplexerAsyncJson,
        "/"
    )

    with pytest.raises(ValueError, match="Test my error"):
        await communicator.connect()


@pytest.mark.asyncio
async def test_stream_no_accept():
    """
    Test that we wait for the first child application to `accept`
    """

    class TestConsumer(EchoTestConsumer):
        async def accept(self):
            pass

    class DemultiplexerAsyncJson(AsyncJsonWebsocketDemultiplexer):
        applications = {
            "test": TestConsumer
        }

    communicator = WebsocketCommunicator(
        DemultiplexerAsyncJson,
        "/"
    )

    with pytest.raises(asyncio.TimeoutError):
        await communicator.connect()

    class DemultiplexerAsyncJson(AsyncJsonWebsocketDemultiplexer):
        applications = {
            "test": TestConsumer,
            "echo": EchoTestConsumer
        }

    communicator = WebsocketCommunicator(
        DemultiplexerAsyncJson,
        "/"
    )

    # check we do connect since the EchoTestConsumer `accepts`
    connected, _ = await communicator.connect()
    assert connected

    # Test sending
    await communicator.send_json_to(
        {
            "stream": "echo",
            "payload": {"hello": "world"}
        }
    )

    response = await communicator.receive_json_from()

    assert response == {
        "stream": "echo",
        "payload": {"hello": "world"}
    }

    # Test sending
    await communicator.send_json_to(
        {
            "stream": "test",
            "payload": {"hello": "world"}
        }
    )

    # we cant send to `test` since it did not yet `accept` the connection
    with pytest.raises(ValueError, match="Invalid multiplexed frame received"):
        await communicator.receive_output()


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

        async def disconnect(self, code):
            await super().disconnect(code)
            # check that this is called in the correct order!
            if results.get("sleep_start") and results.get("sleep_end") is None:
                results["de-multiplexer-disconnect-order"] = True

    communicator = WebsocketCommunicator(DemultiplexerAsyncJson, "/testws/")

    connected, _ = await communicator.connect()

    assert connected

    await communicator.disconnect()

    assert "sleep_start" in results
    assert "sleep_end" not in results
    assert "de-multiplexer-disconnect-order" in results


@pytest.mark.asyncio
async def test_fast_disconnect():
    results = {}

    class TestConsumer(AsyncJsonWebsocketConsumer):
        async def disconnect(self, code):
            results["sleep_start"] = True
            await asyncio.sleep(0.01)
            results["sleep_end"] = True

    class DemultiplexerAsyncJson(AsyncJsonWebsocketDemultiplexer):

        # reduce timeout to make tests run faster.
        application_close_timeout = 0.1

        applications = {
            "mystream": TestConsumer,
        }

        async def disconnect(self, code):
            results["de-multiplexer-disconnect-order-pre-wait"] = True
            await super().disconnect(code)
            # check that this is called in the correct order!
            results["de-multiplexer-disconnect-order-post-wait"] = False

    communicator = WebsocketCommunicator(DemultiplexerAsyncJson, "/testws/")
    connected, _ = await communicator.connect()

    assert connected

    await communicator.disconnect()

    assert "sleep_start" in results
    assert "sleep_end" in results
    assert "de-multiplexer-disconnect-order-pre-wait" in results
    assert "de-multiplexer-disconnect-order-post-wait" not in results


@pytest.mark.asyncio
async def test_nested_with_url_router():

    class PathRoutedDemultiplexer(AsyncJsonWebsocketDemultiplexer):
        applications = {
            "pathfilter": URLRouter(
                [
                    url("^echo/?$", EchoTestConsumer),
                    url("^altecho/?$", AltEchoTestConsumer),
                ]
            )
        }

    communicator = WebsocketCommunicator(
        PathRoutedDemultiplexer,
        "/test"
    )

    with pytest.raises(ValueError, match="No route found for path 'test'."):
        await communicator.connect()

    communicator = WebsocketCommunicator(
        PathRoutedDemultiplexer,
        "echo"
    )

    connected, _ = await communicator.connect()
    assert connected

    # Test sending
    await communicator.send_json_to(
        {
            "stream": "pathfilter",
            "payload": {"hello": "world"}
        }
    )

    response = await communicator.receive_json_from()

    assert response == {
        "stream": "pathfilter",
        "payload": {"hello": "world"}
    }

    await communicator.disconnect()

    communicator = WebsocketCommunicator(
        PathRoutedDemultiplexer,
        "altecho"
    )

    connected, _ = await communicator.connect()
    assert connected

    # Test sending
    await communicator.send_json_to(
        {
            "stream": "pathfilter",
            "payload": {"hello": "world"}
        }
    )

    response = await communicator.receive_json_from()

    assert response == {
        "stream": "pathfilter",
        "payload": {"alt_value": 123, "received": {"hello": "world"}}
    }

    await communicator.disconnect()
