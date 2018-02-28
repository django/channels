from urllib.parse import urlparse

from django.conf import settings
from django.http.request import validate_host, is_same_domain

from ..generic.websocket import AsyncWebsocketConsumer

from http import client as http_client
import ssl


class OriginValidator:
    """
    Validates that the incoming connection has an Origin header that
    is in an allowed list.

    If full attr is True, any origin from allowed_origins must be scheme://hostname[:port].
    Port is optional, but recommended.
    Check_cert works only with full attr.
    """

    def __init__(self, application, allowed_origins, full=False, check_cert=False):
        self.application = application
        self.allowed_origins = allowed_origins
        # Check state of variable full
        self.full = full
        # Check certificate or not. Works only if full True
        self.check_cert = check_cert if full else False

    def __call__(self, scope):
        # Make sure the scope is of type websocket
        if scope["type"] != "websocket":
            raise ValueError("You cannot use OriginValidator on a non-WebSocket connection")
        # Extract the Origin header
        origin_hostname = None
        result_parse = None
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"origin":
                try:
                    # Set ResultParse and origin hostname
                    result_parse = urlparse(header_value.decode("ascii"))
                    origin_hostname = result_parse.hostname
                except UnicodeDecodeError:
                    pass
        # Check to see if the origin header is valid. Full or default check
        valid = self.valid_origin(origin_hostname) if not self.full else self.valid_origin_full(result_parse)
        if valid:
            # Pass control to the application
            return self.application(scope)
        else:
            # Deny the connection
            return WebsocketDenier(scope)

    def valid_origin(self, origin):
        # None is not allowed
        if origin is None:
            return False
        # Get only hostname all allowed origins
        # Only if not full: https://domain.example.com:8443 -> domain.example.com
        #   or //domain.example.com - > domain.example.com
        #   or .example.com -> .example.com
        self.allowed_origins = [urlparse(pattern).hostname or urlparse("//" + pattern).hostname
                                or pattern for pattern in self.allowed_origins]
        # Check against our list
        return validate_host(origin, self.allowed_origins)

    def valid_origin_full(self, origin):
        # None is not allowed
        if origin is None:
            return False
        # Check against our list
        return self.validate_host_full(origin)

    def validate_host_full(self, origin):
        # Return True if valid, False otherwise
        return any(pattern == '*' or self.is_allowed_origin(origin, pattern)
                   for pattern in self.allowed_origins)

    def is_allowed_origin(self, origin, pattern):
        checked_address = 0
        # Get ResultParse object
        pattern = urlparse(pattern.lower())
        # Get check result and origin ports
        valid, origin_ports = self.check_pattern(origin, pattern)
        if valid:
            # Check ssl security certificate
            if origin.scheme == 'https' and self.check_cert:
                for port in origin_ports:
                    try:
                        # Init HTTPSConnection object
                        client = http_client.HTTPSConnection(origin.hostname, port)
                        # Requesting a site with get method
                        client.request('get', origin.hostname + origin.path)
                        checked_address += 1
                    # Except error: security certificate is invalid
                    except (ssl.SSLError, ConnectionRefusedError) as error:
                        # Check error
                        if isinstance(error, ConnectionRefusedError):
                            continue
                        # Raise ssl.SSLError
                        raise ssl.SSLError(origin.geturl() + " uses an invalid security certificate.")
                if not checked_address:
                    # Raise error, if all addresses are not available
                    raise ConnectionRefusedError("Can not connect to at least one address.")
            return True
        return False

    def get_origin_ports(self, origin):
        if origin.port is not None:
            # Return tuple (origin.port, )
            return origin.port,
        # if origin.port doesn`t exists
        if origin.scheme == 'http':
            # Default ports return for http
            return 80, 8080
        elif origin.scheme == 'https':
            # Default ports return for https
            return 443, 8443
        else:
            return None

    def check_pattern(self, origin, pattern):
        # Get origin.port or default ports for origin or None
        origin_ports = self.get_origin_ports(origin)
        # Get pattern.port or default ports for pattern or None
        pattern_ports = self.get_origin_ports(pattern)
        # Get valid origin ports or empty list
        if origin_ports and pattern_ports:
            valid_origin_ports = [origin_ports[i] for i in range(0, len(origin_ports))
                                  if origin_ports[i] in pattern_ports]
        else:
            valid_origin_ports = []
        # Compares hostname, scheme, ports of pattern and origin
        # Return tuple. Values: (True/False, valid_origin_ports)
        return all((pattern.scheme == origin.scheme,
                    is_same_domain(origin.hostname, pattern.hostname),
                    len(valid_origin_ports) > 0,
                    )), valid_origin_ports


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
