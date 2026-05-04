(function() {
  const countElement = document.getElementById('messageCount');
  const container = document.getElementById('cardsContainer');
  const titleInput = document.getElementById('msgTitle');
  const textInput = document.getElementById('msgTextArea');
  const sendBtn = document.getElementById('sendBtn');

  const ws = initWebSocket();
  
  function initWebSocket() {
    const wsPath = `ws://${window.location.host}/ws/message/`;
    const socket = new WebSocket(wsPath);

    window.websocketConnected = false;
    window.messageHandled = false;

    socket.onopen = () => {
      window.websocketConnected = true;
      console.log('WebSocket connected');
    };
    socket.onerror = err => console.error('WebSocket Error:', err);
    socket.onclose = () => console.warn('WebSocket closed');
    socket.onmessage = handleMessage;

    return socket;
  }

  function handleMessage(e) {
    const data = JSON.parse(e.data);
    renderState(data.count, data.messages);
    window.messageHandled = true;
  }

  function renderState(count, messages) {
    countElement.textContent = count;
    container.innerHTML = '';
    messages.forEach(msg => container.appendChild(createCard(msg)));
  }

  function createCard({ id, title, message }) {
    const card = document.createElement('div');
    card.className = 'messageCard';

    const h3 = document.createElement('h3');
    h3.textContent = title;

    card.appendChild(h3);

    const p = document.createElement('p');
    p.textContent = message;
    card.appendChild(p);

    const deleteBtn = document.createElement('button');
    deleteBtn.id = 'deleteBtn';
    deleteBtn.textContent = 'Delete';
    deleteBtn.onclick = () => sendAction('delete', { id });
    card.appendChild(deleteBtn);

    return card;
  }

  function sendAction(action, data = {}) {
    const payload = { action, ...data };
    ws.send(JSON.stringify(payload));
  }

  sendBtn.onclick = () => {
  const title   = titleInput.value.trim();
  const message = textInput.value.trim();
  if (!title || !message) {
    return alert('Please enter both title and message.');
  }
  sendAction('create', { title, message });
  titleInput.value = '';
  textInput.value  = '';
};
})();
