import logging
import logging.config

from django.utils.module_loading import import_string

# Default logging for Django. This sends an email to the site admins on every
# HTTP 500 error. Depending on DEBUG, all other log records are either sent to
# the console (DEBUG=True) or discarded (DEBUG=False) by means of the
# require_debug_true filter.
DEFAULT_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
        },
        'django.server': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'channels.server': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'mail_admins'],
            'level': 'INFO',
        },
        'django.server': {
            'handlers': ['django.server'],
            'level': 'INFO',
            'propagate': False,
        },
        'channels.server': {
            'handlers': ['channels.server'],
            'level': 'INFO',
            'propagate': False,
        },
        'daphne.ws_protocol': {
            'handlers': ['channels.server'],
            'level': 'INFO',
            'propagate': False
        },
        'daphne.http_protocol': {
            'handlers': ['channels.server'],
            'level': 'INFO',
            'propagate': False
        },
        'daphne.server': {
            'handlers': ['channels.server'],
            'level': 'INFO',
            'propagate': False
        }
    }
}


def configure_logging(logging_config, logging_settings):
    """
    Basic logger for runserver etc.
    """

    if logging_config:
        # First find the logging configuration function ...
        logging_config_func = import_string(logging_config)

        logging.config.dictConfig(DEFAULT_LOGGING)

        # ... then invoke it with the logging settings
        if logging_settings:
            logging_config_func(logging_settings)
