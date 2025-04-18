import { setupMarkdown } from './utils/markdown.js';
import { adjustTextareaHeight } from './utils/dom.js';
import { resetConversation } from './utils/api.js';
import { MessagingComponent } from './components/messaging.js';
import { ThemeManager } from './components/theme.js';
import { SettingsManager } from './components/settings.js';

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
        toggleThemeButton: document.getElementById('toggleTheme'),
        clearChatButton: document.getElementById('clearChat'),
        // settingsButton was causing errors - it doesn't exist in the HTML
        settingsButton: null,
        settingsModal: document.getElementById('settingsModal'),
        closeModalButtons: document.querySelectorAll('.close-modal'),
        saveSettingsButton: document.getElementById('saveSettings'),
        temperatureSlider: document.getElementById('temperatureSlider'),
        temperatureValue: document.getElementById('temperatureValue'),
        maxTokensInput: document.getElementById('maxTokensInput'),
        modelSelect: document.getElementById('modelSelect'),
        saveChatHistory: document.getElementById('saveChatHistory'),
        suggestionChips: document.querySelectorAll('.chip'),
        attachButton: document.getElementById('attachButton')
    };
    
    // Ensure loading indicator is hidden on page load
    if (elements.loadingIndicator) {
        elements.loadingIndicator.classList.add('hidden');
    }
    
    // Make sure all required DOM elements are present
    const requiredElements = [
        'userInput', 'sendButton', 'messagesContainer', 'messageForm', 'loadingIndicator'
    ];
    
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
    
    // Initialize components
    try {
        // Only initialize components if we have the necessary elements
        if (!missingElements) {
            const messagingComponent = new MessagingComponent(elements);
            window.messagingComponent = messagingComponent; // Expose globally
            
            if (elements.toggleThemeButton) {
                const themeManager = new ThemeManager(elements.toggleThemeButton);
            }
            
            // Only initialize SettingsManager if both settingsModal and messagingComponent exist
            if (elements.settingsModal && messagingComponent) {
                const settingsManager = new SettingsManager(elements, messagingComponent);
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
        
    } catch (error) {
        console.error('Error initializing components:', error);
        // Add an error message to the UI
        if (elements.messagesContainer) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'message-group system-message';
            errorDiv.innerHTML = `
                <div class="message-content">
                    <div class="message-content-container">
                        <div class="message-bubble">
                            <p>Sorry, there was an error initializing the chat interface: ${error.message}</p>
                        </div>
                    </div>
                </div>
            `;
            elements.messagesContainer.appendChild(errorDiv);
        }
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
});
