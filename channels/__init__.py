__version__ = "2.4.0"

try:
    import django

    if django.VERSION < (3, 2):
        default_app_config = "channels.apps.ChannelsConfig"
except ModuleNotFoundError:
    pass

DEFAULT_CHANNEL_LAYER = "default"
