import { sendChatMessage } from '../utils/api.js';
import { adjustTextareaHeight, scrollToBottom } from '../utils/dom.js';

export class MessagingComponent {
    constructor(elements) {
        this.userInput = elements.userInput;
        this.sendButton = elements.sendButton;
        this.messagesContainer = elements.messagesContainer;
        this.messageForm = elements.messageForm;
        this.loadingIndicator = elements.loadingIndicator;
        this.isProcessing = false;
        
        this.initEvents();
    }
    
    initEvents() {
        this.messageForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const message = this.userInput.value.trim();
            if (message && !this.isProcessing) {
                await this.sendMessage(message);
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
    
    // Add a tool call as a separate message (compact version)
    addToolCallMessage(toolCall) {
        const messageGroup = document.createElement('div');
        messageGroup.className = 'message-group tool-message compact';
        
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        // Parse the arguments
        let args;
        try {
            args = JSON.parse(toolCall.args);
            // Convert args to a more readable string format
            args = Object.entries(args)
                .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
                .join(', ');
        } catch (e) {
            args = toolCall.args;
        }
        
        // Check if result exists and determine if it's a single line
        let resultClass = !toolCall.result ? 'hidden' : '';
        if (toolCall.result && !toolCall.result.includes('\n')) {
            resultClass += ' single-line';
        }
        
        messageGroup.innerHTML = `
            <div class="message-avatar">
                <span class="avatar-icon">🔧</span>
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-sender">${toolCall.name}</span>
                    <span class="tool-status-indicator ${toolCall.status}" title="${toolCall.status}"></span>
                    <span class="message-time">${time}</span>
                </div>
                <div class="message-bubble tool-message-bubble" data-tool-id="tool-call-${toolCall.id}">
                    <div class="tool-execution">
                        <div class="tool-command">
                            <code>${toolCall.name}(${args})</code>
                        </div>
                        <div class="tool-result ${resultClass}">
                            <pre><code>${toolCall.result || ''}</code></pre>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        this.messagesContainer.appendChild(messageGroup);
        
        // Apply syntax highlighting
        messageGroup.querySelectorAll('pre code, .tool-command code').forEach((block) => {
            hljs.highlightElement(block);
        });
        
        scrollToBottom(this.messagesContainer);
        
        return messageGroup;
    }
    
    // Create a tool call element (for compatibility with existing code)
    createToolCallElement(toolCall) {
        const toolCallElement = document.createElement('div');
        toolCallElement.className = `tool-call ${toolCall.status}`;
        toolCallElement.id = `tool-call-${toolCall.id}`;
        
        // Parse the arguments to display them nicely
        let args;
        try {
            args = JSON.parse(toolCall.args);
        } catch (e) {
            args = toolCall.args;
        }
        
        const argsFormatted = JSON.stringify(args, null, 2);
        
        toolCallElement.innerHTML = `
            <div class="tool-call-header">
                <span class="tool-call-icon">🔧</span>
                <span class="tool-call-name">${toolCall.name}</span>
                <span class="tool-call-status">${toolCall.status}</span>
            </div>
            <div class="tool-call-body">
                <div class="tool-call-args">
                    <pre><code class="language-json">${argsFormatted}</code></pre>
                </div>
                <div class="tool-call-result ${toolCall.result ? '' : 'hidden'}">
                    <div class="tool-call-result-header">Result:</div>
                    <pre><code>${toolCall.result || ''}</code></pre>
                </div>
            </div>
        `;
        
        return toolCallElement;
    }
    
    // Update tool call status and result
    updateToolCall(toolCall) {
        // Update the tool call message if it exists
        const toolCallId = `tool-call-${toolCall.id}`;
        const toolMessage = document.querySelector(`.tool-message .message-bubble[data-tool-id="${toolCallId}"]`);
        
        if (toolMessage) {
            const statusIndicator = toolMessage.closest('.message-content').querySelector('.tool-status-indicator');
            if (statusIndicator) {
                statusIndicator.className = `tool-status-indicator ${toolCall.status}`;
                statusIndicator.title = toolCall.status;
            }
            
            const resultElement = toolMessage.querySelector('.tool-result');
            if (resultElement && toolCall.result) {
                resultElement.classList.remove('hidden');
                
                // Add single-line class if result is a single line
                if (!toolCall.result.includes('\n')) {
                    resultElement.classList.add('single-line');
                }
                
                resultElement.querySelector('pre code').textContent = toolCall.result;
                
                // Highlight the result code
                hljs.highlightElement(resultElement.querySelector('pre code'));
            }
        } else {
            // If no dedicated tool message exists (old format), update the embedded tool call
            const toolCallElement = document.getElementById(toolCallId);
            if (toolCallElement) {
                toolCallElement.className = `tool-call ${toolCall.status}`;
                toolCallElement.querySelector('.tool-call-status').textContent = toolCall.status;
                
                const resultElement = toolCallElement.querySelector('.tool-call-result');
                if (toolCall.result) {
                    resultElement.classList.remove('hidden');
                    
                    // Add single-line class if result is a single line
                    if (!toolCall.result.includes('\n')) {
                        resultElement.classList.add('single-line');
                    }
                    
                    resultElement.querySelector('pre code').textContent = toolCall.result;
                    
                    // Highlight the result code
                    hljs.highlightElement(resultElement.querySelector('pre code'));
                }
            }
        }
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
            } else {
                // First add tool calls as separate messages if they exist
                if (data.tool_calls && data.tool_calls.length > 0) {
                    // Add each tool call as its own message before the assistant response
                    data.tool_calls.forEach(toolCall => {
                        this.addToolCallMessage(toolCall);
                    });
                }
                
                // Then add the assistant's text response
                if (data.response) {
                    this.addMessage(data.response, false);
                } else {
                    this.addMessage('Sorry, I received an empty response. Please try again.');
                }
            }
        } catch (error) {
            console.error('Error:', error);
            this.loadingIndicator.classList.add('hidden');
            this.isProcessing = false;
            this.addMessage('Sorry, there was an error processing your request. Please try again.');
        }
    }
    
    // Clear messages from UI
    clearMessages(keepFirst = true) {
        const messages = this.messagesContainer.querySelectorAll('.message-group');
        if (keepFirst && messages.length > 0) {
            for (let i = 1; i < messages.length; i++) {
                messages[i].remove();
            }
        } else {
            this.messagesContainer.innerHTML = '';
        }
    }
}
