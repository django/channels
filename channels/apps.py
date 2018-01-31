from django.apps import AppConfig
from django.conf import settings

from .binding.base import BindingMetaclass
from .log import configure_logging
from .package_checks import check_all


class ChannelsConfig(AppConfig):

    name = "channels"
    verbose_name = "Channels"

    def ready(self):
        # Check versions
        check_all()
        # Do django monkeypatches
        from .hacks import monkeypatch_django
        monkeypatch_django()
        # Instantiate bindings
        BindingMetaclass.register_all()

        configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)
