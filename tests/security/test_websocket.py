import pytest

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.security.websocket import OriginValidator
from channels.testing import WebsocketCommunicator


@pytest.mark.asyncio
async def test_origin_validator():
    """
    Tests that OriginValidator correctly allows/denies connections.
    """
    # Make our test application
    application = OriginValidator(AsyncWebsocketConsumer, ["allowed-domain.com"])
    # Test a normal connection
    communicator = WebsocketCommunicator(application, "/", headers=[(b"origin", b"http://allowed-domain.com")])
    connected, _ = await communicator.connect()
    assert connected
    await communicator.disconnect()
    # Test a bad connection
    communicator = WebsocketCommunicator(application, "/", headers=[(b"origin", b"http://bad-domain.com")])
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_origin_validator_full():
    """
    Tests that OriginValidator correctly allows/denies connections with full option.
    Allowed-domain: scheme://allowed-domain[:port]. Port is optional, but recommended.
    """
    # Make our test application
    application = OriginValidator(AsyncWebsocketConsumer, ["http://allowed-domain.com:8080",
                                                           "https://allowed-domain.com:8443"],
                                  full=True, check_cert=False)
    # Test a normal connection
    communicator = WebsocketCommunicator(application, "/", headers=[(b"origin", b"http://allowed-domain.com")])
    connected, _ = await communicator.connect()
    assert connected
    await communicator.disconnect()
    # Test a normal connection. With port
    communicator = WebsocketCommunicator(application, "/", headers=[(b"origin", b"https://allowed-domain.com:8443")])
    connected, _ = await communicator.connect()
    assert connected
    # Test a bad connection. Without scheme
    communicator = WebsocketCommunicator(application, "/", headers=[(b"origin", b".bad-domain.com")])
    connected, _ = await communicator.connect()
    assert not connected
    # Test a bad connection. Invalid port
    communicator = WebsocketCommunicator(application, "/", headers=[(b"origin", b"https://bad-domain.com:8445")])
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()
    # Test a bad connection
    communicator = WebsocketCommunicator(application, "/", headers=[(b"origin", b".bad-domain.com")])
    connected, _ = await communicator.connect()
    assert not connected
    await communicator.disconnect()
