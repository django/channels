import logging
import traceback

from channels.consumer import AsyncConsumer

from ..db import aclose_old_connections
from ..exceptions import StopConsumer

logger = logging.getLogger("channels.consumer")
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


class AsyncHttpConsumer(AsyncConsumer):
    """
    Async HTTP consumer. Provides basic primitives for building asynchronous
    HTTP endpoints.
    """

    def __init__(self, *args, **kwargs):
        self.body = []

    async def send_headers(self, *, status=200, headers=None):
        """
        Sets the HTTP response status and headers. Headers may be provided as
        a list of tuples or as a dictionary.
        """
        if headers is None:
            headers = []
        elif isinstance(headers, dict):
            headers = list(headers.items())

        await self.send(
            {"type": "http.response.start", "status": status, "headers": headers}
        )

    async def send_body(self, body, *, more_body=False):
        """
        Sends a response body to the client. The method expects a bytestring.
        """
        assert isinstance(body, bytes), "Body is not bytes"
        await self.send(
            {"type": "http.response.body", "body": body, "more_body": more_body}
        )

    async def send_response(self, status, body, **kwargs):
        """
        Sends a response to the client.
        """
        await self.send_headers(status=status, **kwargs)
        await self.send_body(body)

    async def handle(self, body):
        """
        Receives the request body as a bytestring.
        """
        raise NotImplementedError(
            "Subclasses of AsyncHttpConsumer must provide a handle() method."
        )

    async def disconnect(self):
        """
        Overrideable place to run disconnect handling. Do not send anything
        from here.
        """
        pass

    async def http_request(self, message):
        """
        Async entrypoint - concatenates body fragments and hands off control
        to ``self.handle`` when the body has been completely received.
        """
        if "body" in message:
            self.body.append(message["body"])

        if not message.get("more_body"):
            try:
                await self.handle(b"".join(self.body))
            except Exception:
                logger.error(f"Error in handle(): {traceback.format_exc()}")
                await self.send_response(500, b"Internal Server Error")
                raise
            finally:
                await self.disconnect()
            raise StopConsumer()

    async def http_disconnect(self, message):
        """
        Let the user do their cleanup and close the consumer.
        """
        try:
            await self.disconnect()
            await aclose_old_connections()
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
        finally:
            raise StopConsumer()
