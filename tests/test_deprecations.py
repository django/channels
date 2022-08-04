import pytest

from channels.http import AsgiHandler


def test_asgi_handler_deprecation():
    with pytest.warns(DeprecationWarning, match="AsgiHandler is deprecated"):
        AsgiHandler()
