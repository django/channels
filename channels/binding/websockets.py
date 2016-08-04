import json

from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder

from .base import Binding
from ..generic.websockets import WebsocketDemultiplexer


class WebsocketBinding(Binding):
    """
    Websocket-specific outgoing binding subclass that uses JSON encoding
    and the built-in JSON/WebSocket multiplexer.

    To implement outbound, implement:
     - group_names, which returns a list of group names to send to

    To implement inbound, implement:
     - has_permission, which says if the user can do the action on an instance

    Optionally also implement:
     - serialize_data, which returns JSON-safe data from a model instance
     - create, which takes incoming data and makes a model instance
     - update, which takes incoming data and a model instance and applies one to the other
    """

    # Mark as abstract

    model = None

    # Stream multiplexing name

    stream = None

    # Outbound
    @classmethod
    def encode(cls, stream, payload):
        return WebsocketDemultiplexer.encode(stream, payload)

    def serialize(self, instance, action):
        payload = {
            "action": action,
            "pk": instance.pk,
            "data": self.serialize_data(instance),
            "model": self.model_label,
        }
        return payload

    def serialize_data(self, instance):
        """
        Serializes model data into JSON-compatible types.
        """
        if self.fields == ['__all__']:
            fields = None
        else:
            fields = self.fields
        data = serializers.serialize('json', [instance], fields=fields)
        return json.loads(data)[0]['fields']

    # Inbound

    def deserialize(self, message):
        """
        You must hook this up behind a Deserializer, so we expect the JSON
        already dealt with.
        """
        action = message['action']
        pk = message.get('pk', None)
        data = message.get('data', None)
        cb_id = message.get('cb_id', None)
        return action, pk, data, cb_id

    def _hydrate(self, pk, data):
        """
        Given a raw "data" section of an incoming message, returns a
        DeserializedObject.
        """
        s_data = [
            {
                "pk": pk,
                "model": self.model_label,
                "fields": data,
            }
        ]
        # TODO: Avoid the JSON roundtrip by using encoder directly?
        return list(serializers.deserialize("json", json.dumps(s_data)))[0]

    def send_reply(self, cb_id, status, details=None):
        text = {"cb_id": cb_id, "status": status}
        if details is not None:
            text["details"] = details
        self.message.reply_channel.send(
            {"text": json.dumps(text, cls=DjangoJSONEncoder)}
        )

    def create(self, data, cb_id):
        self._hydrate(None, data).save()
        self.send_reply(cb_id, "success")

    def update(self, pk, data, cb_id):
        instance = self.model.objects.get(pk=pk)
        hydrated = self._hydrate(pk, data)
        for name in data.keys():
            setattr(instance, name, getattr(hydrated.object, name))
        instance.save()
        self.send_reply(cb_id, "success")

    def delete(self, pk, cb_id):
        super(WebsocketBinding, self).delete(self, pk, cb_id)
        self.send_reply(cb_id, "success")


class WebsocketBindingWithMembers(WebsocketBinding):
    """
    Outgoing binding binding subclass based on WebsocketBinding.
    Additionally enables sending of member variables, properties and methods.
    Member methods can only have self as a required argument.
    Just add the name of the member to the send_members-list.
    Example:

    class MyModel(models.Model):
        my_field = models.IntegerField(default=0)
        my_var = 3

        @property
        def my_property(self):
            return self.my_var + self.my_field

        def my_function(self):
            return self.my_var - self.my_vield

    class MyBinding(BindingWithMembersMixin, WebsocketBinding):
        model = MyModel
        stream = 'mystream'

        send_members = ['my_var', 'my_property', 'my_function']
    """

    model = None
    send_members = []

    encoder = DjangoJSONEncoder()

    def serialize_data(self, instance):
        data = super(WebsocketBindingWithMembers, self).serialize_data(instance)
        for m in self.send_members:
            member = getattr(instance, m)
            if callable(member):
                data[m] = self.encoder.encode(member())
            else:
                data[m] = self.encoder.encode(member)
        return data
