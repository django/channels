import asyncio
import json

import pytest

from channels.generic.websocket import WebsocketConsumer, WebsocketMultiplexer
from channels.testing import WebsocketCommunicator


def make_test_consumer(reject=False):
    """
    Returns a test consumer class and its bound results dict
    """
    results = {}

    class TestConsumer(WebsocketConsumer):
        def connect(self):
            results["connected"] = True
            if reject:
                self.close()
            else:
                self.accept()

        def receive(self, text_data=None, bytes_data=None):
            results["received"] = (text_data, bytes_data)
            self.send(text_data=text_data, bytes_data=bytes_data)

        def disconnect(self, code):
            results["disconnected"] = code

    return results, TestConsumer


@pytest.mark.asyncio
async def test_websocket_multiplex():
    """
    Tests basic multiplexing.
    """

    results1, TestConsumer1 = make_test_consumer()
    results2, TestConsumer2 = make_test_consumer()

    # Make multiplexer
    multiplexer = WebsocketMultiplexer({
        "stream1": TestConsumer1,
        "stream2": TestConsumer2,
    })
    # Start up connection
    communicator = WebsocketCommunicator(multiplexer, "/testws/")
    connected, _ = await communicator.connect()
    assert connected
    # We need to give the child coroutines time to start
    await asyncio.sleep(0.1)
    assert "connected" in results1
    assert "connected" in results2
    # Test a payload to stream 1
    msg = json.dumps({"stream": "stream1", "payload": "hello world!"})
    await communicator.send_to(text_data=msg)
    response = await communicator.receive_from()
    assert response == msg
    assert results1["received"] == (json.dumps("hello world!"), None)
    assert "received" not in results2
    # And to stream 2
    msg = json.dumps({"stream": "stream2", "payload": [3, 4, 5]})
    await communicator.send_to(text_data=msg)
    response = await communicator.receive_from()
    assert response == msg
    assert results2["received"] == (json.dumps([3, 4, 5]), None)
    # Close out
    await communicator.disconnect()
    assert "disconnected" in results1
    assert "disconnected" in results2


@pytest.mark.asyncio
@pytest.mark.filterwarnings("ignore:Application for")
async def test_single_reject_multiplex():
    """
    Tests that if one consumer rejects a connection the other keeps working.
    """

    results1, TestConsumer1 = make_test_consumer(reject=True)
    results2, TestConsumer2 = make_test_consumer()

    # Make multiplexer
    multiplexer = WebsocketMultiplexer({
        "stream1": TestConsumer1,
        "stream2": TestConsumer2,
    })
    # Start up connection
    communicator = WebsocketCommunicator(multiplexer, "/testws/")
    connected, _ = await communicator.connect()
    assert connected
    # We need to give the child coroutines time to start
    await asyncio.sleep(0.1)
    assert "connected" in results1
    assert "connected" in results2
    # Test a payload to stream 1
    msg = json.dumps({"stream": "stream1", "payload": "hello world!"})
    await communicator.send_to(text_data=msg)
    await communicator.receive_nothing()
    assert "received" not in results1
    assert "received" not in results2
    # And to stream 2
    msg = json.dumps({"stream": "stream2", "payload": [3, 4, 5]})
    await communicator.send_to(text_data=msg)
    response = await communicator.receive_from()
    assert response == msg
    assert results2["received"] == (json.dumps([3, 4, 5]), None)
    # Close out
    await communicator.disconnect()
    assert "disconnected" not in results1
    assert "disconnected" in results2
