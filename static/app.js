// Initialize marked with extensions for code highlighting
marked.use({
    renderer: {
        code(code, language) {
            const validLanguage = hljs.getLanguage(language) ? language : 'plaintext';
            const highlightedCode = hljs.highlight(code, { language: validLanguage }).value;
            
            return `
                <div class="code-block">
                    <div class="code-header">
                        <span class="language-indicator">${validLanguage}</span>
                        <span class="copy-code" onclick="copyCode(this)">
                            <span class="material-icons-round" style="font-size: 16px">content_copy</span>
                            Copy
                        </span>
                    </div>
                    <pre><code class="hljs ${validLanguage}">${highlightedCode}</code></pre>
                </div>
            `;
        }
    }
});

// Initialize the app when DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // Dom elements
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const messagesContainer = document.getElementById('messages');
    const messageForm = document.getElementById('messageForm');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const toggleThemeButton = document.getElementById('toggleTheme');
    const toggleSidebarButton = document.getElementById('toggleSidebar');
    const clearChatButton = document.getElementById('clearChat');
    const settingsButton = document.getElementById('settingsButton');
    const settingsModal = document.getElementById('settingsModal');
    const closeModalButtons = document.querySelectorAll('.close-modal');
    const saveSettingsButton = document.getElementById('saveSettings');
    const temperatureSlider = document.getElementById('temperatureSlider');
    const temperatureValue = document.getElementById('temperatureValue');
    const suggestionChips = document.querySelectorAll('.chip');
    
    // App state
    let isProcessing = false;
    let darkModeEnabled = localStorage.getItem('darkMode') === 'true';
    
    // Apply theme from localStorage
    if (darkModeEnabled) {
        document.body.classList.add('dark-mode');
        toggleThemeButton.querySelector('.material-icons-round').textContent = 'light_mode';
    }
    
    // Resize textarea height as content grows
    function adjustTextareaHeight() {
        userInput.style.height = 'auto';
        userInput.style.height = Math.min(userInput.scrollHeight, 200) + 'px';
        
        // Enable/disable send button based on input
        sendButton.disabled = userInput.value.trim() === '';
    }
    
    // Add message to the UI
    function addMessage(content, isUser = false) {
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
        
        messagesContainer.appendChild(messageGroup);
        scrollToBottom();
        
        return messageGroup;
    }
    
    // Scroll messages container to bottom
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Send message to API and handle response
    async function sendMessage(message) {
        if (isProcessing || !message.trim()) return;
        
        // Add user message to UI
        addMessage(message, true);
        userInput.value = '';
        adjustTextareaHeight();
        
        // Show loading indicator
        isProcessing = true;
        loadingIndicator.classList.remove('hidden');
        
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Hide loading indicator
            loadingIndicator.classList.add('hidden');
            isProcessing = false;
            
            if (data.error) {
                addMessage(`Error: ${data.error}`);
            } else if (data.response) {
                addMessage(data.response);
            } else {
                addMessage('Sorry, I received an empty response. Please try again.');
            }
        } catch (error) {
            console.error('Error:', error);
            loadingIndicator.classList.add('hidden');
            isProcessing = false;
            addMessage(`Sorry, there was an error communicating with the server: ${error.message}`);
        }
    }
    
    // Event listeners
    messageForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (message) {
            sendMessage(message);
        }
    });
    
    userInput.addEventListener('input', adjustTextareaHeight);
    
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendButton.disabled) {
                messageForm.dispatchEvent(new Event('submit'));
            }
        }
    });
    
    toggleThemeButton.addEventListener('click', () => {
        darkModeEnabled = !darkModeEnabled;
        document.body.classList.toggle('dark-mode', darkModeEnabled);
        localStorage.setItem('darkMode', darkModeEnabled);
        
        // Update icon
        const icon = toggleThemeButton.querySelector('.material-icons-round');
        icon.textContent = darkModeEnabled ? 'light_mode' : 'dark_mode';
    });
    
    toggleSidebarButton.addEventListener('click', () => {
        document.querySelector('.sidebar').classList.toggle('open');
    });
    
    clearChatButton.addEventListener('click', () => {
        if (confirm('Are you sure you want to clear the conversation?')) {
            // Keep only the first welcome message
            const firstMessage = messagesContainer.firstElementChild;
            messagesContainer.innerHTML = '';
            if (firstMessage) {
                messagesContainer.appendChild(firstMessage);
            }
            
            // Send a reset request to the server
            fetch('/reset', { method: 'POST' }).catch(err => {
                console.error('Failed to reset conversation on server:', err);
            });
        }
    });
    
    settingsButton.addEventListener('click', () => {
        settingsModal.classList.add('active');
    });
    
    closeModalButtons.forEach(button => {
        button.addEventListener('click', () => {
            settingsModal.classList.remove('active');
        });
    });
    
    saveSettingsButton.addEventListener('click', () => {
        const model = document.getElementById('modelSelect').value;
        const temperature = parseFloat(temperatureSlider.value);
        const saveHistory = document.getElementById('saveChatHistory').checked;
        
        // Send settings to server
        fetch('/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model,
                temperature,
                save_history: saveHistory
            })
        }).then(response => {
            if (response.ok) {
                settingsModal.classList.remove('active');
                addMessage('Settings updated successfully!');
            } else {
                throw new Error('Failed to update settings');
            }
        }).catch(error => {
            console.error('Error saving settings:', error);
            addMessage(`Failed to update settings: ${error.message}`);
        });
    });
    
    temperatureSlider.addEventListener('input', () => {
        temperatureValue.textContent = temperatureSlider.value;
    });
    
    suggestionChips.forEach(chip => {
        chip.addEventListener('click', () => {
            userInput.value = chip.textContent;
            adjustTextareaHeight();
            sendButton.disabled = false;
        });
    });
    
    // Initialize UI
    userInput.focus();
    adjustTextareaHeight();
    
    // Global function to copy code
    window.copyCode = function(button) {
        const codeBlock = button.closest('.code-block').querySelector('code');
        const textToCopy = codeBlock.textContent;
        
        navigator.clipboard.writeText(textToCopy).then(() => {
            const originalText = button.innerHTML;
            button.innerHTML = '<span class="material-icons-round" style="font-size: 16px">check</span> Copied!';
            setTimeout(() => {
                button.innerHTML = originalText;
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy text:', err);
        });
    };
});
