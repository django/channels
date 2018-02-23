import asyncio

import pytest
from django.conf.urls import url

from channels.generic.websocket import AsyncJsonWebsocketConsumer, AsyncJsonWebsocketDemultiplexer
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
    with pytest.raises(asyncio.TimeoutError):
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

    message = await communicator.receive_output()

    assert message == {
        "type": "websocket.close"
    }

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_stream_routing_raiseinaccept():

    communicator = WebsocketCommunicator(
        RaiseInAcceptDemultiplexerAsyncJson,
        "/"
    )

    connected, _ = await communicator.connect()
    assert connected

    with pytest.raises(ValueError, match="Test my error"):
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

        async def disconnect(self, code):
            # check that this is called in the correct order!
            if results.get("sleep_start") and results.get("sleep_end") is None:
                results["de-multiplexer-disconnect-order"] = True

        async def _child_application_closed(self, application_key: str):
            """
            This should not be called since the timeout runs over and thus
            the child is force closed after the observation run loop
            """
            results["_child_application_closed_callback"] = True

    communicator = WebsocketCommunicator(DemultiplexerAsyncJson, "/testws/")

    connected, _ = await communicator.connect()

    assert connected

    await communicator.disconnect()

    assert "sleep_start" in results
    assert "sleep_end" not in results
    assert "de-multiplexer-disconnect-order" in results

    assert "_child_application_closed_callback" not in results


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
            # check that this is called in the correct order!
            if results.get("sleep_start") and results.get("sleep_end"):
                results["de-multiplexer-disconnect-order"] = True

        async def _child_application_closed(self, application_key: str):
            """
            This should be called since the timeout did not go over.
            """
            if results.get("sleep_start") and results.get("sleep_end"):
                results["_child_application_closed_callback"] = True

        # note since `disconnect` is on a different co-routine to
        # `_child_application_closed` we cant assert relative the order of
        # these!

    communicator = WebsocketCommunicator(DemultiplexerAsyncJson, "/testws/")

    connected, _ = await communicator.connect()

    assert connected

    await communicator.disconnect()

    assert "sleep_start" in results
    assert "sleep_end" in results
    assert "de-multiplexer-disconnect-order" in results

    assert "_child_application_closed_callback" in results


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
