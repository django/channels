import asyncio
import functools
import json
import warnings


class WebsocketMultiplexer:
    """
    ASGI application that wraps a series of other ASGI applications and
    multiplexes information down to them via a series of named streams.
    Each stream name is associated with one child application.

    Multiplexed messages (in and out) are a WebSocket text frame containing
    a JSON object with two keys:

        * "stream": A string specifying which stream this is for
        * "payload": The contents of the frame (native JSON, not a text string
          with more JSON inside it)

    Child applications will still send and receive text-frames with JSON
    as a string - the multiplexer will handle ensuring they are JSON. This
    allows applications to be swappable between a direct websocket app
    and one that lives inside a multiplexer.
    """

    def __init__(self, streams):
        self.streams = streams

    def __call__(self, scope):
        """
        Unlike middleware, this class has to handle the scope itself as we
        dispatch dynamically on each send/received frame. Thus, we hand back
        a wrapper object.
        """
        return WebsocketMultiplexerApplication(self, scope)


class WebsocketMultiplexerApplication:
    """
    ASGI application object used to proxy sends/receives for the multiplexer.
    """

    def __init__(self, multiplexer, scope):
        self.multiplexer = multiplexer
        self.scope = scope
        # Instantiate each of our child apps
        self.children = {}
        for stream, application in self.multiplexer.streams.items():
            # We add one key to the app scope so they know they're multiplexed
            app_scope = dict(self.scope)
            app_scope["multiplexer_stream"] = stream
            self.children[stream] = {
                "instance": application(app_scope),
                "queue": None,
                "task": None,
                "accepting": False,
                "buffer": [],
            }

    async def __call__(self, receive, send):
        """
        Main coroutine of the multiplexer. Receives incoming WebSocket messages
        and dispatches them to children.

        Notably, "connect" and "disconnect" go to all children, while "receive"
        gets dispatched to only one with the payload.
        """
        self.send = send
        # Make child coroutines and queues
        await self.create_children()
        # Main loop
        try:
            while True:
                event = await receive()
                # Websocket connect gets passed to each child. If the child rejects
                # the connection, it will be removed from the children dict.
                if event["type"] == "websocket.connect":
                    # Allow custom connection validation
                    if await self.allow_connection():
                        # OK, connection allowed, forward connect message
                        await self.broadcast_event(event)
                        await send({"type": "websocket.accept"})
                    else:
                        # Connection not allowed, send all children a close event
                        await self.broadcast_event({"type": "websocket.disconnect", "code": 1001})
                        # Then close the socket and exit
                        await send({"type": "websocket.close"})
                        break
                # Disconnect gets passed to every child
                elif event["type"] == "websocket.disconnect":
                    await self.broadcast_event(event)
                # Receive gets individually dispatched
                elif event["type"] == "websocket.receive":
                    await self.dispatch_event(event)
                else:
                    raise ValueError("Got unknown event type %s" % event["type"])
            # Don't exit until all our children do. If they take too long, the
            # ASGI server above us will kill us with a CancelledError, which
            # we propagate down into the children in the finally clause.
            for child in self.children.values():
                if not child["task"].done():
                    await child["task"]
        finally:
            # Cleanup
            del self.send
            # Last-ditch cancellation
            for child in self.children.values():
                if not child["task"].done():
                    child["task"].cancel()

    async def create_children(self):
        """
        Creates child application queues and coroutines.
        """
        loop = asyncio.get_event_loop()
        for stream, child in self.children.items():
            child["queue"] = asyncio.Queue()
            child["task"] = loop.create_task(
                child["instance"](
                    child["queue"].get,
                    functools.partial(self.child_send, stream),
                ),
            )

    async def allow_connection(self):
        """
        Overrideable control point for subclasses to implement custom connect
        authentication.
        """
        return True

    async def broadcast_event(self, event):
        """
        Sends an event to all children.
        """
        for child in self.children.values():
            if not child["task"].done():
                await child["queue"].put(event)

    async def dispatch_event(self, event):
        """
        Dispatches an event to a child.
        """
        # Decode event as a text frame
        if "text" not in event:
            raise ValueError("Multiplexer can only deal with text WebSocket frames")
        data = json.loads(event["text"])
        # Pull out the stream
        stream = data.get("stream", None)
        if not stream:
            raise ValueError("No stream defined in received multiplexer frame")
        # Check payload
        if "payload" not in data:
            raise ValueError("No payload defined in received multiplexer frame")
        # Send to the child
        if stream not in self.children:
            # There is no stream with this name.
            warnings.warn("No stream named %r on this multiplexer" % stream)
            return
        child = self.children[stream]
        if not child["queue"] or child["task"].done():
            warnings.warn("Application for stream %r is not in a receiving state." % stream)
            return
        # If they are not yet accepting, put these events onto a buffer
        event = {
            "type": "websocket.receive",
            "text": json.dumps(data["payload"]),
        }
        if not child["accepting"]:
            child["buffer"].append(event)
        else:
            await child["queue"].put(event)

    async def child_send(self, stream, event):
        """
        Called by children when they want to send something.
        """
        child = self.children[stream]
        # Switch on type.
        if event["type"] == "websocket.accept":
            # They have accepted, so start forwarding them messages
            child["accepting"] = True
            for queued_event in child["buffer"]:
                await child["queue"].put(queued_event)
            child["buffer"] = None
        elif event["type"] == "websocket.close":
            # They want to close, so we remove their queue
            # (their coroutine is allowed to live on)
            child["queue"] = None
            child["buffer"] = None
        elif event["type"] == "websocket.send":
            data = {
                "stream": stream,
                "payload": json.loads(event["text"]),
            }
            await self.send({
                "type": "websocket.send",
                "text": json.dumps(data),
            })
        else:
            raise ValueError("Unknown event type for multiplexer send: %r" % event["type"])
