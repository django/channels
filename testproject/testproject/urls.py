from django.conf.urls import  url


urlpatterns = [
    url(r'^$', views.index),
]


try:
    from chtest import consumers, views
    channel_routing = {
    "websocket.receive": consumers.ws_message,
    "websocket.connect": consumers.ws_connect,
}
except:
    pass
