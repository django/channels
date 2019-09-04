import re
import unittest
from tempfile import SpooledTemporaryFile
from unittest.mock import Mock, patch

import pytest
from django.core.exceptions import RequestDataTooBig
from django.http import HttpResponse
from django.test import override_settings

from asgiref.testing import ApplicationCommunicator
from channels.consumer import AsyncConsumer
from channels.http import AsgiHandler, AsgiRequest, AsgiRequestIO, StreamedAsgiHandler
from channels.sessions import SessionMiddlewareStack
from channels.testing import HttpCommunicator


class TestRequest:
    """
    Tests that ASGI request handling correctly decodes HTTP requests given scope
    and body.
    """

    @staticmethod
    def body_stream(stream_class, receive):
        """
        Prepare custom SpooledTemporaryFile or AsgiRequestIO body stream
        from 'receive' callable.
        """

        if stream_class is AsgiRequestIO:
            return AsgiRequestIO(receive)

        stream = stream_class()
        while True:
            message = receive()
            if "body" in message:
                stream.write(message["body"])
            if not message.get("more_body", False):
                stream.seek(0)
                return stream

    @pytest.mark.parametrize("stream_class", [SpooledTemporaryFile, AsgiRequestIO])
    def test_basic(self, stream_class):
        """
        Tests that the handler can decode the most basic request message,
        with all optional fields omitted.
        """

        request = AsgiRequest(
            {"http_version": "1.1", "method": "GET", "path": "/test/"},
            self.body_stream(stream_class, lambda: {}),
        )
        assert request.path == "/test/"
        assert request.method == "GET"
        assert not request.body
        assert "HTTP_HOST" not in request.META
        assert "REMOTE_ADDR" not in request.META
        assert "REMOTE_HOST" not in request.META
        assert "REMOTE_PORT" not in request.META
        assert "SERVER_NAME" in request.META
        assert "SERVER_PORT" in request.META
        assert not request.GET
        assert not request.POST
        assert not request.COOKIES

    @pytest.mark.parametrize("stream_class", [SpooledTemporaryFile, AsgiRequestIO])
    def test_extended(self, stream_class):
        """
        Tests a more fully-featured GET request
        """

        request = AsgiRequest(
            {
                "http_version": "1.1",
                "method": "GET",
                "path": "/test2/",
                "query_string": b"x=1&y=%26foo+bar%2Bbaz",
                "headers": {
                    "host": b"example.com",
                    "cookie": b"test-time=1448995585123; test-value=yeah",
                },
                "client": ["10.0.0.1", 1234],
                "server": ["10.0.0.2", 80],
            },
            self.body_stream(stream_class, lambda: {}),
        )
        assert request.path == "/test2/"
        assert request.method == "GET"
        assert not request.body
        assert request.META["HTTP_HOST"] == "example.com"
        assert request.META["REMOTE_ADDR"] == "10.0.0.1"
        assert request.META["REMOTE_HOST"] == "10.0.0.1"
        assert request.META["REMOTE_PORT"] == 1234
        assert request.META["SERVER_NAME"] == "10.0.0.2"
        assert request.META["SERVER_PORT"] == "80"
        assert request.GET["x"] == "1"
        assert request.GET["y"] == "&foo bar+baz"
        assert request.COOKIES["test-time"] == "1448995585123"
        assert request.COOKIES["test-value"] == "yeah"
        assert not request.POST

    @pytest.mark.parametrize("stream_class", [SpooledTemporaryFile, AsgiRequestIO])
    def test_post(self, stream_class):
        """
        Tests a POST body.
        """

        def receive():
            return {"type": "http.request", "body": b"djangoponies=are+awesome"}

        request = AsgiRequest(
            {
                "http_version": "1.1",
                "method": "POST",
                "path": "/test2/",
                "query_string": "django=great",
                "headers": {
                    "host": b"example.com",
                    "content-type": b"application/x-www-form-urlencoded",
                    "content-length": b"18",
                },
            },
            self.body_stream(stream_class, receive),
        )
        assert request.path == "/test2/"
        assert request.method == "POST"
        assert request.body == b"djangoponies=are+awesome"
        assert request.META["HTTP_HOST"] == "example.com"
        assert request.META["CONTENT_TYPE"] == "application/x-www-form-urlencoded"
        assert request.GET["django"] == "great"
        assert request.POST["djangoponies"] == "are awesome"
        with pytest.raises(KeyError):
            request.POST["django"]
        with pytest.raises(KeyError):
            request.GET["djangoponies"]

    @pytest.mark.parametrize("stream_class", [SpooledTemporaryFile, AsgiRequestIO])
    def test_post_files(self, stream_class):
        """
        Tests POSTing files using multipart form data.
        """
        body = (
            b"--BOUNDARY\r\n"
            + b'Content-Disposition: form-data; name="title"\r\n\r\n'
            + b"My First Book\r\n"
            + b"--BOUNDARY\r\n"
            + b'Content-Disposition: form-data; name="pdf"; filename="book.pdf"\r\n\r\n'
            + b"FAKEPDFBYTESGOHERE"
            + b"--BOUNDARY--"
        )

        def receive():
            return {"type": "http.request", "body": body}

        request = AsgiRequest(
            {
                "http_version": "1.1",
                "method": "POST",
                "path": "/test/",
                "headers": {
                    "content-type": b"multipart/form-data; boundary=BOUNDARY",
                    "content-length": str(len(body)).encode("ascii"),
                },
            },
            self.body_stream(stream_class, receive),
        )
        assert request.method == "POST"
        assert len(request.body) == len(body)
        assert request.META["CONTENT_TYPE"].startswith("multipart/form-data")
        assert request._read_started
        assert not request._post_parse_error
        assert request.POST["title"] == "My First Book"
        assert request.FILES["pdf"].read() == b"FAKEPDFBYTESGOHERE"

    @pytest.mark.parametrize("stream_class", [SpooledTemporaryFile, AsgiRequestIO])
    def test_chunked_post_files(self, stream_class):
        """
        Tests POSTing chunked files using multipart form data.
        """

        chunks = [
            b"--BOUNDARY\r\n",
            b'Content-Disposition: form-data; name="title"\r\n',
            b"\r\n",
            b"My First Book\r\n",
            b"",
            b"--BOUNDARY\r\n",
            b'Content-Disposition: form-data; name="pdf"; filename="book.pdf"\r\n',
            b"\r\n",
            b"FAKEPDFBYTESGOHERE",
            b"--BOUNDARY--\r\n",
            b"",
            b'Content-Disposition: form-data; name="txt"; filename="text.txt"\r\n\r\n',
            b"",
            b"FAKETEXT",
            b"--BOUNDARY--\r\n",
        ]
        body = b"".join(chunks)

        def receive():
            return {
                "type": "http.request",
                "body": chunks.pop(0),
                "more_body": bool(chunks),
            }

        request = AsgiRequest(
            {
                "http_version": "1.1",
                "method": "POST",
                "path": "/test/",
                "headers": {
                    "content-type": b"multipart/form-data; boundary=BOUNDARY",
                    "content-length": str(len(body)).encode("ascii"),
                },
            },
            self.body_stream(stream_class, receive),
        )

        assert request.method == "POST"
        assert request.META["CONTENT_TYPE"].startswith("multipart/form-data")
        assert request.FILES["pdf"].read() == b"FAKEPDFBYTESGOHERE"
        assert request._read_started
        assert not request._post_parse_error
        assert request.FILES["txt"].read() == b"FAKETEXT"
        assert request.POST["title"] == "My First Book"

    @pytest.mark.parametrize("stream_class", [SpooledTemporaryFile, AsgiRequestIO])
    def test_stream(self, stream_class):
        """
        Tests the body stream is emulated correctly.
        """

        def receive():
            return {"type": "http.request", "body": b"onetwothree"}

        request = AsgiRequest(
            {
                "http_version": "1.1",
                "method": "PUT",
                "path": "/",
                "headers": {"host": b"example.com", "content-length": b"11"},
            },
            self.body_stream(stream_class, receive),
        )
        assert request.method == "PUT"
        assert request.read(3) == b"one"
        assert request.read() == b"twothree"

    def test_script_name(self):
        request = AsgiRequest(
            {
                "http_version": "1.1",
                "method": "GET",
                "path": "/test/",
                "root_path": "/path/to/",
            },
            None,  # Dummy value.
        )

        assert request.path == "/path/to/test/"

    @pytest.mark.parametrize("stream_class", [SpooledTemporaryFile, AsgiRequestIO])
    def test_max_memory_size_exceeded(self, stream_class):
        def receive():
            return {"type": "http.request", "body": b""}

        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1):
            with pytest.raises(RequestDataTooBig):
                AsgiRequest(
                    {
                        "http_version": "1.1",
                        "method": "PUT",
                        "path": "/",
                        "headers": {"host": b"example.com", "content-length": b"1000"},
                    },
                    self.body_stream(stream_class, receive),
                ).body

    @pytest.mark.parametrize("stream_class", [SpooledTemporaryFile, AsgiRequestIO])
    def test_size_check_ignores_files(self, stream_class):
        """
        Make sure that AsgiRequest calculates the DATA_UPLOAD_MAX_MEMORY_SIZE
        check against the total request size excluding any file upload data.
        """

        name = b"Title"
        title = b"My first book"
        file_data = (
            b"FAKEPDFBYTESGOHERETHISISREALLYLONGBUTNOTUSEDTOCOMPUTETHESIZEOFTHEREQUEST"
        )
        body = (
            b"--BOUNDARY\r\n"
            + b'Content-Disposition: form-data; name="'
            + name
            + b'"\r\n\r\n'
            + title
            + b"\r\n"
            + b"--BOUNDARY\r\n"
            + b'Content-Disposition: form-data; name="pdf"; filename="book.pdf"\r\n\r\n'
            + file_data
            + b"--BOUNDARY--"
        )

        def receive():
            return {"type": "http.request", "body": body}

        scope = {
            "http_version": "1.1",
            "method": "POST",
            "path": "/test/",
            "headers": {
                "content-type": b"multipart/form-data; boundary=BOUNDARY",
                "content-length": str(len(body)).encode("ascii"),
            },
        }

        # Check the size in which the body of the files certainly does not
        # fit into the 'DATA_UPLOAD_MAX_MEMORY_SIZE' setting. But this size
        # is greater than the size of the fields of the POST request and
        # should not lead to an exception.
        allowable_size = len(file_data) - 10
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=allowable_size):
            AsgiRequest(scope, self.body_stream(stream_class, receive)).POST

        exceptional_size = len(name + title) - 10
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=exceptional_size):
            with pytest.raises(RequestDataTooBig):
                AsgiRequest(scope, self.body_stream(stream_class, receive)).POST

    @pytest.mark.parametrize("stream_class", [SpooledTemporaryFile, AsgiRequestIO])
    def test_size_check_ignores_chunked_files(self, stream_class):
        name = b"Title"
        title = b"My first book"
        file_data = (
            b"FAKEPDFBYTESGOHERETHISISREALLYLONGBUTNOTUSEDTOCOMPUTETHESIZEOFTHEREQUEST"
        )
        chunks = [
            b"--BOUNDARY\r\n",
            b'Content-Disposition: form-data; name="',
            name,
            b'"\r\n\r\n',
            title[:10],
            title[10:],
            b"\r\n",
            b"--BOUNDARY\r\n",
            b'Content-Disposition: form-data; name="pdf"; filename="book.pdf"\r\n\r\n',
            file_data[:50],
            file_data[50:],
            b"--BOUNDARY--",
        ]
        body = b"".join(chunks)

        def receive():
            return {
                "type": "http.request",
                "body": chunks.pop(0),
                "more_body": bool(chunks),
            }

        scope = {
            "http_version": "1.1",
            "method": "POST",
            "path": "/test/",
            "headers": {
                "content-type": b"multipart/form-data; boundary=BOUNDARY",
                "content-length": str(len(body)).encode("ascii"),
            },
        }

        # Check the size in which the body of the files certainly does not
        # fit into the 'DATA_UPLOAD_MAX_MEMORY_SIZE' setting. But this size
        # is greater than the size of the fields of the POST request and
        # should not lead to an exception.
        allowable_size = len(file_data) - 10
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=allowable_size):
            AsgiRequest(scope, self.body_stream(stream_class, receive)).POST


# Handler tests


def fake_get_response(request):
    """
    Mocked 'get_response' method for AsgiHandler-AsgiRequest tests
    with GET requests.
    """
    assert request.method == "GET"
    # Access request body to ensure it is read() in sync context.
    _ = request.body
    return HttpResponse("fake")


class MockHandler(AsgiHandler):
    """
    Testing subclass of AsgiHandler that has the actual Django response part
    ripped out.
    """

    get_response = Mock(side_effect=fake_get_response)


class MockStreamedHandler(StreamedAsgiHandler):
    """
    Testing subclass of StreamedAsgiHandler that has the actual Django response
    part ripped out.
    """

    get_response = Mock(side_effect=fake_get_response)


@pytest.mark.parametrize("application", [MockHandler, MockStreamedHandler])
@pytest.mark.asyncio
async def test_handler_basic(application):
    """
    Tests very basic request handling, no body.
    """
    scope = {"type": "http", "http_version": "1.1", "method": "GET", "path": "/test/"}
    handler = ApplicationCommunicator(application, scope)
    await handler.send_input({"type": "http.request"})
    await handler.receive_output(1)  # response start
    await handler.receive_output(1)  # response body

    request, = application.get_response.call_args[0]
    assert request.scope == scope
    assert request.body == b""


@pytest.mark.parametrize("application", [MockHandler, MockStreamedHandler])
@pytest.mark.asyncio
async def test_handler_body_single(application):
    """
    Tests request handling with a single-part body
    """
    scope = {"type": "http", "http_version": "1.1", "method": "GET", "path": "/test/"}
    handler = ApplicationCommunicator(application, scope)
    await handler.send_input(
        {"type": "http.request", "body": b"chunk one \x01 chunk two"}
    )
    await handler.receive_output(1)  # response start
    await handler.receive_output(1)  # response body

    request, = application.get_response.call_args[0]
    assert request.scope == scope
    assert request.body == b"chunk one \x01 chunk two"


@pytest.mark.parametrize("application", [MockHandler, MockStreamedHandler])
@pytest.mark.asyncio
async def test_handler_body_multiple(application):
    """
    Tests request handling with a multi-part body
    """
    scope = {"type": "http", "http_version": "1.1", "method": "GET", "path": "/test/"}
    handler = ApplicationCommunicator(application, scope)
    await handler.send_input(
        {"type": "http.request", "body": b"chunk one", "more_body": True}
    )
    await handler.send_input(
        {"type": "http.request", "body": b" \x01 ", "more_body": True}
    )
    await handler.send_input({"type": "http.request", "body": b"chunk two"})
    await handler.receive_output(1)  # response start
    await handler.receive_output(1)  # response body

    request, = application.get_response.call_args[0]
    assert request.scope == scope
    assert request.body == b"chunk one \x01 chunk two"


@pytest.mark.parametrize("application", [MockHandler, MockStreamedHandler])
@pytest.mark.asyncio
async def test_handler_body_ignore_extra(application):
    """
    Tests request handling ignores anything after more_body: False
    """
    scope = {"type": "http", "http_version": "1.1", "method": "GET", "path": "/test/"}
    handler = ApplicationCommunicator(application, scope)
    await handler.send_input(
        {"type": "http.request", "body": b"chunk one", "more_body": False}
    )
    await handler.send_input({"type": "http.request", "body": b" \x01 "})
    await handler.receive_output(1)  # response start
    await handler.receive_output(1)  # response body

    request, = application.get_response.call_args[0]
    assert request.scope == scope
    assert request.body == b"chunk one"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_sessions():
    class SimpleHttpApp(AsyncConsumer):
        """
        Barebones HTTP ASGI app for testing.
        """

        async def http_request(self, event):
            self.scope["session"].save()
            assert self.scope["path"] == "/test/"
            assert self.scope["method"] == "GET"
            await self.send(
                {"type": "http.response.start", "status": 200, "headers": []}
            )
            await self.send({"type": "http.response.body", "body": b"test response"})

    communicator = HttpCommunicator(
        SessionMiddlewareStack(SimpleHttpApp), "GET", "/test/"
    )
    response = await communicator.get_response()
    headers = response.get("headers", [])

    assert len(headers) == 1
    name, value = headers[0]

    assert name == b"Set-Cookie"
    value = value.decode("utf-8")

    assert re.compile(r"sessionid=").search(value) is not None

    assert re.compile(r"expires=").search(value) is not None

    assert re.compile(r"HttpOnly").search(value) is not None

    assert re.compile(r"Max-Age").search(value) is not None

    assert re.compile(r"Path").search(value) is not None


class MiddlewareTests(unittest.TestCase):
    def test_middleware_caching(self):
        """
        Tests that middleware is only loaded once
        and is successfully cached on the AsgiHandler class.
        """

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": "/test/",
        }

        AsgiHandler(scope)  # First Handler

        self.assertTrue(AsgiHandler._middleware_chain is not None)

        with patch(
            "django.core.handlers.base.BaseHandler.load_middleware"
        ) as super_function:
            AsgiHandler(scope)  # Second Handler
            self.assertFalse(super_function.called)
