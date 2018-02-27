from importlib import import_module
from unittest import mock

import pytest
from django.conf import settings
from django.contrib.auth import (
    BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model, user_logged_in, user_logged_out,
)
from django.contrib.auth.models import AnonymousUser

from asgiref.sync import sync_to_async
from channels.auth import get_user, login, logout
from channels.db import database_sync_to_async


class catch_signal():
    def __init__(self, signal):
        self.handler = mock.Mock()
        self.signal = signal

    async def __aenter__(self):
        await sync_to_async(self.signal.connect)(self.handler)
        return self.handler

    async def __aexit__(self, exc_type, exc, tb):
        await sync_to_async(self.signal.disconnect)(self.handler)


@pytest.fixture
def user_bob():
    return get_user_model().objects.create(username="bob", email="bob@example.com")


@pytest.fixture
def user_bill():
    return get_user_model().objects.create(username="bill", email="bill@example.com")


@pytest.fixture
def session():
    SessionStore = import_module(settings.SESSION_ENGINE).SessionStore
    session = SessionStore()
    session.create()
    return session


async def assert_is_logged_in(scope, user):
    assert "user" in scope
    assert scope["user"] == user
    session = scope["session"]

    # logged in!
    assert SESSION_KEY in session
    assert BACKEND_SESSION_KEY in session
    assert HASH_SESSION_KEY in session

    assert isinstance(await get_user(scope), await database_sync_to_async(get_user_model)())
    assert await get_user(scope) == user


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_login_no_session_in_scope():

    with pytest.raises(
            ValueError,
            match="Cannot find session in scope. You should wrap your consumer in SessionMiddleware."):
        await login(scope={}, user=None)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_login_no_user_in_scope(session):
    scope = {
        "session": session
    }

    with pytest.raises(ValueError, match="User must be passed as an argument or must be present in the scope."):
        await login(scope, user=None)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_login_user_as_argument(session, user_bob):
    scope = {
        "session": session
    }

    assert isinstance(await get_user(scope), AnonymousUser)
    # not logged in
    assert SESSION_KEY not in session

    async with catch_signal(user_logged_in) as handler:
        assert not handler.called
        await login(scope, user=user_bob)
        assert handler.called

    await assert_is_logged_in(scope, user_bob)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_login_user_on_scope(session, user_bob):
    scope = {
        "session": session,
        "user": user_bob
    }

    # check that we are not logged in on the session
    assert isinstance(await get_user(scope), AnonymousUser)

    async with catch_signal(user_logged_in) as handler:
        assert not handler.called
        await login(scope, user=None)
        assert handler.called

    await assert_is_logged_in(scope, user_bob)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_login_change_user(session, user_bob, user_bill):
    scope = {
        "session": session,
    }

    # check that we are not logged in on the session
    assert isinstance(await get_user(scope), AnonymousUser)

    async with catch_signal(user_logged_in) as handler:
        assert not handler.called
        await login(scope, user=user_bob)
        assert handler.called

    await assert_is_logged_in(scope, user_bob)

    session_key = session[SESSION_KEY]
    assert session_key

    async with catch_signal(user_logged_in) as handler:
        assert not handler.called
        await login(scope, user=user_bill)
        assert handler.called

    await assert_is_logged_in(scope, user_bill)

    assert session_key != session[SESSION_KEY]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_logout(session, user_bob):
    scope = {
        "session": session,
    }

    # check that we are not logged in on the session
    assert isinstance(await get_user(scope), AnonymousUser)

    async with catch_signal(user_logged_in) as handler:
        assert not handler.called
        await login(scope, user=user_bob)
        assert handler.called

    await assert_is_logged_in(scope, user_bob)

    assert SESSION_KEY in session
    session_key = session[SESSION_KEY]
    assert session_key

    async with catch_signal(user_logged_out) as handler:
        assert not handler.called
        await logout(scope)
        assert handler.called

    assert isinstance(await get_user(scope), AnonymousUser)
    assert isinstance(scope["user"], AnonymousUser)

    assert SESSION_KEY not in session


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_logout_not_logged_in(session):
    scope = {
        "session": session,
    }

    # check that we are not logged in on the session
    assert isinstance(await get_user(scope), AnonymousUser)

    async with catch_signal(user_logged_out) as handler:
        assert not handler.called
        await logout(scope)
        assert not handler.called

    assert "user" not in scope
    assert isinstance(await get_user(scope), AnonymousUser)
