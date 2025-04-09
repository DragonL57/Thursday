import { streamChatMessage, abortCurrentRequest } from '../../utils/api.js';
import { scrollToBottom } from '../../utils/dom.js';
import { UIStateManager } from './UIStateManager.js';
import { MessageRenderer } from './MessageRenderer.js';
import { ToolCallHandler } from './ToolCallHandler.js';
import { ImageHandler } from './ImageHandler.js';

export class MessagingComponent {
    constructor(elements) {
        // Store elements
        this.userInput = elements.userInput;
        this.sendButton = elements.sendButton;
        this.messagesContainer = elements.messagesContainer;
        this.messageForm = elements.messageForm;
        this.loadingIndicator = elements.loadingIndicator;
        
        // Initialize sub-modules
        this.uiStateManager = new UIStateManager(this);
        this.messageRenderer = new MessageRenderer(this);
        this.toolCallHandler = new ToolCallHandler(this);
        this.imageHandler = new ImageHandler(this);
        
        // State variables
        this.isProcessing = false;
        this.currentAssistantMessage = null;
        this.currentImageData = null;
        this.autoSaveCompleted = false; // Add a flag to track if auto-save has been done
        this.elements = elements; // Store full elements reference
        
        // Track active tool calls
        this.activeToolCalls = new Set();
        
        // Initialize events
        this.initEvents();
        
        console.log('MessagingComponent initialized');
    }
    
    initEvents() {
        if (!this.messageForm) {
            console.error('Message form not found - cannot initialize events');
            return;
        }
        
        console.log('Setting up form submission handler');
        
        // Form submission handler with error handling
        this.messageForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            console.log('Form submitted');
            
            try {
                // If we're already processing, this means we want to stop generation
                if (this.isProcessing) {
                    console.log('Stopping generation');
                    this.uiStateManager.stopGeneration();
                    return;
                }
                
                const message = this.userInput.value.trim();
                console.log(`Message: "${message}", Image data present: ${!!this.currentImageData}`);
                
                if ((message || this.currentImageData) && !this.isProcessing) {
                    // Store a copy of the image data for sending
                    const imageDataToSend = this.currentImageData;
                    
                    // Clear the image preview IMMEDIATELY after form submission
                    // This ensures the UI is responsive right away
                    this.imageHandler.clearImagePreview();
                    
                    // Send the message with the copied image data
                    await this.sendMessage(message, imageDataToSend);
                } else {
                    console.log('No message or image to send, or already processing');
                }
            } catch (error) {
                console.error('Error in form submission handler:', error);
                this.isProcessing = false;
                this.uiStateManager.setGeneratingState(false);
            }
        });
        
        // Add paste event listener to the textarea
        this.userInput.addEventListener('paste', (e) => {
            this.imageHandler.handlePaste(e);
        });
    }

    stopGeneration() {
        this.uiStateManager.stopGeneration();
    }

    // Send message to API and handle response
    async sendMessage(message, imageDataToSend = null, skipUserMessage = false) {
        if (!message.trim() && !imageDataToSend) return;
        
        const component = this;
        
        // If we're already processing, stop the current generation before starting a new one
        if (component.isProcessing) {
            // Stop the current generation but don't reset isProcessing yet
            this.uiStateManager.stopGeneration();
        }
        
        component.isProcessing = true;
        component.clearInfoMessages();
        
        // Clear any active tool calls
        this.activeToolCalls.clear();
        
        // Reset the tools list for the new conversation turn
        console.log('Calling resetToolsList before sending new message');
        if (this.toolCallHandler) {
            this.toolCallHandler.resetToolsList();
        }
        
        // Determine if we have an image
        const hasImage = !!imageDataToSend;
        
        // Only add user message to UI if we're not skipping it (for retry)
        if (!skipUserMessage) {
            this.messageRenderer.addMessage(message, true, hasImage);
        }
        
        // Clear the input field
        this.elements.userInput.value = '';
        this.elements.userInput.style.height = 'auto';
        this.elements.sendButton.disabled = true;
        
        // Hide suggestions
        if (this.elements.suggestionsContainer) {
            this.elements.suggestionsContainer.style.display = 'none';
        }
        
        // Show loading indicator
        if (this.elements.loadingIndicator) {
            this.elements.loadingIndicator.style.display = 'block';
        }
        
        // Format the provided image data based on provider
        let formattedImageData = null;
        if (hasImage) {
            formattedImageData = this.formatImageDataForProvider(imageDataToSend);
        }
        
        try {
            // Send the message to the API with streaming
            let assistantMessage = null;
            let currentContent = '';
            let inRecursiveCall = false;
            let recursionDepth = 0;
            let lastMessageContent = ''; // Track last content to prevent duplicates
            let waitingForTokens = false; // Track if we're waiting for tokens after recursion depth change
            let lastToken = ''; // Track the last token to prevent duplicates
            
            await streamChatMessage(message, formattedImageData, {
                onToken: (token) => {
                    // Skip empty tokens
                    if (!token.trim()) return;
                    
                    // Detect and skip duplicate tokens
                    if (lastToken === token) {
                        console.log("Skipping duplicate token:", token);
                        return;
                    }
                    lastToken = token;
                    
                    // If we have a recursive call waiting for tokens, create a new message
                    if (waitingForTokens) {
                        console.log("Creating new message for recursive response that was waiting for tokens");
                        assistantMessage = null;
                        this.currentAssistantMessage = null;
                        currentContent = ''; // Reset content for the new message
                        waitingForTokens = false; // Reset the flag
                    }
                    
                    // Initialize assistant message if it doesn't exist yet
                    if (!assistantMessage) {
                        console.log("Creating new assistant message bubble");
                        assistantMessage = this.messageRenderer.addMessage('', false);
                        this.currentAssistantMessage = assistantMessage;
                    }

                    // Prevent content duplication
                    if (currentContent.endsWith(token)) {
                        console.log("Skipping duplicate token sequence");
                        return;
                    }

                    // Simply append the new token without adding unnecessary spaces
                    currentContent += token;
                    
                    // Update the UI with the correct current content
                    this.messageRenderer.updateAssistantMessage(currentContent, true);
                    
                    // Save the latest content for reference
                    lastMessageContent = currentContent;
                },
                
                // Called when a tool call is received
                onToolCall: (toolCall) => {
                    console.log("Tool call received:", toolCall);
                    
                    // Add to active tool calls
                    this.activeToolCalls.add(toolCall.id);
                    
                    // IMPORTANT: Add to the tool list
                    if (this.toolCallHandler) {
                        console.log("Adding tool call to list:", toolCall.name);
                        this.toolCallHandler.addToolCallToList(toolCall);
                        
                        // Ensure proper positioning after user message
                        this.toolCallHandler.repositionToolList();
                    }
                    
                    // Add or update the tool status indicator
                    this.messageRenderer.addToolStatusIndicator(toolCall);
                },
                
                // Called when a tool call status is updated
                onToolUpdate: (toolCall) => {
                    console.log("Tool update received:", toolCall);
                    
                    // IMPORTANT: Update in the tool list
                    if (this.toolCallHandler) {
                        console.log("Updating tool in list:", toolCall.name, toolCall.status);
                        this.toolCallHandler.updateToolInList(toolCall);
                    }
                    
                    // Update the tool status indicator
                    this.messageRenderer.updateToolStatusIndicator(toolCall);
                    
                    // Remove from active calls if completed
                    if (toolCall.status === 'completed' || toolCall.status === 'error') {
                        this.activeToolCalls.delete(toolCall.id);
                    }
                },
                
                // Called when receiving information about recursion
                onRecursionDepth: (depth) => {
                    console.log(`Recursion depth changed to: ${depth}`);
                    
                    // Detect if we're transitioning to a new recursion level
                    const isNewRecursionLevel = depth !== recursionDepth;
                    recursionDepth = depth;
                    inRecursiveCall = depth > 0;
                    
                    // If we're going to a new recursion level, prepare for a new message bubble
                    if (isNewRecursionLevel) {
                        console.log(`Recursion level changed from ${recursionDepth} to ${depth}, preparing for new message`);
                        waitingForTokens = true;
                    }
                },
                
                // Called to display temporary info messages
                onInfo: (message, isTemporary = false) => {
                    this.addInfoMessage(message, isTemporary);
                },
                
                // Called to clear temporary info messages
                onClearTempInfo: () => {
                    this.clearTemporaryInfoMessages();
                },
                
                // Called when there's an error
                onError: (errorMessage) => {
                    this.addInfoMessage(`Error: ${errorMessage}`, false, true);
                    component.isProcessing = false;
                    
                    // Hide loading indicator
                    if (component.elements.loadingIndicator) {
                        component.elements.loadingIndicator.style.display = 'none';
                    }
                },
                
                // Called when the stream is done
                onDone: () => {
                    component.isProcessing = false;
                    
                    // Clear any remaining tool status indicators
                    this.messageRenderer.clearToolStatusIndicators();
                    
                    // Mark the current message as completed to prevent adding "stopped" note later
                    if (this.currentAssistantMessage) {
                        this.currentAssistantMessage.dataset.completed = "true";
                    }
                    
                    this.latestAssistantResponse = currentContent;
                    
                    // Hide loading indicator
                    if (component.elements.loadingIndicator) {
                        component.elements.loadingIndicator.style.display = 'none';
                    }
                    
                    // Emit the firstMessageComplete event if this is the first exchange
                    if (!this.firstMessageCompleted) {
                        this.firstMessageCompleted = true;
                        const event = new CustomEvent('firstMessageComplete');
                        document.dispatchEvent(event);
                    }
                    
                    // Clear the image data
                    this.clearImageData();
                }
            });
            
            // Clear the image after sending
            this.clearImageData();
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.addInfoMessage(`Error: ${error.message}`, false, true);
            this.isProcessing = false;
            this.uiStateManager.setGeneratingState(false);
            
            // Clear any remaining tool status indicators
            this.messageRenderer.clearToolStatusIndicators();
            
            // Clear the image on error too
            this.clearImageData();
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

    // Check if there are any messages (for saving empty conversations)
    hasMessages() {
        return this.messagesContainer.querySelectorAll('.message-group').length > 1; // > 1 to account for welcome message
    }
    
    // Get the first user message for naming conversations
    getFirstUserMessage() {
        const userMessages = this.messagesContainer.querySelectorAll('.user-message');
        if (userMessages.length > 0) {
            const messageBubble = userMessages[0].querySelector('.message-bubble');
            if (messageBubble) {
                // First try to get from data-markdown attribute for accurate content
                const markdownContent = userMessages[0].getAttribute('data-markdown');
                if (markdownContent) {
                    return markdownContent;
                }
                
                // Fall back to text content
                const paragraphs = messageBubble.querySelectorAll('p');
                if (paragraphs.length > 0) {
                    return paragraphs[0].textContent.trim();
                } else {
                    return messageBubble.textContent.trim();
                }
            }
        }
        return '';
    }

    // Helper method to clear info messages
    clearInfoMessages() {
        // Remove all info messages from the container
        const infoMessages = this.messagesContainer.querySelectorAll('.info-message');
        infoMessages.forEach(message => message.remove());
    }
    
    // Helper method to clear only temporary info messages
    clearTemporaryInfoMessages() {
        const tempInfoMessages = this.messagesContainer.querySelectorAll('.info-message.temporary');
        tempInfoMessages.forEach(message => message.remove());
    }
    
    // Add an info message to the UI with improved display
    addInfoMessage(message, isTemporary = false, isError = false) {
        const infoMessage = document.createElement('div');
        infoMessage.className = `info-message ${isTemporary ? 'temporary' : ''} ${isError ? 'error' : ''}`;
        
        // Add a prefix based on message type
        let prefix = '';
        if (isError) {
            prefix = '❌ Error: ';
        } else if (!isTemporary) {
            prefix = 'ℹ️ ';
        }
        
        infoMessage.textContent = prefix + message;
        
        // Style the message for better visibility
        infoMessage.style.padding = '0.5rem 1rem';
        infoMessage.style.margin = '0.5rem 0';
        infoMessage.style.borderRadius = '8px';
        infoMessage.style.backgroundColor = isError ? 'rgba(255,0,0,0.05)' : 'rgba(0,0,0,0.03)';
        infoMessage.style.border = `1px solid ${isError ? 'rgba(255,0,0,0.1)' : 'rgba(0,0,0,0.05)'}`;
        infoMessage.style.color = isError ? '#d32f2f' : 'var(--text-secondary)';
        infoMessage.style.fontSize = '0.9rem';
        
        // If there's an assistant message currently being shown, insert before it
        if (this.currentAssistantMessage && this.messagesContainer.contains(this.currentAssistantMessage)) {
            this.messagesContainer.insertBefore(infoMessage, this.currentAssistantMessage);
        } else {
            // Otherwise append to the end
            this.messagesContainer.appendChild(infoMessage);
        }
        
        scrollToBottom(this.messagesContainer);
        return infoMessage;
    }
    
    // Get the current image data
    getImageData() {
        return this.imageHandler.getFormattedImageData();
    }
    
    // Clear the current image data
    clearImageData() {
        this.currentImageData = null;
        this.imageHandler.clearImageAttachment();
    }

    // Helper method to format image data for provider
    formatImageDataForProvider(imageData) {
        if (!imageData) return null;
        
        // Get current provider and model information
        const providerSelect = document.getElementById('providerSelect');
        const modelSelect = document.getElementById('modelSelect');
        const provider = providerSelect ? providerSelect.value : 'pollinations';
        const model = modelSelect ? modelSelect.value : '';
        
        // Format based on provider and model
        if (provider === 'pollinations') {
            return imageData;
        } else if (model.includes('gemini')) {
            return imageData;
        } else if (model.includes('github')) {
            // Let the backend know this is for GitHub
            console.log('GitHub model detected, sending image for backend processing');
            return imageData;
        } else {
            return [{
                type: 'image_url',
                image_url: {
                    url: imageData
                }
            }];
        }
    }
}
