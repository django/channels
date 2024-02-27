import functools
from typing import Type, Dict, Set

from asgiref.sync import async_to_sync
from django.conf import settings

from . import DEFAULT_CHANNEL_LAYER
from .db import database_sync_to_async
from .exceptions import StopConsumer
from .layers import get_channel_layer
from .utils import await_many_dispatch


def get_handler_name(message):
    """
    Looks at a message, checks it has a sensible type, and returns the
    handler name for that type.
    """
    # Check message looks OK
    if "type" not in message:
        raise ValueError("Incoming message has no 'type' attribute")
    # Extract type and replace . with _
    handler_name = message["type"].replace(".", "_")
    if handler_name.startswith("_"):
        raise ValueError("Malformed type in message (leading underscore)")
    return handler_name


def msg_handler(msg_type: str):
    class MsgHandler:
        def __init__(self, func):
            self.func = func

        def __set_name__(self, owner: Type["AsyncConsumer"], name):
            # set the value to the function's name instead of the function itself
            # to allow for the function to be overridden in subclasses without losing the handler functionality
            if msg_type in owner._channels_message_handlers:
                owner._channels_message_handlers[msg_type].add(name)
            else:
                owner._channels_message_handlers[msg_type] = {name}

            setattr(owner, name, self.func)
    return MsgHandler


class ConsumerMeta(type):
    def __new__(mcs, name, bases, attrs):
        cls = super().__new__(mcs, name, bases, attrs)
        if not hasattr(cls, "_channels_message_handlers"):
            cls._channels_message_handlers = {}
        return cls


class AsyncConsumer(metaclass=ConsumerMeta):
    """
    Base consumer class. Implements the ASGI application spec, and adds on
    channel layer management and routing of events to named methods based
    on their type.
    """

    _sync = False
    channel_layer_alias = DEFAULT_CHANNEL_LAYER
    _channels_message_handlers: Dict[str, Set[str]]  # set by metaclass so every class has a new list of handlers

    async def __call__(self, scope, receive, send):
        """
        Dispatches incoming messages to type-based handlers asynchronously.
        """
        self.scope = scope

        # Initialize channel layer
        self.channel_layer = get_channel_layer(self.channel_layer_alias)
        if self.channel_layer is not None:
            self.channel_name = await self.channel_layer.new_channel()
            self.channel_receive = functools.partial(
                self.channel_layer.receive, self.channel_name
            )
        # Store send function
        if self._sync:
            self.base_send = async_to_sync(send)
        else:
            self.base_send = send
        # Pass messages in from channel layer or client to dispatch method
        try:
            if self.channel_layer is not None:
                await await_many_dispatch(
                    [receive, self.channel_receive], self.dispatch
                )
            else:
                await await_many_dispatch([receive], self.dispatch)
        except StopConsumer:
            # Exit cleanly
            pass

    def _get_message_handlers(self, message):
        handlers = self._channels_message_handlers.get(message["type"], [])
        handlers = [getattr(self, handler) for handler in handlers]
        if getattr(settings, "CHANNELS_AUTO_HANDLER_BY_NAME", False):
            # this is only for compatibility with old code / should be removed in the future
            # as this feature SHOULD be deprecated
            handler = getattr(self, get_handler_name(message), None)
            if handler and handler not in handlers:
                # we check for a duplicate in case the setting CHANNELS_AUTO_HANDLER_BY_NAME is enabled in addition to
                # the decorator
                handlers.append(handler)

        if len(handlers) < 1:
            raise ValueError("No handler for message type %s" % message["type"])

        return handlers

    async def dispatch(self, message):
        """
        Works out what to do with a message.
        """
        handlers = self._get_message_handlers(message)
        for handler in handlers:
            await handler(message)

    async def send(self, message):
        """
        Overrideable/callable-by-subclasses send method.
        """
        await self.base_send(message)

    @classmethod
    def as_asgi(cls, **initkwargs):
        """
        Return an ASGI v3 single callable that instantiates a consumer instance
        per scope. Similar in purpose to Django's as_view().

        initkwargs will be used to instantiate the consumer instance.
        """

        async def app(scope, receive, send):
            consumer = cls(**initkwargs)
            return await consumer(scope, receive, send)

        app.consumer_class = cls
        app.consumer_initkwargs = initkwargs

        # take name and docstring from class
        functools.update_wrapper(app, cls, updated=())
        return app


class SyncConsumer(AsyncConsumer):
    """
    Synchronous version of the consumer, which is what we write most of the
    generic consumers against (for now). Calls handlers in a threadpool and
    uses CallBouncer to get the send method out to the main event loop.

    It would have been possible to have "mixed" consumers and auto-detect
    if a handler was awaitable or not, but that would have made the API
    for user-called methods very confusing as there'd be two types of each.
    """

    _sync = True

    @database_sync_to_async
    def dispatch(self, message):
        """
        Dispatches incoming messages to type-based handlers asynchronously.
        """
        handlers = self._get_message_handlers(message)
        for handler in handlers:
            handler(message)

    def send(self, message):
        """
        Overrideable/callable-by-subclasses send method.
        """
        self.base_send(message)
