import os

from django.conf import settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def pytest_configure():
    settings.configure(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "TEST": {
                    # We can't use an in-memory database because the
                    # communicators use the ORM
                    "NAME": os.path.join(BASE_DIR, "db_test.sqlite3"),
                },
            }
        },
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.admin",
            "channels",
        ],
    )
