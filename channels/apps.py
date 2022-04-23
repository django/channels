import sys

if (
    len(sys.argv) >= 2
    and sys.argv[0].endswith("manage.py")
    and sys.argv[1] == "runserver"
) or sys.argv[0].endswith("daphne"):
    # We import this here to ensure the reactor is installed very early on
    # in case other packages accidentally import twisted.internet.reactor
    # (e.g. raven does this).
    import daphne.server

    assert daphne.server  # pyflakes doesn't support ignores

from django.apps import AppConfig


class ChannelsConfig(AppConfig):

    name = "channels"
    verbose_name = "Channels"

    def ready(self):
        # Do django monkeypatches
        from .hacks import monkeypatch_django

        monkeypatch_django()
