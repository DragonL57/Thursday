import { setupMarkdown } from './utils/markdown.js';
import { adjustTextareaHeight } from './utils/dom.js';
import { resetConversation } from './utils/api.js';
import { MessagingComponent } from './components/messaging/index.js';
import { ThemeManager } from './components/theme.js';
import { SettingsManager } from './components/settings.js';
import { ModelSelector } from './components/ModelSelector.js'; // Add this import

// Initialize the app when DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // Set up markdown renderer
    setupMarkdown();
    
    // DOM elements
    const elements = {
        userInput: document.getElementById('userInput'),
        sendButton: document.getElementById('sendButton'),
        messagesContainer: document.getElementById('messages'),
        messageForm: document.getElementById('messageForm'),
        loadingIndicator: document.getElementById('loadingIndicator'),
        settingsButton: document.querySelector('.sidebar-settings-button'),
        settingsModal: document.getElementById('settingsModal'),
        closeModalButtons: document.querySelectorAll('.close-modal'),
        saveSettingsButton: document.getElementById('saveSettings'),
        temperatureSlider: document.getElementById('temperatureSlider'),
        temperatureValue: document.getElementById('temperatureValue'),
        maxTokensInput: document.getElementById('maxTokensInput'),
        providerSelect: document.getElementById('providerSelect'), // Add this line
        modelSelect: document.getElementById('modelSelect'),
        saveChatHistory: document.getElementById('saveChatHistory'),
        suggestionChips: document.querySelectorAll('.chip'),
        attachButton: document.getElementById('attachButton'),
        newChatButton: document.querySelector('.new-chat-icon'),
        chatHistory: document.querySelector('.chat-history'),
        newChatHeaderButton: document.querySelector('.new-chat-button')
    };
    
    // Create theme manager instance
    const themeManager = new ThemeManager();
    window.themeManager = themeManager; // Expose globally
    
    // Initialize components if we have the necessary elements
    if (!missingRequiredElements(elements)) {
        const messagingComponent = new MessagingComponent(elements);
        window.messagingComponent = messagingComponent; // Expose globally
        
        // Initialize SettingsManager
        if (elements.settingsModal && messagingComponent) {
            const settingsManager = new SettingsManager(elements, messagingComponent, themeManager);
            
            // Create and mount model selector
            const modelSelector = new ModelSelector(settingsManager);
            // Find the input actions container
            const inputActions = document.querySelector('.input-actions');
            if (inputActions) {
                modelSelector.mount(inputActions);
                console.log('Model selector mounted to input actions container');
                
                // Store the model selector instance globally for debugging
                window.modelSelector = modelSelector;
            } else {
                console.error('Could not find input-actions container to mount model selector');
            }
        }
        
        // Set up new chat button
        if (elements.newChatButton) {
            elements.newChatButton.addEventListener('click', () => {
                // Remove confirmation dialog and just execute the action
                messagingComponent.clearMessages(true);
                
                // Send a reset request to the server
                resetConversation().catch(err => {
                    console.error('Failed to reset conversation on server:', err);
                });
            });
        }

        // Add a direct event listener for form submission
        if (elements.messageForm) {
            elements.messageForm.addEventListener('submit', (e) => {
                e.preventDefault();
                console.log('Form submission detected');
                
                const message = elements.userInput.value.trim();
                if (message && !messagingComponent.isProcessing) {
                    messagingComponent.sendMessage(message).catch(err => {
                        console.error('Error sending message:', err);
                    });
                }
            });
            
            console.log('Direct form submission listener added');
        }
        
        // Enable the send button explicitly when there's text
        if (elements.userInput && elements.sendButton) {
            elements.userInput.addEventListener('input', () => {
                elements.sendButton.disabled = elements.userInput.value.trim() === '';
            });
            console.log('Input listener for enabling button added');
        }

        // After a new message is added to the DOM, render any LaTeX in it and highlight code
        const originalAddMessage = MessagingComponent.prototype.addMessage;
        MessagingComponent.prototype.addMessage = function(message, isUser = false, toolCalls = []) {
            const messageElement = originalAddMessage.call(this, message, isUser, toolCalls);
            if (messageElement) {
                // Apply syntax highlighting to any code blocks
                messageElement.querySelectorAll('pre code').forEach((block) => {
                    hljs.highlightElement(block);
                });
                
                // Perform math rendering in a non-blocking way
                setTimeout(() => {
                    try {
                        if (typeof renderMathInElement === 'function') {
                            renderMathInElement(messageElement, {
                                delimiters: [
                                    {left: '$$', right: '$$', display: true},
                                    {left: '$', right: '$', display: false},
                                    {left: '\\[', right: '\\]', display: true},
                                    {left: '\\(', right: '\\)', display: false},
                                    {left: '[', right: ']', display: true}
                                ],
                                ignoredTags: [
                                    'script', 'noscript', 'style', 'textarea', 'pre',
                                    'code', 'annotation', 'annotation-xml'
                                ],
                                throwOnError: false,
                                strict: false,
                                trust: true,
                                macros: {
                                    "\\phi": "\\varphi",
                                    "\\quad": "\\;\\;"
                                }
                            });
                        }
                    } catch (e) {
                        console.error('Error rendering LaTeX:', e);
                    }
                }, 0); // Use 0ms timeout to put in next event loop but not delay too much
            }
            return messageElement;
        };
        
        // Enable code highlighting when updating tool call results
        const originalUpdateToolCall = MessagingComponent.prototype.updateToolCall;
        MessagingComponent.prototype.updateToolCall = function(toolCall) {
            originalUpdateToolCall.call(this, toolCall);
            const element = document.getElementById(`tool-call-${toolCall.id}`);
            if (element) {
                element.querySelectorAll('pre code').forEach((block) => {
                    hljs.highlightElement(block);
                });
            }
        };
    }
    
    // Set up input handling events
    if (elements.userInput && elements.sendButton) {
        elements.userInput.addEventListener('input', () => {
            adjustTextareaHeight(elements.userInput, elements.sendButton);
        });
        
        elements.userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!elements.sendButton.disabled) {
                    elements.messageForm.dispatchEvent(new Event('submit'));
                }
            }
        });
    }
    
    // Set up clear chat button
    if (elements.clearChatButton && window.messagingComponent) {
        elements.clearChatButton.addEventListener('click', () => {
            if (confirm('Are you sure you want to clear the conversation?')) {
                window.messagingComponent.clearMessages(true);
                
                // Send a reset request to the server
                resetConversation().catch(err => {
                    console.error('Failed to reset conversation on server:', err);
                });
            }
        });
    }
    
    // Set up suggestion chips
    if (elements.suggestionChips && elements.userInput && elements.sendButton) {
        elements.suggestionChips.forEach(chip => {
            chip.addEventListener('click', () => {
                elements.userInput.value = chip.textContent;
                adjustTextareaHeight(elements.userInput, elements.sendButton);
                elements.sendButton.disabled = false;
            });
        });
    }

    // Add file upload support
    if (elements.attachButton) {
        elements.attachButton.addEventListener('click', () => {
            // Create a hidden file input element
            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'image/*';
            fileInput.style.display = 'none';
            document.body.appendChild(fileInput);
            
            // Trigger file dialog
            fileInput.click();
            
            // Handle selected file
            fileInput.addEventListener('change', () => {
                if (fileInput.files && fileInput.files[0] && window.messagingComponent) {
                    window.messagingComponent.processImageFile(fileInput.files[0]);
                }
                
                // Remove the file input element
                document.body.removeChild(fileInput);
            });
        });
    }
    
    // Remove the input event listener that hides welcome message while typing
    // Keep only the form submission event to hide welcome message
    const welcomeMessage = document.getElementById('welcomeMessage');
    
    // Hide welcome message only on form submission, not while typing
    if (elements.messageForm && welcomeMessage) {
        elements.messageForm.addEventListener('submit', (e) => {
            welcomeMessage.classList.add('hidden');
        }, { once: true });
    }
    
    // Initialize UI
    if (elements.userInput && elements.sendButton) {
        elements.userInput.focus();
        adjustTextareaHeight(elements.userInput, elements.sendButton);
    }

    // Add a global document listener to handle copy button clicks
    document.addEventListener('click', function(e) {
        // Check if the clicked element or its parent is a copy button
        const copyButton = e.target.closest('.copy-markdown-button');
        if (copyButton) {
            // Check if the message already has a class or data attribute indicating its own handler is working
            const messageGroup = copyButton.closest('.message-group');
            
            // Only use the global handler as a fallback if the message doesn't have its own handler
            if (messageGroup && !messageGroup.id && !messageGroup.hasAttribute('data-markdown')) {
                console.log('Copy button clicked via global handler (fallback)');
                e.preventDefault();
                e.stopPropagation();
                
                // Find text content to copy
                const messageBubble = messageGroup.querySelector('.message-bubble');
                const textContent = messageBubble ? messageBubble.textContent : messageGroup.textContent;
                
                // Use the most direct and reliable method
                navigator.clipboard.writeText(textContent)
                    .then(() => {
                        console.log('✓ Copied to clipboard via fallback handler!');
                        // Show visual feedback
                        // ...existing feedback code...
                    })
                    .catch(err => {
                        console.error('Copy failed:', err);
                    });
            }
        }
    });
});

// Check if any required elements are missing
function missingRequiredElements(elements) {
    const requiredElements = ['userInput', 'sendButton', 'messagesContainer', 'messageForm', 'loadingIndicator'];
    
    let missingElements = false;
    requiredElements.forEach(elementName => {
        if (!elements[elementName]) {
            console.error(`Required DOM element '${elementName}' not found`);
            missingElements = true;
        }
    });
    
    if (missingElements) {
        console.error('Some required DOM elements are missing. Chat functionality may not work properly.');
    }
    
    return missingElements;
}
