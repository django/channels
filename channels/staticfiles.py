from urllib.parse import urlparse
from urllib.request import url2pathname

from django.conf import settings
from django.contrib.staticfiles import utils
from django.contrib.staticfiles.views import serve
from django.http import Http404

from .http import AsgiHandler


class StaticFilesWrapper:
    """
    ASGI application which wraps another and intercepts requests for static
    files, passing them off to Django's static file serving.
    """

    def __init__(self, application, staticfiles_handler=None):
        self.application = application
        self.staticfiles_handler_class = staticfiles_handler or StaticFilesHandler
        self.base_url = urlparse(self.get_base_url())

    def get_base_url(self):
        utils.check_settings()
        return settings.STATIC_URL

    def _should_handle(self, path):
        """
        Checks if the path should be handled. Ignores the path if:

        * the host is provided as part of the base_url
        * the request's path isn't under the static files path (or equal)
        """
        return path.startswith(self.base_url[2]) and not self.base_url[1]

    async def __call__(self, scope, receive, send):
        # Only even look at HTTP requests
        if scope["type"] == "http" and self._should_handle(scope["path"]):
            # Serve static content
            return await self.staticfiles_handler_class()(
                dict(scope, static_base_url=self.base_url), receive, send
            )
        # Hand off to the main app
        return await self.application(scope, receive, send)


class StaticFilesHandler(AsgiHandler):
    """
    Subclass of AsgiHandler that serves directly from its get_response.
    """

    # TODO: Review hierarchy here. Do we NEED to inherit BaseHandler, AsgiHandler?

    async def __call__(self, scope, receive, send):
        self.static_base_url = scope["static_base_url"][2]
        return await super().__call__(scope, receive, send)

    def file_path(self, url):
        """
        Returns the relative path to the media file on disk for the given URL.
        """
        relative_url = url[len(self.static_base_url) :]
        return url2pathname(relative_url)

    def serve(self, request):
        """
        Actually serves the request path.
        """
        return serve(request, self.file_path(request.path), insecure=True)

    def get_response(self, request):
        """
        Always tries to serve a static file as you don't even get into this
        handler subclass without the wrapper directing you here.
        """
        try:
            return self.serve(request)
        except Http404 as e:
            if settings.DEBUG:
                from django.views import debug

                return debug.technical_404_response(request, e)
