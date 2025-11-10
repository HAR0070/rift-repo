// Updated script.js — defensive and compatible with updated HTML/CSS

const LAMBDA_URL = 'https://qijmbjbb26uh273zxckc5shfwi0hvtva.lambda-url.us-east-1.on.aws/';
const WEBSOCKET_URL = 'wss://9x0grhrp7g.execute-api.us-east-1.amazonaws.com/production/';

let socket = null;
let isConnected = false;
let messageQueue = [];
let reconnectTimer = null;

function safeGet(id) {
    return document.getElementById(id);
}

function updateConnectionStatus(status) {
    const s = safeGet('connectionStatus');
    if (!s) return;
    s.textContent = status;
    s.style.color = status === 'Connected' ? '#9AE6B4' : (status === 'Connecting...' ? '#FBBF24' : '#F87171');
}

function displayMessage(content, role) {
    const container = safeGet('chatMessages');
    if (!container) return;
    const el = document.createElement('div');
    el.className = `message ${role === 'user' ? 'user-message' : 'assistant-message'}`;
    el.textContent = content;
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
}

function showTypingIndicator() {
    if (safeGet('typingIndicator')) return;
    const container = safeGet('chatMessages');
    if (!container) return;
    const el = document.createElement('div');
    el.id = 'typingIndicator';
    el.className = 'typing-indicator';
    el.textContent = '🤔 Thinking...';
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
}

function hideTypingIndicator() {
    const el = safeGet('typingIndicator');
    if (el) el.remove();
}

function connectToWebSocket() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;

    try {
        updateConnectionStatus('Connecting...');
        socket = new WebSocket(WEBSOCKET_URL);

        socket.onopen = () => {
            isConnected = true;
            updateConnectionStatus('Connected');
            while (messageQueue.length) {
                const msg = messageQueue.shift();
                try { socket.send(JSON.stringify(msg)); } catch (e) { console.warn('send queue failed', e); break; }
            }
            if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        };

        socket.onmessage = (evt) => {
            try {
                const data = JSON.parse(evt.data);
                if (data.type === 'chunk' && data.content) {
                    displayMessage(data.content, 'assistant');
                    hideTypingIndicator();
                } else if (data.type === 'end') {
                    hideTypingIndicator();
                } else if (data.type === 'error') {
                    hideTypingIndicator();
                    displayMessage('Error processing request.', 'assistant');
                } else {
                    // fallback
                    displayMessage(typeof data === 'string' ? data : JSON.stringify(data), 'assistant');
                }
            } catch (err) {
                console.error('Invalid WS message', err);
            }
        };

        socket.onclose = () => {
            isConnected = false;
            updateConnectionStatus('Disconnected');
            if (!reconnectTimer) {
                reconnectTimer = setTimeout(() => { reconnectTimer = null; connectToWebSocket(); }, 3000);
            }
        };

        socket.onerror = (err) => {
            console.error('WS error', err);
            updateConnectionStatus('Error');
            isConnected = false;
        };

    } catch (err) {
        console.error('WS connect failed', err);
        updateConnectionStatus('Failed');
    }
}

function sendMessage() {
    const input = safeGet('chatInput');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;
    displayMessage(text, 'user');
    input.value = '';
    showTypingIndicator();

    const payload = { messages: [{ role: 'user', content: text }] };

    if (socket && socket.readyState === WebSocket.OPEN) {
        try { socket.send(JSON.stringify(payload)); }
        catch (err) { messageQueue.push(payload); connectToWebSocket(); }
    } else {
        messageQueue.push(payload);
        connectToWebSocket();
    }
}

function toggleChat() {
    const container = safeGet('chatContainer');
    if (!container) return;
    container.classList.toggle('minimized');
}

// Enter to send (simple)
function handleKeyPress(e) {
    if (e.key === 'Enter') sendMessage();
}

/* Contact form handling */
document.addEventListener('DOMContentLoaded', () => {
    connectToWebSocket();
    document.addEventListener('keydown', (e) => { if (e.key === 'Enter' && document.activeElement && document.activeElement.id === 'chatInput') { sendMessage(); } });

    const form = document.querySelector('.contact-form-container') || safeGet('contactForm');
    if (form) {
        form.addEventListener('submit', async function (ev) {
            ev.preventDefault();
            const submitBtn = document.querySelector('.contact-submit-btn') || safeGet('contactSubmitBtn');
            if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Sending...'; }

            const nameField = form.querySelector('[name="name"]');
            const emailField = form.querySelector('[name="email"]');
            const messageField = form.querySelector('[name="message"]');

            const payload = {
                name: nameField ? nameField.value : '',
                email: emailField ? emailField.value : '',
                message: messageField ? messageField.value : ''
            };

            try {
                const res = await fetch(LAMBDA_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    showMessage('Message sent successfully!', 'success');
                    form.reset();
                } else {
                    showMessage('Failed to send message.', 'error');
                }
            } catch (err) {
                console.error('Network error', err);
                showMessage('Network error. Try again later.', 'error');
            } finally {
                if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Send Message'; }
            }
        });
    }
});

function showMessage(text, type) {
    const m = safeGet('form-message');
    if (!m) return;
    m.textContent = text;
    m.className = `form-message ${type}`;
    m.style.display = 'block';
    setTimeout(() => { m.style.display = 'none'; }, 9000);
}
