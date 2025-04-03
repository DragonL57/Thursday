import { scrollToBottom } from '../utils/dom.js';
import { sendChatMessage } from '../utils/api.js';

export class MessagingComponent {
    constructor(elements) {
        this.userInput = elements.userInput;
        this.sendButton = elements.sendButton;
        this.messageForm = elements.messageForm;
        this.messagesContainer = elements.messagesContainer;
        this.loadingIndicator = elements.loadingIndicator;
        
        this.isProcessing = false;
        
        // Ensure the loading indicator is hidden initially
        this.loadingIndicator.classList.add('hidden');
        
        // Initialize events
        this.initEvents();
    }
    
    initEvents() {
        // Handle form submission
        this.messageForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const message = this.userInput.value.trim();
            if (message) {
                this.sendMessage(message);
            }
        });
    }
    
    // Add message to the UI
    addMessage(content, isUser = false) {
        const messageGroup = document.createElement('div');
        messageGroup.className = isUser ? 'message-group user-message' : 'message-group assistant-message';
        
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        messageGroup.innerHTML = `
            <div class="message-avatar">
                <span class="avatar-icon">${isUser ? '👤' : '💎'}</span>
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-sender">${isUser ? 'You' : 'Gem Assistant'}</span>
                    <span class="message-time">${time}</span>
                </div>
                <div class="message-bubble"></div>
            </div>
        `;
        
        const messageBubble = messageGroup.querySelector('.message-bubble');
        if (isUser) {
            messageBubble.textContent = content;
        } else {
            // Render markdown for assistant messages
            messageBubble.innerHTML = marked.parse(content);
            
            // Render LaTeX within the newly added message
            renderMathInElement(messageBubble, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "$", right: "$", display: false}
                ]
            });
        }
        
        this.messagesContainer.appendChild(messageGroup);
        scrollToBottom(this.messagesContainer);
        
        return messageGroup;
    }
    
    // Send message to API and handle response
    async sendMessage(message) {
        if (this.isProcessing || !message.trim()) return;
        
        // Add user message to UI
        this.addMessage(message, true);
        this.userInput.value = '';
        
        // Trigger input event to adjust textarea height and disable send button
        this.userInput.dispatchEvent(new Event('input'));
        
        // Show loading indicator
        this.isProcessing = true;
        this.loadingIndicator.classList.remove('hidden');
        
        try {
            const data = await sendChatMessage(message);
            
            // Hide loading indicator
            this.loadingIndicator.classList.add('hidden');
            this.isProcessing = false;
            
            if (data.error) {
                this.addMessage(`Error: ${data.error}`);
            } else if (data.response) {
                this.addMessage(data.response);
            } else {
                this.addMessage('Sorry, I received an empty response. Please try again.');
            }
        } catch (error) {
            console.error('Error:', error);
            this.loadingIndicator.classList.add('hidden'); // Ensure it's hidden on error
            this.isProcessing = false;
            this.addMessage(`Sorry, there was an error communicating with the server: ${error.message}`);
        } finally {
            // Additional fallback to ensure the indicator is always hidden after processing
            this.loadingIndicator.classList.add('hidden');
        }
    }
    
    // Clear messages from UI
    clearMessages(keepFirst = true) {
        const firstMessage = this.messagesContainer.firstElementChild;
        this.messagesContainer.innerHTML = '';
        
        if (keepFirst && firstMessage) {
            this.messagesContainer.appendChild(firstMessage);
        }
    }
}
