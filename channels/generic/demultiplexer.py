import asyncio
from functools import partial

from channels.consumer import get_handler_name
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class AsyncJsonWebsocketDemultiplexer(AsyncJsonWebsocketConsumer):
    """
    JSON-understanding WebSocket consumer subclass that handles de-multiplexing streams using a "stream" key in a
    top-level dict and the actual payload in a sub-dict called "payload".
    This lets you run multiple streams over a single WebSocket connection in a standardised way.
    Incoming messages on streams are dispatched to consumers so you can just tie in consumers the normal way.
    """
    applications = {}
    application_close_timeout = 5

    def __init__(self, scope):
        super().__init__(scope)
        self.application_streams = {}
        self.application_futures = {}
        self.applications_accepting_frames = set()
        self.closing = False

    async def __call__(self, receive, send):
        loop = asyncio.get_event_loop()
        # create the child applications
        await loop.create_task(self._create_upstream_applications())
        # start observing for messages
        message_consumer = loop.create_task(super().__call__(receive, send))
        try:
            # wait for either an upstream application to close or the message consumer loop.
            await asyncio.wait(
                list(self.application_futures.values()) + [message_consumer],
                return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            # make sure we clean up the message consumer loop
            message_consumer.cancel()
            try:
                # check if there were any exceptions raised
                await message_consumer
            except asyncio.CancelledError:
                pass
            finally:
                # Make sure we clean up upstream applications on exit
                for future in self.application_futures.values():
                    future.cancel()
                    try:
                        # check for exceptions
                        await future
                    except asyncio.CancelledError:
                        pass

    async def _create_upstream_applications(self):
        """
        Create the upstream applications.
        """
        loop = asyncio.get_event_loop()
        for steam_name, ApplicationsCls in self.applications.items():
            application = ApplicationsCls(self.scope)
            upstream_queue = asyncio.Queue()
            self.application_streams[steam_name] = upstream_queue
            self.application_futures[steam_name] = loop.create_task(
                application(
                    upstream_queue.get,
                    partial(self.dispatch_downstream, steam_name=steam_name)
                )
            )

    async def send_upstream(self, message, stream_name=None):
        """
        Send a message upstream to a de-multiplexed application.

        If stream_name is includes will send just to that upstream steam, if not included will send ot all upstream
        steams.
        """
        if stream_name is None:
            for steam_queue in self.application_streams.values():
                await steam_queue.put(message)
            return
        steam_queue = self.application_streams.get(stream_name)
        if steam_queue is None:
            raise ValueError("Invalid multiplexed frame received (stream not mapped)")
        await steam_queue.put(message)

    async def dispatch_downstream(self, message, steam_name):
        """
        Handle a downstream message coming from an upstream steam.

        if there is not handling method set for this method type it will propagate the message further downstream.

        This is called as part of the co-routine of an upstream steam, not the same loop as used for upstream messages
        in the de-multiplexer.
        """
        handler = getattr(self, get_handler_name(message), None)
        if handler:
            await handler(message, stream_name=steam_name)
        else:
            # if there is not handler then just pass the message further downstream.
            await self.base_send(message)

    # Websocket upstream handlers

    async def websocket_connect(self, message):
        await self.send_upstream(message)

    async def receive_json(self, content, **kwargs):
        """
        Rout the message down the correct stream.
        """
        # Check the frame looks good
        if isinstance(content, dict) and "stream" in content and "payload" in content:
            # Match it to a channel
            steam_name = content["stream"]
            payload = content["payload"]
            # block upstream frames
            if steam_name not in self.applications_accepting_frames:
                raise ValueError("Invalid multiplexed frame received (stream not mapped)")
            # send it on to the application that handles this stream
            await self.send_upstream(
                message={
                    "type": "websocket.receive",
                    "text": await self.encode_json(payload)
                },
                stream_name=steam_name
            )
            return
        else:
            raise ValueError("Invalid multiplexed **frame received (no channel/payload key)")

    async def websocket_disconnect(self, message):
        """
        Handle the disconnect message.

        This is propagated to all upstream applications.
        """
        # set this flag so as to ensure we don't send a downstream `websocket.close` message due to all
        # child applications closing.
        self.closing = True
        # inform all children
        await self.send_upstream(message)
        await super().websocket_disconnect(message)

    async def disconnect(self, code):
        """
        default is to wait for the child applications to close.
        """
        try:
            await asyncio.wait(
                self.application_futures.values(),
                return_when=asyncio.ALL_COMPLETED,
                timeout=self.application_close_timeout
            )
        except asyncio.TimeoutError:
            pass

    # Note if all child applications close within the timeout this cor-routine will be killed before we get here.

    async def websocket_send(self, message, stream_name):
        """
        Capture downstream websocket.send messages from the upstream applications.
        """
        text = message.get("text")
        # todo what to do on binary!
        json = await self.decode_json(text)
        data = {
            "stream": stream_name,
            "payload": json
        }
        await self.send_json(data)

    async def websocket_accept(self, message, stream_name):
        """
        Intercept downstream `websocket.accept` message and thus allow this upsteam application to accept websocket
        frames.
        """
        is_first = not self.applications_accepting_frames
        self.applications_accepting_frames.add(stream_name)
        # accept the connection after the first upstream application accepts.
        if is_first:
            await self.accept()

    async def websocket_close(self, message, stream_name):
        """
        Handle downstream `websocket.close` message.

        Will disconnect this upstream application from receiving any new frames.

        If there are not more upstream applications accepting messages it will then call `close`.
        """
        if stream_name in self.applications_accepting_frames:
            # remove from set of upsteams steams than can receive new messages
            self.applications_accepting_frames.remove(stream_name)
        # we are already closing due to an upstream websocket.disconnect command
        if self.closing:
            return
        # if none of the upstream applications are listing we need to close.
        if not self.applications_accepting_frames:
            await self.close(message.get("code"))
