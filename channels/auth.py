import django
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

if django.VERSION >= (5, 2):

    async def get_user(scope):
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
            backend_path = await session.aget(BACKEND_SESSION_KEY)
        except KeyError:
            pass
        else:
            if backend_path in settings.AUTHENTICATION_BACKENDS:
                backend = load_backend(backend_path)
                user = await backend.aget_user(user_id)
                # Verify the session
                if hasattr(user, "get_session_auth_hash"):
                    session_hash = await session.aget(HASH_SESSION_KEY)
                    session_hash_verified = session_hash and constant_time_compare(
                        session_hash, user.get_session_auth_hash()
                    )
                    if not session_hash_verified:
                        await session.aflush()
                        user = None
        return user or AnonymousUser()

    async def login(scope, user, backend=None):
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
                    await session.aget(HASH_SESSION_KEY, ""), session_auth_hash
                )
            ):
                # To avoid reusing another user's session, create a new, empty
                # session if the existing session corresponds to a different
                # authenticated user.
                await session.aflush()
        else:
            await session.acycle_key()
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
        await session.aset(SESSION_KEY, user._meta.pk.value_to_string(user))
        await session.aset(BACKEND_SESSION_KEY, backend)
        await session.aset(HASH_SESSION_KEY, session_auth_hash)
        scope["user"] = user
        # note this does not reset the CSRF_COOKIE/Token
        await user_logged_in.asend(sender=user.__class__, request=None, user=user)

    async def logout(scope):
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
            await user_logged_out.asend(sender=user.__class__, request=None, user=user)
        await session.aflush()
        if "user" in scope:
            scope["user"] = AnonymousUser()

else:

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
