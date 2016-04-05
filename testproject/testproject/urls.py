from django.conf.urls import url
from chtest import consumers, views


urlpatterns = [
    url(r'^$', views.websocket_test),
    url(r'^plain-text/$', views.plain_text),
]


channel_routing = {
    "websocket.receive": consumers.ws_message,
    "websocket.connect": consumers.ws_connect,
}
