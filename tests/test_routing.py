import pytest
from django.core.exceptions import ImproperlyConfigured
from django.urls import path, re_path

from channels.routing import ChannelNameRouter, ProtocolTypeRouter, URLRouter


class MockApplication:
    call_args = None

    def __init__(self, return_value):
        self.return_value = return_value
        super().__init__()

    async def __call__(self, scope, receive, send):
        self.call_args = ((scope, receive, send), None)
        return self.return_value


@pytest.mark.asyncio
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
async def test_protocol_type_router():
    """
    Tests the ProtocolTypeRouter
    """
    # Test basic operation
    router = ProtocolTypeRouter(
        {
            "websocket": MockApplication(return_value="ws"),
            "http": MockApplication(return_value="http"),
        }
    )
    assert await router({"type": "websocket"}, None, None) == "ws"
    assert await router({"type": "http"}, None, None) == "http"
    # Test an unmatched type
    with pytest.raises(ValueError):
        await router({"type": "aprs"}, None, None)
    # Test a scope with no type
    with pytest.raises(KeyError):
        await router({"tyyyype": "http"}, None, None)


@pytest.mark.asyncio
async def test_channel_name_router():
    """
    Tests the ChannelNameRouter
    """
    # Test basic operation
    router = ChannelNameRouter(
        {
            "test": MockApplication(return_value=1),
            "other_test": MockApplication(return_value=2),
        }
    )
    assert await router({"channel": "test"}, None, None) == 1
    assert await router({"channel": "other_test"}, None, None) == 2
    # Test an unmatched channel
    with pytest.raises(ValueError):
        await router({"channel": "chat"}, None, None)
    # Test a scope with no channel
    with pytest.raises(ValueError):
        await router({"type": "http"}, None, None)


@pytest.mark.asyncio
async def test_url_router():
    """
    Tests the URLRouter
    """
    posarg_app = MockApplication(return_value=4)
    kwarg_app = MockApplication(return_value=5)
    defaultkwarg_app = MockApplication(return_value=6)
    router = URLRouter(
        [
            path("", MockApplication(return_value=1)),
            path("foo/", MockApplication(return_value=2)),
            re_path(r"bar", MockApplication(return_value=3)),
            re_path(r"^posarg/(\d+)/$", posarg_app),
            path("kwarg/<str:name>/", kwarg_app),
            path("defaultkwargs/", defaultkwarg_app, kwargs={"default": 42}),
        ]
    )
    # Valid basic matches
    assert await router({"type": "http", "path": "/"}, None, None) == 1
    assert await router({"type": "http", "path": "/foo/"}, None, None) == 2
    assert await router({"type": "http", "path": "/bar/"}, None, None) == 3
    assert await router({"type": "http", "path": "/bar/baz/"}, None, None) == 3
    # Valid positional matches
    assert await router({"type": "http", "path": "/posarg/123/"}, None, None) == 4
    assert posarg_app.call_args[0][0]["url_route"] == {"args": ("123",), "kwargs": {}}
    assert await router({"type": "http", "path": "/posarg/456/"}, None, None) == 4
    assert posarg_app.call_args[0][0]["url_route"] == {"args": ("456",), "kwargs": {}}
    # Valid keyword argument matches
    assert await router({"type": "http", "path": "/kwarg/hello/"}, None, None) == 5
    assert kwarg_app.call_args[0][0]["url_route"] == {
        "args": tuple(),
        "kwargs": {"name": "hello"},
    }
    assert await router({"type": "http", "path": "/kwarg/hellothere/"}, None, None) == 5
    assert kwarg_app.call_args[0][0]["url_route"] == {
        "args": tuple(),
        "kwargs": {"name": "hellothere"},
    }
    # Valid default keyword arguments
    assert await router({"type": "http", "path": "/defaultkwargs/"}, None, None) == 6
    assert defaultkwarg_app.call_args[0][0]["url_route"] == {
        "args": tuple(),
        "kwargs": {"default": 42},
    }

    # Invalid matches
    with pytest.raises(ValueError):
        await router({"type": "http", "path": "/nonexistent/"}, None, None)


@pytest.mark.asyncio
async def test_url_router_nesting():
    """
    Tests that nested URLRouters add their keyword captures together.
    """
    test_app = MockApplication(return_value=1)
    inner_router = URLRouter(
        [
            re_path(r"^book/(?P<book>[\w\-]+)/page/(?P<page>\d+)/$", test_app),
            re_path(r"^test/(\d+)/$", test_app),
        ]
    )
    outer_router = URLRouter(
        [
            re_path(
                r"^universe/(?P<universe>\d+)/author/(?P<author>\w+)/", inner_router
            ),
            re_path(r"^positional/(\w+)/", inner_router),
        ]
    )
    assert (
        await outer_router(
            {
                "type": "http",
                "path": "/universe/42/author/andrewgodwin/book/channels-guide/page/10/",
            },
            None,
            None,
        )
        == 1
    )
    assert test_app.call_args[0][0]["url_route"] == {
        "args": (),
        "kwargs": {
            "book": "channels-guide",
            "author": "andrewgodwin",
            "page": "10",
            "universe": "42",
        },
    }

    assert (
        await outer_router(
            {"type": "http", "path": "/positional/foo/test/3/"}, None, None
        )
        == 1
    )
    assert test_app.call_args[0][0]["url_route"] == {"args": ("foo", "3"), "kwargs": {}}


@pytest.mark.asyncio
async def test_url_router_nesting_path():
    """
    Tests that nested URLRouters add their keyword captures together when used
    with path().
    """
    from django.urls import path

    test_app = MockApplication(return_value=1)
    inner_router = URLRouter([path("test/<int:page>/", test_app)])

    def asgi_middleware(inner):
        # Some middleware which hides the fact that we have an inner URLRouter
        async def app(scope, receive, send):
            return await inner(scope, receive, send)

        app._path_routing = True
        return app

    outer_router = URLRouter(
        [path("number/<int:number>/", asgi_middleware(inner_router))]
    )

    assert await inner_router({"type": "http", "path": "/test/3/"}, None, None) == 1
    assert (
        await outer_router({"type": "http", "path": "/number/42/test/3/"}, None, None)
        == 1
    )
    assert test_app.call_args[0][0]["url_route"] == {
        "args": (),
        "kwargs": {"number": 42, "page": 3},
    }
    with pytest.raises(ValueError):
        assert await outer_router(
            {"type": "http", "path": "/number/42/test/3/bla/"}, None, None
        )
    with pytest.raises(ValueError):
        assert await outer_router(
            {"type": "http", "path": "/number/42/blub/"}, None, None
        )


@pytest.mark.asyncio
async def test_url_router_path():
    """
    Tests that URLRouter also works with path()
    """
    from django.urls import path

    kwarg_app = MockApplication(return_value=3)
    router = URLRouter(
        [
            path("", MockApplication(return_value=1)),
            path("foo/", MockApplication(return_value=2)),
            path("author/<name>/", kwarg_app),
            path("year/<int:year>/", kwarg_app),
        ]
    )
    # Valid basic matches
    assert await router({"type": "http", "path": "/"}, None, None) == 1
    assert await router({"type": "http", "path": "/foo/"}, None, None) == 2
    # Named without typecasting
    assert (
        await router({"type": "http", "path": "/author/andrewgodwin/"}, None, None) == 3
    )
    assert kwarg_app.call_args[0][0]["url_route"] == {
        "args": tuple(),
        "kwargs": {"name": "andrewgodwin"},
    }
    # Named with typecasting
    assert await router({"type": "http", "path": "/year/2012/"}, None, None) == 3
    assert kwarg_app.call_args[0][0]["url_route"] == {
        "args": tuple(),
        "kwargs": {"year": 2012},
    }
    # Invalid matches
    with pytest.raises(ValueError):
        await router({"type": "http", "path": "/nonexistent/"}, None, None)


@pytest.mark.asyncio
async def test_path_remaining():
    """
    Resolving continues in outer router if an inner router has no matching
    routes
    """
    inner_router = URLRouter([path("no-match/", MockApplication(return_value=1))])
    test_app = MockApplication(return_value=2)
    outer_router = URLRouter(
        [path("prefix/", inner_router), path("prefix/stuff/", test_app)]
    )
    outermost_router = URLRouter([path("", outer_router)])

    assert (
        await outermost_router({"type": "http", "path": "/prefix/stuff/"}, None, None)
        == 2
    )


def test_invalid_routes():
    """
    Test URLRouter route validation
    """
    from django.urls import include

    with pytest.raises(ImproperlyConfigured) as exc:
        URLRouter([path("", include([]))])

    assert "include() is not supported in URLRouter." in str(exc)
