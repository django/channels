try:
    # We import this here to ensure the reactor is installed very early on
    # in case other packages accidentally import twisted.internet.reactor
    # (e.g. raven does this).
    import daphne.server

    assert daphne.server  # pyflakes doesn't support ignores
    DAPHNE_INSTALLED = True
except ModuleNotFoundError as exc:
    # for CHANNELS_SLIM_INSTALL
    if exc.name != "daphne":
        raise
    DAPHNE_INSTALLED = False

from django.apps import AppConfig


class ChannelsConfig(AppConfig):

    name = "channels"
    verbose_name = "Channels"

    def ready(self):
        if DAPHNE_INSTALLED:
            # Do django monkeypatches
            from .hacks import monkeypatch_django

            monkeypatch_django()
