from contextlib import contextmanager
from importlib import import_module
from unittest import mock

from django.conf import settings
from django.contrib.auth import (
    BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model, user_logged_in, user_logged_out,
)
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from channels.auth import get_user, login, logout


@contextmanager
def catch_signal(signal):
    """Catch django signal and return the mocked call."""
    handler = mock.Mock()
    signal.connect(handler)
    yield handler
    signal.disconnect(handler)


class LoginLogoutTests(TransactionTestCase):

    def setUp(self):
        self.SessionStore = import_module(settings.SESSION_ENGINE).SessionStore
        self.session = self.SessionStore()  # type: SessionBase
        self.session.create()
        self.user = get_user_model().objects.create(
            username="bob",
            email="bob@example.com"
        )  # type: AbstractUser

        self.user2 = get_user_model().objects.create(
            username="bil",
            email="bill@example.com"
        )  # type: AbstractUser

    def test_no_session_in_scope(self):

        with self.assertRaises(ValueError) as cm:
            login(scope={}, user=None)

        exc = cm.exception
        self.assertEqual(str(exc), "Cannot find session in scope. "
                                   "You should wrap your consumer in "
                                   "SessionMiddleware.")

    def test_no_user_no_user_in_scope(self):
        scope = {
            "session": self.session
        }

        with self.assertRaises(ValueError) as cm:
            login(scope, user=None)

        exc = cm.exception
        self.assertEqual(str(exc),
                         "User must be passed as an argument or must be "
                         "present in the scope.")

    def assertIsLoggedIn(self, scope, user):
        assert "user" in scope
        assert scope["user"] == user
        session = scope["session"]

        # logged in!
        assert SESSION_KEY in session
        assert BACKEND_SESSION_KEY in session
        assert HASH_SESSION_KEY in session

        self.assertIsInstance(get_user(scope), get_user_model())
        assert get_user(scope) == user

    def test_login_user_as_argument(self):
        scope = {
            "session": self.session
        }

        self.assertIsInstance(get_user(scope), AnonymousUser)
        # not logged in
        assert SESSION_KEY not in self.session

        with catch_signal(user_logged_in) as handler:
            assert not handler.called
            login(scope, user=self.user)
            assert handler.called

        self.assertIsLoggedIn(scope, self.user)

    def test_login_user_on_scope(self):
        scope = {
            "session": self.session,
            "user": self.user
        }

        # check that we are not logged in on the session
        self.assertIsInstance(get_user(scope), AnonymousUser)

        with catch_signal(user_logged_in) as handler:
            assert not handler.called
            login(scope, user=None)
            assert handler.called

        self.assertIsLoggedIn(scope, self.user)

    def test_change_user(self):
        scope = {
            "session": self.session,
        }

        # check that we are not logged in on the session
        self.assertIsInstance(get_user(scope), AnonymousUser)

        with catch_signal(user_logged_in) as handler:
            assert not handler.called
            login(scope, user=self.user)
            assert handler.called

        self.assertIsLoggedIn(scope, self.user)

        session_key = self.session[SESSION_KEY]
        assert session_key

        with catch_signal(user_logged_in) as handler:
            assert not handler.called
            login(scope, user=self.user2)
            assert handler.called

        self.assertIsLoggedIn(scope, self.user2)

        assert session_key != self.session[SESSION_KEY]

    def test_logout(self):
        scope = {
            "session": self.session,
        }

        # check that we are not logged in on the session
        self.assertIsInstance(get_user(scope), AnonymousUser)

        with catch_signal(user_logged_in) as handler:
            assert not handler.called
            login(scope, user=self.user)
            assert handler.called

        self.assertIsLoggedIn(scope, self.user)

        assert SESSION_KEY in self.session
        session_key = self.session[SESSION_KEY]
        assert session_key

        with catch_signal(user_logged_out) as handler:
            assert not handler.called
            logout(scope)
            assert handler.called

        self.assertIsInstance(get_user(scope), AnonymousUser)
        self.assertIsInstance(scope["user"], AnonymousUser)

        assert SESSION_KEY not in self.session

    def test_logout_not_logged_in(self):
        scope = {
            "session": self.session,
        }

        # check that we are not logged in on the session
        self.assertIsInstance(get_user(scope), AnonymousUser)

        with catch_signal(user_logged_out) as handler:
            assert not handler.called
            logout(scope)
            assert not handler.called

        assert "user" not in scope
        self.assertIsInstance(get_user(scope), AnonymousUser)
