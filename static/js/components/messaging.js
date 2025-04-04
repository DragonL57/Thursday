import { sendChatMessage, streamChatMessage, abortCurrentRequest } from '../utils/api.js';
import { adjustTextareaHeight, scrollToBottom } from '../utils/dom.js';

export class MessagingComponent {
    constructor(elements) {
        this.userInput = elements.userInput;
        this.sendButton = elements.sendButton;
        this.messagesContainer = elements.messagesContainer;
        this.messageForm = elements.messageForm;
        this.loadingIndicator = elements.loadingIndicator;
        this.isProcessing = false;
        this.currentAssistantMessage = null; // Track the current assistant message being generated
        
        // Track image attachments
        this.currentImageData = null;
        this.imagePreviewContainer = elements.imagePreviewContainer || document.getElementById('imagePreviewContainer');
        
        this.initEvents();
    }
    
    initEvents() {
        // Form submission handler
        this.messageForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // If we're already processing, this means we want to stop generation
            if (this.isProcessing) {
                this.stopGeneration();
                return;
            }
            
            const message = this.userInput.value.trim();
            if ((message || this.currentImageData) && !this.isProcessing) {
                await this.sendMessage(message);
            }
        });
        
        // Add paste event listener to the textarea
        this.userInput.addEventListener('paste', (e) => {
            this.handlePaste(e);
        });
        
        // Add handler for image preview clear button if it exists
        if (this.imagePreviewContainer) {
            this.imagePreviewContainer.addEventListener('click', (e) => {
                if (e.target.classList.contains('remove-image')) {
                    this.clearImageAttachment();
                }
            });
        }
    }
    
    // New method to stop ongoing generation
    stopGeneration() {
        // Abort the current API request
        abortCurrentRequest();
        
        // Reset UI state
        this.setGeneratingState(false);
        
        // Add a note that generation was stopped
        if (this.currentAssistantMessage) {
            const messageBubble = this.currentAssistantMessage.querySelector('.message-bubble');
            if (messageBubble) {
                const stoppedNote = document.createElement('div');
                stoppedNote.className = 'generation-stopped-note';
                stoppedNote.textContent = '(Generation stopped)';
                stoppedNote.style.color = 'var(--text-tertiary)';
                stoppedNote.style.fontStyle = 'italic';
                stoppedNote.style.fontSize = '0.85rem';
                stoppedNote.style.marginTop = '0.5rem';
                messageBubble.appendChild(stoppedNote);
            }
        }
        
        // Clear reference to current assistant message
        this.currentAssistantMessage = null;
    }
    
    // Set UI state for generating/not generating
    setGeneratingState(isGenerating) {
        this.isProcessing = isGenerating;
        
        // Update input field state
        this.userInput.disabled = isGenerating;
        const inputWrapper = this.userInput.closest('.input-wrapper');
        if (isGenerating) {
            inputWrapper.classList.add('generating');
        } else {
            inputWrapper.classList.remove('generating');
        }
        
        // Update button appearance
        if (isGenerating) {
            this.sendButton.classList.remove('send-button');
            this.sendButton.classList.add('stop-button');
            this.sendButton.querySelector('.material-icons-round').textContent = 'close';
            this.sendButton.title = 'Stop generation';
        } else {
            this.sendButton.classList.remove('stop-button');
            this.sendButton.classList.add('send-button');
            this.sendButton.querySelector('.material-icons-round').textContent = 'send';
            this.sendButton.title = 'Send message';
            this.sendButton.disabled = !this.userInput.value.trim() && !this.currentImageData;
        }
        
        // Hide the standalone loading indicator
        this.loadingIndicator.classList.add('hidden');
    }
    
    // Handle paste events to capture images
    handlePaste(e) {
        const items = e.clipboardData?.items;
        if (!items) return;
        
        // Look for image items in the clipboard
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                // Convert the image to a File object
                const file = items[i].getAsFile();
                if (file) {
                    this.processImageFile(file);
                    // Prevent the image from being pasted as a blob URL
                    e.preventDefault();
                    break;
                }
            }
        }
    }
    
    // Process an image file and show preview
    processImageFile(file) {
        // Add size validation
        if (file.size > 4 * 1024 * 1024) { // 4MB limit
            this.addMessage("Image is too large. Please use an image smaller than 4MB.", false);
            return;
        }
        
        const reader = new FileReader();
        reader.onload = (e) => {
            const dataUrl = e.target.result;
            this.currentImageData = dataUrl;
            this.showImagePreview(dataUrl);
            
            // Enable send button even if text is empty
            this.sendButton.disabled = false;
            
            // Show a very minimal size notice
            if (file.size > 1 * 1024 * 1024) {
                const sizeInMB = (file.size / (1024 * 1024)).toFixed(1);
                const imageResizeNotice = document.createElement('span');
                imageResizeNotice.className = 'image-notice';
                imageResizeNotice.textContent = `${sizeInMB}MB`;
                imageResizeNotice.style.marginLeft = '4px';
                this.imagePreviewContainer.appendChild(imageResizeNotice);
            }
        };
        reader.readAsDataURL(file);
    }
    
    // Show image preview in the UI
    showImagePreview(dataUrl) {
        if (!this.imagePreviewContainer) {
            this.imagePreviewContainer = document.createElement('div');
            this.imagePreviewContainer.id = 'imagePreviewContainer';
            this.imagePreviewContainer.className = 'image-preview-container';
            this.messageForm.querySelector('.input-wrapper').appendChild(this.imagePreviewContainer);
        }
        
        // Clear any existing content
        this.imagePreviewContainer.innerHTML = '';
        
        // Build the HTML directly with inline styles as a backup
        this.imagePreviewContainer.innerHTML = `
            <div class="image-preview" style="position:relative; width:80px; height:80px; overflow:visible;">
                <img src="${dataUrl}" alt="Preview" style="width:100%; height:100%; object-fit:cover;">
                <button type="button" class="remove-image" title="Remove" style="position:absolute; top:-6px; right:-6px; width:14px; height:14px; background-color:red; color:white; font-size:10px; border-radius:50%; line-height:14px; border:1px solid white; padding:0; margin:0; z-index:9999; box-shadow:0 0 2px rgba(0,0,0,0.5);">×</button>
            </div>
        `;
        
        this.imagePreviewContainer.classList.remove('hidden');
        
        // Add event listener directly to the button
        const removeBtn = this.imagePreviewContainer.querySelector('.remove-image');
        if (removeBtn) {
            removeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.clearImageAttachment();
            });
        }
        
        // Force styles with JavaScript as ultimate backup
        const imagePreview = this.imagePreviewContainer.querySelector('.image-preview');
        if (imagePreview) {
            imagePreview.style.position = 'relative';
            imagePreview.style.width = '80px';  // Doubled from 40px to 80px
            imagePreview.style.height = '80px'; // Doubled from 40px to 80px
            imagePreview.style.overflow = 'visible';
            imagePreview.style.margin = '0';
            imagePreview.style.padding = '0';
            
            const img = imagePreview.querySelector('img');
            if (img) {
                img.style.width = '100%';
                img.style.height = '100%';
                img.style.objectFit = 'cover';
            }
        }
        
        console.log('Image preview created at 80px size (doubled)');
    }
    
    // Clear the current image attachment
    clearImageAttachment() {
        this.currentImageData = null;
        if (this.imagePreviewContainer) {
            this.imagePreviewContainer.innerHTML = '';
            this.imagePreviewContainer.classList.add('hidden');
        }
        
        // Disable send button if text is also empty
        if (!this.userInput.value.trim()) {
            this.sendButton.disabled = true;
        }
    }
    
    // Add message to the UI
    addMessage(content, isUser = false, hasImage = false) {
        // Hide welcome message if it exists
        const welcomeMessage = document.getElementById('welcomeMessage');
        if (welcomeMessage) {
            welcomeMessage.classList.add('hidden');
        }
        
        const messageGroup = document.createElement('div');
        messageGroup.className = isUser ? 'message-group user-message' : 'message-group assistant-message';
        
        let messageHTML = `
            <div class="message-content">
                <div class="message-content-container">
                    <div class="message-bubble">
        `;
        
        // Add image if exists
        if (isUser && hasImage && this.currentImageData) {
            messageHTML += `
                <div class="message-image">
                    <img src="${this.currentImageData}" alt="Attached image" loading="lazy">
                </div>
            `;
        }
        
        // For assistant messages, add thinking indicator if we're starting a new response
        if (!isUser && !content) {
            messageHTML += `
                <div class="message-thinking">
                    <span>Thursday is thinking</span>
                    <div class="typing-dots">
                        <div class="dot"></div>
                        <div class="dot"></div>
                        <div class="dot"></div>
                    </div>
                </div>
            `;
        }
        
        // Close message bubble div
        messageHTML += `</div></div></div>`;
        
        messageGroup.innerHTML = messageHTML;
        
        const messageBubble = messageGroup.querySelector('.message-bubble');
        
        // Add the text content
        if (isUser) {
            // For user messages, we add a text paragraph if there's content
            if (content) {
                const textParagraph = document.createElement('p');
                textParagraph.textContent = content;
                
                // If there's an image, insert the text before it
                const imageElement = messageBubble.querySelector('.message-image');
                if (imageElement) {
                    messageBubble.insertBefore(textParagraph, imageElement);
                } else {
                    messageBubble.appendChild(textParagraph);
                }
            }
        } else if (content) {
            // For both user and assistant messages, render markdown
            const preservedContent = this.preserveLineBreaks(content);
            messageBubble.innerHTML += marked.parse(preservedContent);
            
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
        
        // If this is an assistant message, store reference to update later with streaming content
        if (!isUser) {
            this.currentAssistantMessage = messageGroup;
        }
        
        return messageGroup;
    }
    
    // Helper method to preserve line breaks in content
    preserveLineBreaks(content) {
        // Replace single-character line breaks with special markup
        // This will preserve sequences of single characters on their own lines
        if (!content) return '';
        
        // First, identify patterns where single characters are on their own lines
        return content.replace(/^(\w)$|(\n\w)$/gm, (match) => {
            const char = match.trim();
            return `${char}<!-- linebreak -->`;
        });
    }

    // Update the current assistant message with new content
    updateAssistantMessage(content) {
        if (!this.currentAssistantMessage) return;
        
        const messageBubble = this.currentAssistantMessage.querySelector('.message-bubble');
        if (!messageBubble) return;
        
        // Remove thinking indicator if it exists
        const thinkingIndicator = messageBubble.querySelector('.message-thinking');
        if (thinkingIndicator) {
            thinkingIndicator.remove();
        }
        
        // Update with new content
        messageBubble.innerHTML = marked.parse(content);
        
        // Apply formatting
        renderMathInElement(messageBubble, {
            delimiters: [
                {left: "$$", right: "$$", display: true},
                {left: "$", right: "$", display: false}
            ]
        });
        
        // Highlight any code blocks
        messageBubble.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });
        
        scrollToBottom(this.messagesContainer);
    }

    // Add a tool call as a separate message (compact version)
    addToolCallMessage(toolCall) {
        const messageGroup = document.createElement('div');
        messageGroup.className = 'message-group tool-message compact';
        
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
            <div class="message-content">
                <div class="message-content-container">
                    <div class="tool-status-indicator ${toolCall.status}" title="${toolCall.status}"></div>
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
        if (this.isProcessing) return;
        
        // Check if we have either a message or an image
        if (!message.trim() && !this.currentImageData) return;
        
        // Add user message to UI with image if present
        this.addMessage(message, true, !!this.currentImageData);
        
        // Store image data before clearing it
        const imageData = this.currentImageData;
        
        // Reset UI state
        this.userInput.value = '';
        this.clearImageAttachment();
        
        // Trigger input event to adjust textarea height
        this.userInput.dispatchEvent(new Event('input'));
        
        // Create empty assistant message with thinking indicator
        this.addMessage('', false);
        
        // Set UI to generating state
        this.setGeneratingState(true);
        
        let currentContent = '';
        
        try {
            // Use streaming API with callbacks for real-time updates
            await streamChatMessage(message, imageData, {
                // Called when a new token is received
                onToken: (token) => {
                    // Ensure proper spacing between tokens
                    if (currentContent && token) {
                        // Check if we need to add space between chunks
                        const lastChar = currentContent.charAt(currentContent.length - 1);
                        const firstChar = token.charAt(0);
                        
                        // Add space in the following cases:
                        // 1. Between two alphanumeric characters
                        // 2. After punctuation like comma, semicolon, etc. when followed by alphanumeric
                        // 3. Before an opening parenthesis or bracket when preceded by alphanumeric
                        const needsSpace = (
                            // Case 1: Between alphanumeric characters
                            (/[a-zA-Z0-9]/.test(lastChar) && 
                             /[a-zA-Z0-9]/.test(firstChar)) ||
                            
                            // Case 2: After punctuation when followed by alphanumeric
                            (/[,.;:!?]/.test(lastChar) && 
                             /[a-zA-Z0-9]/.test(firstChar)) ||
                            
                            // Case 3: Before opening brackets/parentheses
                            (/[a-zA-Z0-9]/.test(lastChar) && 
                             /[\(\[\{]/.test(firstChar))
                        );
                        
                        // Add space if needed and if there isn't already a space
                        if (needsSpace && 
                            !currentContent.endsWith(' ') && 
                            !token.startsWith(' ')) {
                            currentContent += ' ';
                        }
                    }
                    
                    currentContent += token;
                    this.updateAssistantMessage(currentContent);
                },
                
                // Called when a new tool call is detected
                onToolCall: (toolCall) => {
                    this.addToolCallMessage(toolCall);
                },
                
                // Called when a tool call is updated with results
                onToolUpdate: (toolCall) => {
                    this.updateToolCall(toolCall);
                },
                
                // Called when the final response is ready
                onFinalResponse: (response) => {
                    if (response) {
                        // If we already have built up content from streaming, we don't need this
                        if (!currentContent) {
                            this.updateAssistantMessage(response);
                        }
                    }
                },
                
                // Called on error
                onError: (error) => {
                    console.error('Error during streaming:', error);
                    
                    // Show a more helpful message for rate limit errors
                    if (error.toLowerCase().includes('rate limit')) {
                        this.updateAssistantMessage("Sorry, the server is busy processing images right now. Please wait a moment and try again, or use a smaller image.");
                    } else {
                        this.updateAssistantMessage(`Error: ${error}`);
                    }
                    
                    // Reset UI state
                    this.setGeneratingState(false);
                },
                
                // Called when the stream is complete
                onDone: () => {
                    // Reset UI state
                    this.setGeneratingState(false);
                    this.currentAssistantMessage = null;
                }
            });
        } catch (error) {
            console.error('Error:', error);
            
            // Show a more helpful message for rate limit errors
            if (error.toString().toLowerCase().includes('rate limit')) {
                this.updateAssistantMessage("Sorry, the server is busy processing images right now. Please wait a moment and try again, or use a smaller image.");
            } else {
                this.updateAssistantMessage('Sorry, there was an error processing your request. Please try again.');
            }
            
            // Reset UI state
            this.setGeneratingState(false);
            this.currentAssistantMessage = null;
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
