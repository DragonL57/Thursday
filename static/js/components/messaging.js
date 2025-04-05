import { sendChatMessage, streamChatMessage, abortCurrentRequest } from '../utils/api.js';
import { adjustTextareaHeight, scrollToBottom } from '../utils/dom.js';

export class MessagingComponent {
    constructor(elements) {
        // Store elements
        this.userInput = elements.userInput;
        this.sendButton = elements.sendButton;
        this.messagesContainer = elements.messagesContainer;
        this.messageForm = elements.messageForm;
        this.loadingIndicator = elements.loadingIndicator;
        this.imagePreviewContainer = document.getElementById('imagePreviewContainer');
        
        // State variables
        this.isProcessing = false;
        this.abortController = null;
        this.currentImageData = null;
        
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
                    this.stopGeneration();
                    return;
                }
                
                const message = this.userInput.value.trim();
                console.log(`Message: "${message}", Image data present: ${!!this.currentImageData}`);
                
                if ((message || this.currentImageData) && !this.isProcessing) {
                    await this.sendMessage(message);
                } else {
                    console.log('No message or image to send, or already processing');
                }
            } catch (error) {
                console.error('Error in form submission handler:', error);
                this.isProcessing = false;
                this.setGeneratingState(false);
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
        
        // Fixed template literal - removed extra newlines
        let messageHTML = `<div class="message-content"><div class="message-content-container"><div class="message-bubble">`;
        
        // Add image if exists
        if (isUser && hasImage && this.currentImageData) {
            // Fixed template literal - removed extra newlines
            messageHTML += `<div class="message-image"><img src="${this.currentImageData}" alt="Attached image" loading="lazy"></div>`;
        }
        
        // For assistant messages, add thinking indicator if we're starting a new response
        if (!isUser && !content) {
            // Fixed template literal - removed extra newlines
            messageHTML += `<div class="message-thinking"><span>Thursday is thinking</span><div class="typing-dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>`;
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
        
        // Store the full content in a data attribute for better rebuilding
        let fullContent = messageBubble.getAttribute('data-content') || '';
        fullContent += content;
        messageBubble.setAttribute('data-content', fullContent);
        
        // Instead of appending tokens to DOM which creates spacing issues,
        // rebuild the entire content each time with proper markdown parsing
        messageBubble.innerHTML = `<div class="markdown-content">${marked.parse(fullContent)}</div>`;
        
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
        
        // Don't display empty parentheses for no arguments
        const displayArgs = args && args !== "{}" ? `(${args})` : "";
        
        // Check if result exists and determine if it's a single line
        let resultClass = !toolCall.result ? 'hidden' : '';
        if (toolCall.result && !toolCall.result.includes('\n')) {
            resultClass += ' single-line';
        }
        
        // Determine appropriate language based on tool name and result content
        let language = 'plaintext'; // Default to plaintext
        
        // Check for specific tool types
        if (toolCall.name === 'get_current_datetime' || 
            /^\d{4}-\d{2}-\d{2}/.test(toolCall.result)) {
            language = 'plaintext';
        } else if (toolCall.result && toolCall.result.startsWith('{') || toolCall.result && toolCall.result.startsWith('[')) {
            language = 'json';
        } else if (toolCall.result && toolCall.result.includes('def ') || toolCall.result && toolCall.result.includes('import ')) {
            language = 'python';
        } else if (toolCall.result && toolCall.result.includes('function') || toolCall.result && toolCall.result.includes('const ')) {
            language = 'javascript';
        } else if (toolCall.result && toolCall.result.includes('<html') || toolCall.result && toolCall.result.includes('<!DOCTYPE')) {
            language = 'html';
        }
        
        // Check if this tool call message already exists
        const existingToolCall = document.querySelector(`.message-bubble[data-tool-id="tool-call-${toolCall.id}"]`);
        if (existingToolCall) {
            // If it exists, we'll update it instead of creating a new one
            return existingToolCall.closest('.message-group');
        }
        
        messageGroup.innerHTML = `
            <div class="message-content">
                <div class="message-content-container">
                    <div class="tool-status-indicator ${toolCall.status}" title="${toolCall.status}"></div>
                    <div class="message-bubble tool-message-bubble" data-tool-id="tool-call-${toolCall.id}">
                        <div class="tool-execution">
                            <div class="tool-command">
                                <code>${toolCall.name}${displayArgs}</code>
                            </div>
                            <div class="tool-result ${resultClass}">
                                <pre><code class="language-${language}">${toolCall.result || ''}</code></pre>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Find the assistant message to place tool calls before it
        const assistantMessage = this.currentAssistantMessage;
        if (assistantMessage) {
            // Insert before the assistant message instead of appending to the container
            this.messagesContainer.insertBefore(messageGroup, assistantMessage);
        } else {
            // Fall back to appending if we don't have a reference to the assistant message
            this.messagesContainer.appendChild(messageGroup);
        }
        
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
            
            // Update tool command display if it's empty
            const commandElement = toolMessage.querySelector('.tool-command code');
            if (commandElement && commandElement.textContent.trim() === toolCall.name) {
                // If the command doesn't have args, update it
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
                
                // Don't display empty parentheses for no arguments
                const displayArgs = args && args !== "{}" ? `(${args})` : "";
                commandElement.textContent = `${toolCall.name}${displayArgs}`;
            }
            
            const resultElement = toolMessage.querySelector('.tool-result');
            if (resultElement && toolCall.result) {
                resultElement.classList.remove('hidden');
                
                // Add single-line class if result is a single line
                if (!toolCall.result.includes('\n')) {
                    resultElement.classList.add('single-line');
                }
                
                const codeElement = resultElement.querySelector('pre code');
                codeElement.textContent = toolCall.result;
                
                // Determine appropriate language based on tool name and result content
                let language = 'plaintext'; // Default to plaintext
                
                // Check for specific tool types
                if (toolCall.name === 'get_current_datetime' || 
                    /^\d{4}-\d{2}-\d{2}/.test(toolCall.result)) {
                    language = 'plaintext';
                } else if (toolCall.result.startsWith('{') || toolCall.result.startsWith('[')) {
                    language = 'json';
                } else if (toolCall.result.includes('def ') || toolCall.result.includes('import ')) {
                    language = 'python';
                } else if (toolCall.result.includes('function') || toolCall.result.includes('const ')) {
                    language = 'javascript';
                } else if (toolCall.result.includes('<html') || toolCall.result.includes('<!DOCTYPE')) {
                    language = 'html';
                }
                
                // Update the class with the determined language
                codeElement.className = `language-${language}`;
                
                // Highlight the result code
                hljs.highlightElement(codeElement);
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
                    
                    const codeElement = resultElement.querySelector('pre code');
                    codeElement.textContent = toolCall.result;
                    
                    // Determine appropriate language (same logic as above)
                    let language = 'plaintext'; // Default to plaintext
                    
                    if (toolCall.name === 'get_current_datetime' || 
                        /^\d{4}-\d{2}-\d{2}/.test(toolCall.result)) {
                        language = 'plaintext';
                    } else if (toolCall.result.startsWith('{') || toolCall.result.startsWith('[')) {
                        language = 'json';
                    } else if (toolCall.result.includes('def ') || toolCall.result.includes('import ')) {
                        language = 'python';
                    } else if (toolCall.result.includes('function') || toolCall.result.includes('const ')) {
                        language = 'javascript';
                    } else if (toolCall.result.includes('<html') || toolCall.result.includes('<!DOCTYPE')) {
                        language = 'html';
                    }
                    
                    // Update the class with the determined language
                    codeElement.className = `language-${language}`;
                    
                    // Highlight the result code
                    hljs.highlightElement(codeElement);
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
        
        // Set UI to generating state
        this.setGeneratingState(true);
        
        // Create empty assistant message with thinking indicator
        let assistantMessage = this.addMessage('', false);
        let currentContent = '';
        let recursionDepth = 0;
        let inRecursiveCall = false;
        
        // Keep track of temporary info messages
        let tempInfoElement = null;

        try {
            // Use streaming API with callbacks for real-time updates
            await streamChatMessage(message, imageData, {
                // Called when a new token is received
                onToken: (token) => {
                    // If we're in a recursive call and have no content yet,
                    // create a new message for the follow-up response
                    if (inRecursiveCall && !currentContent) {
                        console.log("Creating new message for recursive response");
                        // Create a new assistant message for the follow-up response
                        assistantMessage = this.addMessage('', false);
                        currentContent = '';
                    }

                    // Update current content
                    currentContent += token;
                    
                    // Update the UI with the token
                    this.updateAssistantMessage(token);
                },
                
                // Called when a new tool call is detected
                onToolCall: (toolCall) => {
                    console.log('Tool call detected:', toolCall);
                    // The message added by this will now appear before the assistant message
                    this.addToolCallMessage(toolCall);
                },
                
                // Called when a tool call is updated with results
                onToolUpdate: (toolCall) => {
                    console.log('Tool call updated:', toolCall);
                    this.updateToolCall(toolCall);
                },
                
                // Called when receiving information messages
                onInfo: (info, isTemporary) => {
                    console.log(`Info event: ${info}, temporary: ${isTemporary}`);
                    
                    if (isTemporary) {
                        // Create a temporary info message that can be removed later
                        if (tempInfoElement) {
                            tempInfoElement.textContent = info;
                        } else {
                            tempInfoElement = document.createElement('div');
                            tempInfoElement.className = 'tool-processing-info temp-info';
                            tempInfoElement.textContent = info;
                            tempInfoElement.style.fontSize = '0.8rem';
                            tempInfoElement.style.color = 'var(--text-tertiary)';
                            tempInfoElement.style.fontStyle = 'italic';
                            tempInfoElement.style.marginBottom = '0.5rem';
                            
                            // Add to the assistant message
                            const messageBubble = assistantMessage.querySelector('.message-bubble');
                            if (messageBubble) {
                                messageBubble.appendChild(tempInfoElement);
                                scrollToBottom(this.messagesContainer);
                            }
                        }
                    } else {
                        // Add a permanent info message
                        const infoDiv = document.createElement('div');
                        infoDiv.className = 'tool-processing-info';
                        infoDiv.textContent = info;
                        infoDiv.style.fontSize = '0.8rem';
                        infoDiv.style.color = 'var(--text-tertiary)';
                        infoDiv.style.fontStyle = 'italic';
                        infoDiv.style.marginBottom = '0.5rem';
                        
                        // Add to the messages container
                        this.messagesContainer.appendChild(infoDiv);
                        scrollToBottom(this.messagesContainer);
                    }
                },
                
                // Called to clear temporary info messages
                onClearTempInfo: () => {
                    console.log('Clearing temporary info messages');
                    if (tempInfoElement) {
                        tempInfoElement.remove();
                        tempInfoElement = null;
                    }
                },
                
                // Called when receiving information about recursion
                onRecursionDepth: (depth) => {
                    console.log(`Recursion depth changed to: ${depth}`);
                    recursionDepth = depth;
                    inRecursiveCall = depth > 0;
                    
                    if (inRecursiveCall) {
                        // Create a new assistant message for the follow-up response
                        console.log("Creating new message bubble for recursive response");
                        assistantMessage = this.addMessage('', false);
                        // Reset content for the new recursive response
                        currentContent = '';
                    }
                },
                
                // Called when the final response is ready
                onFinalResponse: (response) => {
                    console.log('Final response received:', response);
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
                    
                    // Also clear any temporary info messages
                    if (tempInfoElement) {
                        tempInfoElement.remove();
                        tempInfoElement = null;
                    }
                },
                
                // Called when the stream is complete
                onDone: () => {
                    // Clear any remaining temporary info messages
                    if (tempInfoElement) {
                        tempInfoElement.remove();
                        tempInfoElement = null;
                    }
                    
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
            
            // Clear any temporary info messages
            if (tempInfoElement) {
                tempInfoElement.remove();
                tempInfoElement = null;
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
