
## handle rest_framework Token and simplejwt JWT Authentication 

### Only you have to config your asgi.py file like this:

AuthTokenMiddleware class handle this problem.
```
import os
from django.core.asgi import get_asgi_application 
from myapp.routing import ws_urlpatterns
from channels.routing import ProtocolTypeRouter , URLRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from channels.auth import AuthMiddlewareStack
from channels.auth import AuthTokenMiddleware
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(AuthTokenMiddleware(URLRouter(ws_urlpatterns)))
})

```

### in your Consumer class user can extract like this:


```

class CustomConsumer(WebsocketConsumer):

    def connect(self):
        self.accept()
        user = self.scope['user']

```

thanks for your attention!