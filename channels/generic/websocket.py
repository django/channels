import json
from typing import Any, Dict, List

from asgiref.sync import async_to_sync
from channels.consumer import AsyncConsumer, SyncConsumer
from channels.exceptions import (
    AcceptConnection,
    DenyConnection,
    InvalidChannelLayerError,
    StopConsumer,
)


class WebsocketConsumer(SyncConsumer):
    """
    Base WebSocket consumer. Provides a general encapsulation for the
    WebSocket handling model that other applications can build on.
    """

    groups = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.groups is None:
            self.groups = []

    def websocket_connect(self, message: Dict[str, Any]) -> None:
        """
        Called when a WebSocket connection is opened.
        """
        try:
            for group in self.groups:
                async_to_sync(self.channel_layer.group_add)(group, self.channel_name)
        except AttributeError:
            raise InvalidChannelLayerError(
                "BACKEND is unconfigured or doesn't support groups"
            )
        try:
            self.connect()
        except AcceptConnection:
            self.accept()
        except DenyConnection:
            self.close()

    def connect(self) -> None:
        self.accept()

    def accept(self, subprotocol: List[str] = None) -> None:
        """
        Accepts an incoming socket
        """
        super().send({"type": "websocket.accept", "subprotocol": subprotocol})

    def websocket_receive(self, message: Dict[str, Any]) -> None:
        """
        Called when a WebSocket frame is received. Decodes it and passes it
        to receive().
        """
        if "text" in message:
            self.receive(text_data=message["text"])
        else:
            self.receive(bytes_data=message["bytes"])

    def receive(self, text_data: str = None, bytes_data: bytes = None):
        """
        Called with a decoded WebSocket frame.
        """
        pass

    def send(
        self, text_data: str = None, bytes_data: bytes = None, close: bool = False
    ):
        """
        Sends a reply back down the WebSocket
        """
        if text_data is not None:
            super().send({"type": "websocket.send", "text": text_data})
        elif bytes_data is not None:
            super().send({"type": "websocket.send", "bytes": bytes_data})
        else:
            raise ValueError("You must pass one of bytes_data or text_data")
        if close:
            self.close(close)

    def close(self, code=None):
        """
        Closes the WebSocket from the server end
        """
        if code is not None and code is not True:
            super().send({"type": "websocket.close", "code": code})
        else:
            super().send({"type": "websocket.close"})

    def websocket_disconnect(self, message: Dict[str, Any]):
        """
        Called when a WebSocket connection is closed. Base level so you don't
        need to call super() all the time.
        """
        try:
            for group in self.groups:
                async_to_sync(self.channel_layer.group_discard)(
                    group, self.channel_name
                )
        except AttributeError:
            raise InvalidChannelLayerError(
                "BACKEND is unconfigured or doesn't support groups"
            )
        self.disconnect(message["code"])
        raise StopConsumer()

    def disconnect(self, code):
        """
        Called when a WebSocket connection is closed.
        """
        pass


class JsonWebsocketConsumer(WebsocketConsumer):
    """
    Variant of WebsocketConsumer that automatically JSON-encodes and decodes
    messages as they come in and go out. Expects everything to be text; will
    error on binary data.
    """

    def receive(
        self, text_data: str = None, bytes_data: bytes = None, **kwargs
    ) -> None:
        if text_data:
            self.receive_json(self.decode_json(text_data), **kwargs)
        else:
            raise ValueError("No text section for incoming WebSocket frame!")

    def receive_json(self, content: Dict[str, Any], **kwargs) -> None:
        """
        Called with decoded JSON content.
        """
        pass

    def send_json(self, content: Dict[str, Any], close=False) -> None:
        """
        Encode the given content as JSON and send it to the client.
        """
        super().send(text_data=self.encode_json(content), close=close)

    @classmethod
    def decode_json(cls, text_data: str) -> Dict[str, Any]:
        return json.loads(text_data)

    @classmethod
    def encode_json(cls, content: Dict[str, Any]) -> str:
        return json.dumps(content)


class AsyncWebsocketConsumer(AsyncConsumer):
    """
    Base WebSocket consumer, async version. Provides a general encapsulation
    for the WebSocket handling model that other applications can build on.
    """

    groups = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.groups is None:
            self.groups = []

    async def websocket_connect(self, message: Dict[str, Any]) -> None:
        """
        Called when a WebSocket connection is opened.
        """
        try:
            for group in self.groups:
                await self.channel_layer.group_add(group, self.channel_name)
        except AttributeError:
            raise InvalidChannelLayerError(
                "BACKEND is unconfigured or doesn't support groups"
            )
        try:
            await self.connect()
        except AcceptConnection:
            await self.accept()
        except DenyConnection:
            await self.close()

    async def connect(self) -> None:
        await self.accept()

    async def accept(self, subprotocol: List[str] = None) -> None:
        """
        Accepts an incoming socket
        """
        await super().send({"type": "websocket.accept", "subprotocol": subprotocol})

    async def websocket_receive(self, message: Dict[str, Any]) -> None:
        """
        Called when a WebSocket frame is received. Decodes it and passes it
        to receive().
        """
        if "text" in message:
            await self.receive(text_data=message["text"])
        else:
            await self.receive(bytes_data=message["bytes"])

    async def receive(
        self, text_data: str = None, bytes_data: bytes = None
    ) -> None:
        """
        Called with a decoded WebSocket frame.
        """
        pass

    async def send(
        self, text_data: str = None, bytes_data: bytes = None, close=False
    ) -> None:
        """
        Sends a reply back down the WebSocket
        """
        if text_data is not None:
            await super().send({"type": "websocket.send", "text": text_data})
        elif bytes_data is not None:
            await super().send({"type": "websocket.send", "bytes": bytes_data})
        else:
            raise ValueError("You must pass one of bytes_data or text_data")
        if close:
            await self.close(close)

    async def close(self, code=None):
        """
        Closes the WebSocket from the server end
        """
        if code is not None and code is not True:
            await super().send({"type": "websocket.close", "code": code})
        else:
            await super().send({"type": "websocket.close"})

    async def websocket_disconnect(self, message: Dict[str, Any]) -> None:
        """
        Called when a WebSocket connection is closed. Base level so you don't
        need to call super() all the time.
        """
        try:
            for group in self.groups:
                await self.channel_layer.group_discard(group, self.channel_name)
        except AttributeError:
            raise InvalidChannelLayerError(
                "BACKEND is unconfigured or doesn't support groups"
            )
        await self.disconnect(message["code"])
        raise StopConsumer()

    async def disconnect(self, code) -> None:
        """
        Called when a WebSocket connection is closed.
        """
        pass


class AsyncJsonWebsocketConsumer(AsyncWebsocketConsumer):
    """
    Variant of AsyncWebsocketConsumer that automatically JSON-encodes and decodes
    messages as they come in and go out. Expects everything to be text; will
    error on binary data.
    """

    async def receive(
        self, text_data: str = None, bytes_data: bytes = None, **kwargs
    ) -> None:
        if text_data:
            await self.receive_json(await self.decode_json(text_data), **kwargs)
        else:
            raise ValueError("No text section for incoming WebSocket frame!")

    async def receive_json(self, content: Dict[str, Any], **kwargs) -> None:
        """
        Called with decoded JSON content.
        """
        pass

    async def send_json(self, content: Dict[str, Any], close=False) -> None:
        """
        Encode the given content as JSON and send it to the client.
        """
        await super().send(text_data=await self.encode_json(content), close=close)

    @classmethod
    async def decode_json(cls, text_data: str) -> Dict[str, Any]:
        return json.loads(text_data)

    @classmethod
    async def encode_json(cls, content: Dict[str, Any]) -> str:
        return json.dumps(content)
