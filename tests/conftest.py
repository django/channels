import os

import pytest
from django.conf import settings


def pytest_configure():
    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.testproject.settings"
    settings._setup()


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
