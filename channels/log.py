import logging
import logging.config

from django.utils.log import DEFAULT_LOGGING
from django.utils.module_loading import import_string


def configure_logging(logging_config, logging_settings):
    """
    Basic logger for runserver etc.
    """

    DEFAULT_LOGGING['formatters'].update({
        'django.channels.server': {
            '()': 'django.utils.log.ServerFormatter',
            'format': '%(asctime)s - %(levelname)s - %(module)s - %(message)s',
        }
    })

    DEFAULT_LOGGING['handlers'].update({
        'django.channels.server': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'django.channels.server',
        }
    })

    DEFAULT_LOGGING['loggers'].update({
        'django.channels.server': {
            'handlers': ['django.channels.server'],
            'level': 'INFO',
            'propagate': False,
        },
        'daphne.ws_protocol': {
            'handlers': ['django.channels.server'],
            'level': 'INFO',
            'propagate': False
        },
        'daphne.http_protocol': {
            'handlers': ['django.channels.server'],
            'level': 'INFO',
            'propagate': False
        },
        'daphne.server': {
            'handlers': ['django.channels.server'],
            'level': 'INFO',
            'propagate': False
        }
    })

    if logging_config:
        # First find the logging configuration function ...
        logging_config_func = import_string(logging_config)

        logging.config.dictConfig(DEFAULT_LOGGING)

        # ... then invoke it with the logging settings
        if logging_settings:
            logging_config_func(logging_settings)
