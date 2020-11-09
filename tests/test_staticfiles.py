import pytest

from channels.staticfiles import StaticFilesWrapper


@pytest.fixture(autouse=True)
def configure_static_files(settings):
    settings.STATIC_URL = "/static"
    settings.MEDIA_URL = "/media"


class MockApplication:
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.was_called = False

    async def __call__(self, scope, receive, send):
        self.was_called = True
        return self.return_value


class MockStaticHandler:
    async def __call__(self, scope, receive, send):
        return scope["path"]


def request_for_path(path, type="http"):
    return {
        "type": type,
        "path": path,
    }


@pytest.mark.asyncio
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
async def test_staticfiles_wrapper_serves_static_http_requests(settings):
    settings.STATIC_URL = "/mystatic/"

    application = MockApplication("application")

    wrapper = StaticFilesWrapper(application, staticfiles_handler=MockStaticHandler)

    scope = request_for_path("/mystatic/image.png")
    assert (
        await wrapper(scope, None, None) == "/mystatic/image.png"
    ), "StaticFilesWrapper should serve paths under the STATIC_URL path"
    assert (
        not application.was_called
    ), "The inner application should not be called when serving static files"


@pytest.mark.asyncio
async def test_staticfiles_wrapper_calls_application_for_non_static_http_requests():
    wrapper = StaticFilesWrapper(MockApplication("application"))

    non_static_path = request_for_path("/path/to/non/static/resource")
    assert (
        await wrapper(non_static_path, None, None) == "application"
    ), "StaticFilesWrapper should call inner application for non-static HTTP paths"

    non_http_path = request_for_path("/path/to/websocket", type="websocket")
    assert (
        await wrapper(non_http_path, None, None) == "application"
    ), "StaticFilesWrapper should call inner application for non-HTTP paths"


@pytest.mark.asyncio
async def test_staticfiles_wrapper_calls_application_for_non_http_paths(settings):
    settings.STATIC_URL = "/mystatic/"

    wrapper = StaticFilesWrapper(MockApplication("application"))

    non_http_static_path = request_for_path("/mystatic/match", type="websocket")
    assert await wrapper(non_http_static_path, None, None) == "application", (
        "StaticFilesWrapper should call inner application if path matches "
        "but type is not HTTP"
    )


@pytest.mark.asyncio
async def test_staticfiles_wrapper_calls_application_if_static_url_has_host(settings):
    settings.STATIC_URL = "http://hostname.com/mystatic/"

    wrapper = StaticFilesWrapper(MockApplication("application"))

    scope = request_for_path("/mystatic/match")
    assert await wrapper(scope, None, None) == "application", (
        "StaticFilesWrapper should call inner application if STATIC_URL contains a "
        "host, even if path matches"
    )


def test_is_single_callable():
    from asgiref.compatibility import is_double_callable

    wrapper = StaticFilesWrapper(None)

    assert not is_double_callable(wrapper), (
        "StaticFilesWrapper should be recognized as a single callable by "
        "asgiref compatibility tools"
    )
