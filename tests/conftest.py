import pytest
from django.conf import settings


def pytest_configure():
    settings.configure(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                # Override Django’s default behaviour of using an in-memory database
                # in tests for SQLite, since that avoids connection.close() working.
                "TEST": {"NAME": "test_db.sqlite3"},
            }
        },
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.admin",
            "channels",
        ],
        SECRET_KEY="Not_a_secret_key",
    )


def pytest_generate_tests(metafunc):
    if "samesite" in metafunc.fixturenames:
        metafunc.parametrize("samesite", ["Strict", "None"], indirect=True)


@pytest.fixture
def samesite(request, settings):
    """Set samesite flag to strict."""
    settings.SESSION_COOKIE_SAMESITE = request.param


@pytest.fixture
def samesite_invalid(settings):
    """Set samesite flag to strict."""
    settings.SESSION_COOKIE_SAMESITE = "Hello"
