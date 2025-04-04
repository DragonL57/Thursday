import { setupMarkdown } from './utils/markdown.js';
import { adjustTextareaHeight } from './utils/dom.js';
import { resetConversation } from './utils/api.js';
import { MessagingComponent } from './components/messaging.js';
import { ThemeManager } from './components/theme.js';
import { SidebarManager } from './components/sidebar.js';
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
        toggleSidebarButton: document.getElementById('toggleSidebar'),
        clearChatButton: document.getElementById('clearChat'),
        settingsButton: document.getElementById('settingsButton'),
        settingsModal: document.getElementById('settingsModal'),
        closeModalButtons: document.querySelectorAll('.close-modal'),
        saveSettingsButton: document.getElementById('saveSettings'),
        temperatureSlider: document.getElementById('temperatureSlider'),
        temperatureValue: document.getElementById('temperatureValue'),
        modelSelect: document.getElementById('modelSelect'),
        saveChatHistory: document.getElementById('saveChatHistory'),
        sidebar: document.querySelector('.sidebar'),
        suggestionChips: document.querySelectorAll('.chip'),
        attachButton: document.getElementById('attachButton')
    };
    
    // Ensure loading indicator is hidden on page load
    elements.loadingIndicator.classList.add('hidden');
    
    // Initialize components
    const messagingComponent = new MessagingComponent(elements);
    const themeManager = new ThemeManager(elements.toggleThemeButton);
    const sidebarManager = new SidebarManager(elements.toggleSidebarButton, elements.sidebar);
    const settingsManager = new SettingsManager(elements, messagingComponent);
    
    // Expose messaging component globally so attachButton can access it
    window.messagingComponent = messagingComponent;

    // After a new message is added to the DOM, render any LaTeX in it and highlight code
    const originalAddMessage = MessagingComponent.prototype.addMessage;
    MessagingComponent.prototype.addMessage = function(message, isUser = false, toolCalls = []) {
        const messageElement = originalAddMessage.call(this, message, isUser, toolCalls);
        if (messageElement) {
            // Apply syntax highlighting to any code blocks
            messageElement.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
            
            // Wait a bit to ensure content is fully rendered
            setTimeout(() => {
                try {
                    if (typeof renderMathInElement === 'function') {
                        // Add more restrictive configuration to avoid false positives
                        renderMathInElement(messageElement, {
                            delimiters: [
                                {left: '$$', right: '$$', display: true},
                                {left: '$', right: '$', display: false},
                                // Be more specific about square bracket math to avoid capturing citations
                                {left: '[\\n\\s]*', right: '[\\n\\s]*', display: true}
                            ],
                            ignoredTags: [
                                'a', 'script', 'noscript', 'style', 'textarea', 'pre',
                                'code', 'annotation', 'annotation-xml', 'cite', 'span'
                            ],
                            throwOnError: false,
                            strict: false,
                            // Don't process text that looks like a citation or URL
                            trust: (context) => {
                                const text = context.text;
                                // Skip processing if it looks like a citation or URL
                                if (/(Source:|http|www|\.com|\.org|\.net)/.test(text)) {
                                    return false;
                                }
                                // Also skip if it contains newlines with single letters (formatted citations)
                                if (/\n[A-Za-z]\n[A-Za-z]\n/.test(text)) {
                                    return false;
                                }
                                return true;
                            }
                        });
                    }
                } catch (e) {
                    console.error('Error rendering LaTeX:', e);
                }
            }, 100);
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
    
    // Set up input handling events
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
    
    // Set up clear chat button
    elements.clearChatButton.addEventListener('click', () => {
        if (confirm('Are you sure you want to clear the conversation?')) {
            messagingComponent.clearMessages(true);
            
            // Send a reset request to the server
            resetConversation().catch(err => {
                console.error('Failed to reset conversation on server:', err);
            });
        }
    });
    
    // Set up suggestion chips
    elements.suggestionChips.forEach(chip => {
        chip.addEventListener('click', () => {
            elements.userInput.value = chip.textContent;
            adjustTextareaHeight(elements.userInput, elements.sendButton);
            elements.sendButton.disabled = false;
        });
    });

    // Add file upload support
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
            if (fileInput.files && fileInput.files[0]) {
                // Get the messaging component
                const messagingComponent = window.messagingComponent;
                
                if (messagingComponent) {
                    messagingComponent.processImageFile(fileInput.files[0]);
                }
            }
            
            // Remove the file input element
            document.body.removeChild(fileInput);
        });
    });
    
    // Remove the input event listener that hides welcome message while typing
    // Keep only the form submission event to hide welcome message
    const welcomeMessage = document.getElementById('welcomeMessage');
    
    // Hide welcome message only on form submission, not while typing
    elements.messageForm.addEventListener('submit', (e) => {
        if (welcomeMessage) {
            welcomeMessage.classList.add('hidden');
        }
    }, { once: true });
    
    // Initialize UI
    elements.userInput.focus();
    adjustTextareaHeight(elements.userInput, elements.sendButton);
});
