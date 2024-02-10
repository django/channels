from django.conf import settings
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    HASH_SESSION_KEY,
    SESSION_KEY,
    _get_backends,
    get_user_model,
    load_backend,
    user_logged_in,
    user_logged_out,
)
from django.utils.crypto import constant_time_compare
from django.utils.functional import LazyObject

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from channels.sessions import CookieMiddleware, SessionMiddleware
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
import re
from django.conf import settings
import jwt
from datetime import datetime
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
User = get_user_model()
@database_sync_to_async
def get_user(scope):
    """
    Return the user model instance associated with the given scope.
    If no user is retrieved, return an instance of `AnonymousUser`.
    """
    # postpone model import to avoid ImproperlyConfigured error before Django
    # setup is complete.
    from django.contrib.auth.models import AnonymousUser

    if "session" not in scope:
        raise ValueError(
            "Cannot find session in scope. You should wrap your consumer in "
            "SessionMiddleware."
        )
    session = scope["session"]
    user = None
    try:
        user_id = _get_user_session_key(session)
        backend_path = session[BACKEND_SESSION_KEY]
    except KeyError:
        pass
    else:
        if backend_path in settings.AUTHENTICATION_BACKENDS:
            backend = load_backend(backend_path)
            user = backend.get_user(user_id)
            # Verify the session
            if hasattr(user, "get_session_auth_hash"):
                session_hash = session.get(HASH_SESSION_KEY)
                session_hash_verified = session_hash and constant_time_compare(
                    session_hash, user.get_session_auth_hash()
                )
                if not session_hash_verified:
                    session.flush()
                    user = None
    return user or AnonymousUser()


@database_sync_to_async
def login(scope, user, backend=None):
    """
    Persist a user id and a backend in the request.
    This way a user doesn't have to re-authenticate on every request.
    Note that data set during the anonymous session is retained when the user
    logs in.
    """
    if "session" not in scope:
        raise ValueError(
            "Cannot find session in scope. You should wrap your consumer in "
            "SessionMiddleware."
        )
    session = scope["session"]
    session_auth_hash = ""
    if user is None:
        user = scope.get("user", None)
    if user is None:
        raise ValueError(
            "User must be passed as an argument or must be present in the scope."
        )
    if hasattr(user, "get_session_auth_hash"):
        session_auth_hash = user.get_session_auth_hash()
    if SESSION_KEY in session:
        if _get_user_session_key(session) != user.pk or (
            session_auth_hash
            and not constant_time_compare(
                session.get(HASH_SESSION_KEY, ""), session_auth_hash
            )
        ):
            # To avoid reusing another user's session, create a new, empty
            # session if the existing session corresponds to a different
            # authenticated user.
            session.flush()
    else:
        session.cycle_key()
    try:
        backend = backend or user.backend
    except AttributeError:
        backends = _get_backends(return_tuples=True)
        if len(backends) == 1:
            _, backend = backends[0]
        else:
            raise ValueError(
                "You have multiple authentication backends configured and "
                "therefore must provide the `backend` "
                "argument or set the `backend` attribute on the user."
            )
    session[SESSION_KEY] = user._meta.pk.value_to_string(user)
    session[BACKEND_SESSION_KEY] = backend
    session[HASH_SESSION_KEY] = session_auth_hash
    scope["user"] = user
    # note this does not reset the CSRF_COOKIE/Token
    user_logged_in.send(sender=user.__class__, request=None, user=user)


@database_sync_to_async
def logout(scope):
    """
    Remove the authenticated user's ID from the request and flush their session
    data.
    """
    # postpone model import to avoid ImproperlyConfigured error before Django
    # setup is complete.
    from django.contrib.auth.models import AnonymousUser

    if "session" not in scope:
        raise ValueError(
            "Login cannot find session in scope. You should wrap your "
            "consumer in SessionMiddleware."
        )
    session = scope["session"]
    # Dispatch the signal before the user is logged out so the receivers have a
    # chance to find out *who* logged out.
    user = scope.get("user", None)
    if hasattr(user, "is_authenticated") and not user.is_authenticated:
        user = None
    if user is not None:
        user_logged_out.send(sender=user.__class__, request=None, user=user)
    session.flush()
    if "user" in scope:
        scope["user"] = AnonymousUser()


def _get_user_session_key(session):
    # This value in the session is always serialized to a string, so we need
    # to convert it back to Python whenever we access it.
    return get_user_model()._meta.pk.to_python(session[SESSION_KEY])


class UserLazyObject(LazyObject):
    """
    Throw a more useful error message when scope['user'] is accessed before
    it's resolved
    """

    def _setup(self):
        raise ValueError("Accessing scope user before it is ready.")


class AuthMiddleware(BaseMiddleware):
    """
    Middleware which populates scope["user"] from a Django session.
    Requires SessionMiddleware to function.
    """

    def populate_scope(self, scope):
        # Make sure we have a session
        if "session" not in scope:
            raise ValueError(
                "AuthMiddleware cannot find session in scope. "
                "SessionMiddleware must be above it."
            )
        # Add it to the scope if it's not there already
        if "user" not in scope:
            scope["user"] = UserLazyObject()

    async def resolve_scope(self, scope):
        scope["user"]._wrapped = await get_user(scope)

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        # Scope injection/mutation per this middleware's needs.
        self.populate_scope(scope)
        # Grab the finalized/resolved scope
        await self.resolve_scope(scope)

        return await super().__call__(scope, receive, send)


# Handy shortcut for applying all three layers at once
def AuthMiddlewareStack(inner):
    return CookieMiddleware(SessionMiddleware(AuthMiddleware(inner)))


class AuthTokenMiddleware(BaseMiddleware):

    async def __call__(self, scope, receive, send):
        # Extract access token from headers
        headers = dict(scope['headers'])
        if b'authorization' in headers.keys(): 
            authorization_header = headers[b'authorization']
            if not authorization_header:
                # No access token found
                scope['user'] = AnonymousUser()
            else:
                authorization_header = authorization_header.decode('utf-8')
                bearer = re.findall(r'^\s*Bearer\s+',authorization_header)
                token = re.findall(r'^\s*Token\s+',authorization_header)
                if bearer:
                    bearer = bearer[0]
                    access_token = authorization_header.split(bearer)[1]
                    scope['user'] = await self.get_user_from_jwt(access_token=access_token)
                elif token:
                    token = token[0]
                    token_key = authorization_header.split(token)[1]
                    scope['user'] = await self.get_user_from_token(key=token_key)
        else: scope['user'] = AnonymousUser()


        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_jwt(self, access_token):
        try:
            # Decode JWT token and get user
            decoded_token = jwt.decode(access_token, settings.SECRET_KEY, algorithms=['HS256'])
            if 'exp' not in decoded_token or datetime.utcfromtimestamp(decoded_token['exp']) < datetime.now():
                return AnonymousUser()
            user_id = decoded_token["user_id"]
            user = User.objects.get(id = user_id)
            return user
        except :
            return AnonymousUser()

    @database_sync_to_async
    def get_user_from_token(self, key):
        try:
            # Decode token and get user
            token = Token.objects.get(key=key)
            return token.user
        except :
            return AnonymousUser()
