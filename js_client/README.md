### Usage

Channels WebSocket wrapper.

To process messages:

```js
import { WebSocketBridge } from 'django-channels'

const webSocketBridge = new WebSocketBridge();
webSocketBridge.connect('/ws/');
webSocketBridge.listen(function(payload, stream) {
  console.log(payload, stream);
});
```

To send messages:

```js
webSocketBridge.send({prop1: 'value1', prop2: 'value1'});
```

To demultiplex specific streams:

```js
const webSocketBridge = new WebSocketBridge();
webSocketBridge.connect('/ws/');
webSocketBridge.listen();
webSocketBridge.demultiplex('mystream', function(payload, stream) {
  console.log(payload, stream);
});
webSocketBridge.demultiplex('myotherstream', function(payload, stream) {
  console.info(payload, stream);
});
```

To send a message to a specific stream:

```js
webSocketBridge.stream('mystream').send({prop1: 'value1', prop2: 'value1'})
```

The `WebSocketBridge` instance exposes the underlaying `ReconnectingWebSocket` as the `socket` property. You can use this property to add any custom behavior. For example:

```js
webSocketBridge.socket.addEventListener('open', function() {
    console.log("Connected to WebSocket");
})
```
