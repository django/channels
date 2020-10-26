import django

__version__ = "2.4.0"

if django.VERSION < (3, 2):
    default_app_config = "channels.apps.ChannelsConfig"
DEFAULT_CHANNEL_LAYER = "default"
