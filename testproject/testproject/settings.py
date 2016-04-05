# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = '-3yt98bfvxe)7+^h#(@8k#1(1m_fpd9x3q2wolfbf^!r5ma62u'

DEBUG = True

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'channels',
    'chtest',
)

ROOT_URLCONF = 'testproject.urls'

WSGI_APPLICATION = 'testproject.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
    },
]

STATIC_URL = "/static/"

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "asgiref.inmemory.ChannelLayer",
        "ROUTING": "testproject.urls.channel_routing",
        # Use this for Redis testing
        # "BACKEND": "asgi_redis.RedisChannelLayer",
        # "CONFIG": {
        #     "hosts": [os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379')],
        # }
    },
}
