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
        suggestionChips: document.querySelectorAll('.chip')
    };
    
    // Ensure loading indicator is hidden on page load
    elements.loadingIndicator.classList.add('hidden');
    
    // Initialize components
    const messagingComponent = new MessagingComponent(elements);
    const themeManager = new ThemeManager(elements.toggleThemeButton);
    const sidebarManager = new SidebarManager(elements.toggleSidebarButton, elements.sidebar);
    const settingsManager = new SettingsManager(elements, messagingComponent);
    
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
    
    // Initialize UI
    elements.userInput.focus();
    adjustTextareaHeight(elements.userInput, elements.sendButton);
});
