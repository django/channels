from django.urls import Resolver404


class RequestAborted(Exception):
    """
    Raised when the incoming request tells us it's aborted partway through
    reading the body.
    """

    pass


class RequestTimeout(RequestAborted):
    """
    Aborted specifically due to timeout.
    """

    pass


class InvalidChannelLayerError(ValueError):
    """
    Raised when a channel layer is configured incorrectly.
    """

    pass


class AcceptConnection(Exception):
    """
    Raised during a websocket.connect (or other supported connection) handler
    to accept the connection.
    """

    pass


class DenyConnection(Exception):
    """
    Raised during a websocket.connect (or other supported connection) handler
    to deny the connection.
    """

    pass


class ChannelFull(Exception):
    """
    Raised when a channel cannot be sent to as it is over capacity.
    """

    pass


class MessageTooLarge(Exception):
    """
    Raised when a message cannot be sent as it's too big.
    """

    pass


class StopConsumer(Exception):
    """
    Raised when a consumer wants to stop and close down its application instance.
    """

    pass


class RouterResolver404(Resolver404, ValueError):
    """
    Raised when a router cannot resolve a path.
    Backwards compatible, in future ValueError will be deprecated in favor of Resolver404
    """

    pass
