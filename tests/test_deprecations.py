import pytest

from channels.http import AsgiHandler
from channels.routing import ProtocolTypeRouter


def test_automatical_http_protocol_registration_deprecation():
    with pytest.warns(DeprecationWarning):
        ProtocolTypeRouter({})


def test_asgi_handler_deprecation():
    with pytest.warns(DeprecationWarning, match="AsgiHandler is deprecated"):
        AsgiHandler()
