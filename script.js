// Contact form handler - Sends form data to AWS Lambda
const LAMBDA_URL = 'https://qijmbjbb26uh273zxckc5shfwi0hvtva.lambda-url.us-east-1.on.aws/'; // Replace with your Function URL

// Your WebSocket API configuration from Challenge 6
const WEBSOCKET_URL = 'wss://9x0grhrp7g.execute-api.us-east-1.amazonaws.com/production/';

let socket = null;
let isConnected = false;
let isMinimized = false;
let messageQueue = [];

// WebSocket Connection Management
function connectToWebSocket() {
    try {
        updateConnectionStatus('Connecting...');
        
        // Create WebSocket connection to your existing API Gateway
        socket = new WebSocket(WEBSOCKET_URL);
        
        socket.onopen = () => {
            console.log('Connected to WebSocket API');
            updateConnectionStatus('Connected');
            isConnected = true;
            
            // Process any queued messages
            while (messageQueue.length > 0) {
                const queuedMessage = messageQueue.shift();
                socket.send(JSON.stringify(queuedMessage));
            }
        };
        
        socket.onmessage = (event) => {
            try {
                const response = JSON.parse(event.data);
                console.log('Received:', response);
                
                // Handle different message types from your Challenge 6 API
                if (response.type === 'chunk' && response.content) {
                    displayMessage(response.content, 'assistant');
                    hideTypingIndicator();
                } else if (response.type === 'end') {
                    // Response complete
                    hideTypingIndicator();
                } else if (response.type === 'error') {
                    hideTypingIndicator();
                    displayMessage('Sorry, I encountered an error processing your message.', 'assistant');
                }
            } catch (error) {
                console.error('Error parsing message:', error);
                hideTypingIndicator();
            }
        };
        
        socket.onclose = (evt) => {
            console.log('WebSocket closed:', evt.reason);
            isConnected = false;
            updateConnectionStatus('Disconnected');
            
            // Attempt to reconnect after 3 seconds
            setTimeout(connectToWebSocket, 3000);
        };
        
        socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateConnectionStatus('Error');
            isConnected = false;
        };
        
    } catch (error) {
        console.error('Connection error:', error);
        updateConnectionStatus('Failed');
    }
}

// Chat Interface Functions
function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Display user message immediately
    displayMessage(message, 'user');
    showTypingIndicator();
    
    // Clear input
    input.value = '';
    
    // Prepare message in the format your Challenge 6 Lambda expects
    const messageData = {
        messages: [
            { role: "user", content: message }
        ]
    };
    
    // Send message through WebSocket
    if (isConnected && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(messageData));
    } else {
        // Queue message if not connected
        messageQueue.push(messageData);
        updateConnectionStatus('Reconnecting...');
        connectToWebSocket();
    }
}

function displayMessage(content, role) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    
    messageDiv.className = `message ${role}-message`;
    messageDiv.textContent = content;
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showTypingIndicator() {
    const messagesContainer = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    
    typingDiv.className = 'typing-indicator';
    typingDiv.id = 'typingIndicator';
    typingDiv.textContent = '🤔 Thinking...';
    
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

function updateConnectionStatus(status) {
    const statusElement = document.getElementById('connectionStatus');
    statusElement.textContent = status;
    
    // Add visual indicators
    statusElement.style.color = status === 'Connected' ? '#90EE90' : 
                              status === 'Connecting...' ? '#FFD700' : '#FF6B6B';
}

function toggleChat() {
    const chatContainer = document.getElementById('chatContainer');
    isMinimized = !isMinimized;
    
    if (isMinimized) {
        chatContainer.classList.add('minimized');
    } else {
        chatContainer.classList.remove('minimized');
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

// Initialize connection when page loads
document.addEventListener('DOMContentLoaded', () => {
    connectToWebSocket();
});


document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('.contact-form-container');

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const submitBtn = form.querySelector('.contact-submit-btn');
        const messageDiv = document.getElementById('form-message');

        // Show loading state
        submitBtn.textContent = 'Sending...';
        submitBtn.disabled = true;
        messageDiv.style.display = 'none';

        // Get form data
        const formData = {
            name: form.name.value,
            email: form.email.value,
            message: form.message.value
        };

        try {
            const response = await fetch(LAMBDA_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                showMessage('Message sent successfully! Thank you for reaching out.', 'success');
                form.reset();
            } else {
                showMessage('Failed to send message. Please try again.', 'error');
            }
        } catch (error) {
            showMessage('Network error. Please check your connection and try again.', 'error');
        }

        // Reset button
        submitBtn.textContent = 'Send Message';
        submitBtn.disabled = false;
    });
});

function showMessage(text, type) {
    const messageDiv = document.getElementById('form-message');
    messageDiv.textContent = text;
    messageDiv.className = `form-message ${type}`;
    messageDiv.style.display = 'block';

    // Auto-hide after 10 seconds
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 10000);
}
