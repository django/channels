import ssl, socket
from http import client as http_client
from urllib.parse import urlparse

from django.conf import settings
from django.http.request import is_same_domain, validate_host

from ..generic.websocket import AsyncWebsocketConsumer


class OriginValidator:
    """
    Validates that the incoming connection has an Origin header that
    is in an allowed list.
    """

    def __init__(self, application, allowed_origins):
        self.application = application
        self.allowed_origins = allowed_origins

    def __call__(self, scope):
        # Make sure the scope is of type websocket
        if scope["type"] != "websocket":
            raise ValueError("You cannot use OriginValidator on a non-WebSocket connection")
        # Extract the Origin header
        parsed_origin = None
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"origin":
                try:
                    # Set ResultParse
                    parsed_origin = urlparse(header_value.decode("ascii"))
                except UnicodeDecodeError:
                    pass
        # Check to see if the origin header is valid
        if self.valid_origin(parsed_origin):
            # Pass control to the application
            return self.application(scope)
        else:
            # Deny the connection
            return WebsocketDenier(scope)

    def valid_origin(self, parsed_origin):
        """
        Checks parsed origin is None.

        Pass control to the validate_origin function.

        Returns ``True`` if validation function was successful, ``False`` otherwise.
        """
        # None is not allowed
        if parsed_origin is None:
            return False
        return self.validate_origin(parsed_origin)

    def validate_origin(self, origin):
        """
        Validate the given origin for this site.

        Check than the origin looks valid and matches the origin pattern in
        specified list `` allowed_origins``. Any pattern begins with a scheme.
        After the scheme there must be a domain. Any domain beginning with a period
        corresponds to the domain and all its subdomains (for example, ``http://.example.com``
        ``http://example.com`` and any subdomain).After the domain there must be a port,
        but it can be omitted. `` * `` matches anything and anything
        else must match exactly.

        Note. This function assumes that the given origin has a schema, domain and port,
        but port is optional.

        Returns `` True`` for a valid host, `` False`` otherwise.
        """
        return any(
            pattern == "*" or self.is_allowed_origin(origin, pattern)
            for pattern in self.allowed_origins
        )

    def is_allowed_origin(self, origin, pattern):
        """
        Returns ``True`` if the origin is either an exact match or a match
        to the wildcard pattern. Compares scheme, domain, port of origin and pattern.

        Any pattern can be begins with a scheme. After the scheme must be a domain,
        or just domain without scheme.
        Any domain beginning with a period corresponds to the domain and all
        its subdomains (for example, ``.example.com`` ``example.com``
        and any subdomain). Also with scheme (for example, ``http://.example.com``
        ``http://exapmple.com``). After the domain there must be a port,
        but it can be omitted.

        Also, if scheme is ``https``, verifies security certificate.

        Note. This function assumes that the given origin has a schema, domain and port,
        or only domain. Port is optional.

        Raises SSLError if origin used an invalid security certificate.

        Raises ConnectionRefusedError if the connection is rejected.
        Occurs when connected to a port that is not listening.

        Raises socket.gaierror if name or service not known.
        """
        # Get ResultParse object
        parsed_pattern = urlparse(pattern.lower(), scheme=None)
        if parsed_pattern.scheme is None:
            pattern_hostname = urlparse("//" + pattern).hostname or pattern
            return is_same_domain(origin.hostname, pattern_hostname)
        # Get origin.port or default ports for origin or None
        origin_port = self.get_origin_port(origin)
        # Get pattern.port or default ports for pattern or None
        pattern_port = self.get_origin_port(parsed_pattern)
        # Compares hostname, scheme, ports of pattern and origin
        if parsed_pattern.scheme == origin.scheme and origin_port == pattern_port \
                and is_same_domain(origin.hostname, parsed_pattern.hostname):
            # Check ssl security certificate
            if origin.scheme == "https":
                try:
                    # Init HTTPSConnection object
                    http_client.HTTPSConnection(origin.hostname, port=origin_port, timeout=5).connect()
                # Except error: security certificate is invalid
                except (ssl.SSLError, socket.gaierror, ConnectionRefusedError) as error:
                    # Raise Connection error
                    if isinstance(error, ConnectionRefusedError):
                        address = origin.geturl()
                        raise ConnectionRefusedError("Can not connect to " + address + " address.")
                    # Raise, if name or service not known
                    elif isinstance(error, socket.gaierror):
                        # Uncomment this string, if try to listen port. But include
                        raise socket.gaierror(
                            "Address: " + origin.geturl() + ". Port: " + str(origin_port) +
                            ". Name or service not known."
                        )
                    # Raise ssl.SSLError
                    raise ssl.SSLError(origin.geturl() + " uses an invalid security certificate.")
            return True
        return False

    def get_origin_port(self, origin):
        """
        Returns the origin.port or port for this schema by default.
        Otherwise, it returns None.
        """
        if origin.port is not None:
            # Return origin.port
            return origin.port
        # if origin.port doesn`t exists
        if origin.scheme == "http" or origin.scheme == "ws":
            # Default port return for http
            return 80
        elif origin.scheme == "https" or origin.scheme == "wss":
            # Default port return for https
            return 443
        else:
            return None


def AllowedHostsOriginValidator(application):
    """
    Factory function which returns an OriginValidator configured to use
    settings.ALLOWED_HOSTS.
    """
    allowed_hosts = settings.ALLOWED_HOSTS
    if settings.DEBUG and not allowed_hosts:
        allowed_hosts = ["localhost", "127.0.0.1", "[::1]"]
    return OriginValidator(application, allowed_hosts)


class WebsocketDenier(AsyncWebsocketConsumer):
    """
    Simple application which denies all requests to it.
    """

    async def connect(self):
        await self.close()
