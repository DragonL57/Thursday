import { resetConversation } from '../utils/api.js';
import { BrowserStorageManager } from '../utils/BrowserStorageManager.js';

export class ConversationManager {
    constructor(messagingComponent, elements) {
        this.messagingComponent = messagingComponent;
        this.chatHistory = elements.chatHistory;
        this.newChatButton = elements.newChatButton;
        this.newChatHeaderButton = elements.newChatHeaderButton;
        this.currentConversationId = 'current'; // Default conversation ID
        
        // Initialize the storage manager
        this.storageManager = new BrowserStorageManager();
        
        this.init();
    }
    
    async init() {
        // Fetch existing conversations
        await this.loadConversationList();
        
        // Add event listeners
        if (this.newChatButton) {
            this.newChatButton.addEventListener('click', () => this.createNewConversation());
        }
        
        if (this.newChatHeaderButton) {
            this.newChatHeaderButton.addEventListener('click', () => this.createNewConversation());
        }
    }
    
    async loadConversationList() {
        try {
            // Get conversations from browser storage
            const conversations = this.storageManager.getConversations();
            this.renderConversationList(conversations);
        } catch (error) {
            console.error('Failed to load conversations:', error);
        }
    }
    
    renderConversationList(conversations) {
        if (!this.chatHistory) return;
        
        // Clear existing items
        this.chatHistory.innerHTML = '';
        
        // Only add "Current Conversation" item if we're actually in a current/new conversation
        // This prevents it from showing up when switching between saved conversations
        if (this.currentConversationId === 'current') {
            const currentChatItem = this.createConversationItem({
                id: 'current',
                name: 'Current Conversation',
                timestamp: new Date().toISOString(),
                isCurrent: true
            });
            this.chatHistory.appendChild(currentChatItem);
        }
        
        // Add saved conversations
        if (conversations && conversations.length > 0) {
            conversations.forEach(conversation => {
                const chatItem = this.createConversationItem({
                    id: conversation.id,
                    name: conversation.name,
                    timestamp: conversation.timestamp,
                    isCurrent: conversation.id === this.currentConversationId
                });
                this.chatHistory.appendChild(chatItem);
            });
        }
    }
    
    createConversationItem(conversation) {
        const item = document.createElement('li');
        item.className = `chat-item${conversation.isCurrent ? ' active' : ''}`;
        item.setAttribute('data-id', conversation.id);
        
        // Format the conversation item with chat icon and name
        item.innerHTML = `
            <div class="chat-item-content">
                <span class="material-icons-round">chat</span>
                <span class="chat-name">${conversation.name}</span>
            </div>
            <div class="chat-actions">
                <button class="chat-action-button rename-chat" title="Rename conversation">
                    <span class="material-icons-round">edit</span>
                </button>
                <button class="chat-action-button delete-chat" title="Delete conversation">
                    <span class="material-icons-round">delete</span>
                </button>
            </div>
        `;
        
        // Add event listeners
        item.addEventListener('click', (e) => {
            // Only switch conversation if not clicking an action button
            if (!e.target.closest('.chat-action-button')) {
                this.switchToConversation(conversation.id);
            }
        });
        
        // Add rename functionality
        const renameButton = item.querySelector('.rename-chat');
        if (renameButton) {
            renameButton.addEventListener('click', (e) => {
                e.stopPropagation();
                this.renameConversation(conversation.id);
            });
        }
        
        // Add delete functionality
        const deleteButton = item.querySelector('.delete-chat');
        if (deleteButton) {
            deleteButton.addEventListener('click', (e) => {
                e.stopPropagation();
                this.confirmDeleteConversation(conversation.id);
            });
        }
        
        return item;
    }
    
    async switchToConversation(conversationId) {
        // Don't switch if it's the same conversation
        if (conversationId === this.currentConversationId) return;
        
        console.log(`Switching from conversation ${this.currentConversationId} to ${conversationId}`);
        
        try {
            // Notify user we're switching conversations
            this.messagingComponent.addInfoMessage(`Switching conversations...`, true);
            
            // STEP 1: Save current conversation state if needed
            if (this.messagingComponent.hasMessages()) {
                try {
                    // Gather current messages from the UI
                    const currentMessages = this.getCurrentMessages();
                    
                    // Only save if we have meaningful content
                    if (currentMessages.length > 0) {
                        console.log(`Saving current conversation state with ${currentMessages.length} messages`);
                        
                        if (this.currentConversationId !== 'current') {
                            // If switching from a saved conversation, update its content
                            this.storageManager.updateConversationContent(this.currentConversationId, currentMessages);
                        } else if (!this.messagingComponent.autoSaveCompleted) {
                            // If we're in a new unsaved conversation, save it first
                            await this.saveCurrentConversation();
                        }
                    }
                } catch (saveError) {
                    console.error("Error saving current conversation before switch:", saveError);
                    // Continue with the switch even if saving fails
                }
            }
            
            // STEP 2: Update UI state first to prevent race conditions
            this.updateActiveConversation(conversationId);
            
            // STEP 3: Reset conversation state
            this.messagingComponent.clearMessages(true);
            
            // STEP 4: Set current conversation ID before loading
            // This prevents auto-save from triggering during load
            this.currentConversationId = conversationId;
            
            // STEP 5: If it's a new conversation, just reset
            if (conversationId === 'new' || conversationId === 'current') {
                // Tell user we're resetting
                this.messagingComponent.addInfoMessage(`Creating new conversation...`, true);
                
                try {
                    await resetConversation();
                    this.currentConversationId = 'current';
                    this.messagingComponent.autoSaveCompleted = false;
                    
                    // Show welcome message
                    const welcomeMessage = document.getElementById('welcomeMessage');
                    if (welcomeMessage) {
                        welcomeMessage.classList.remove('hidden');
                    }
                    
                    // Update the conversation list to show current conversation
                    await this.loadConversationList();
                    
                    // Clear any info messages
                    this.messagingComponent.clearInfoMessages();
                    return;
                } catch (resetError) {
                    console.error("Error resetting conversation on server:", resetError);
                    this.messagingComponent.addInfoMessage(`Failed to reset conversation on server: ${resetError.message}`, false, true);
                    return;
                }
            }
            
            // STEP 6: Load the selected conversation
            console.log(`Loading conversation ${conversationId} from storage`);
            try {
                const conversation = this.storageManager.loadConversation(conversationId);
                
                if (!conversation) {
                    throw new Error(`Conversation ${conversationId} not found`);
                }
                
                // STEP 7: Load the messages into the UI
                this.loadMessagesIntoUI(conversation);
                
                // STEP 8: Mark as existing conversation to prevent auto-save
                this.messagingComponent.autoSaveCompleted = true;
                
                // STEP 9: Update the conversation list to reflect changes
                await this.loadConversationList();
                
                // STEP 10: Clear info messages and inform user
                this.messagingComponent.clearInfoMessages();
                
                // STEP 11: Send a silent reset request to sync server state
                try {
                    await resetConversation();
                    console.log("Server conversation state reset to match loaded conversation");
                } catch (resetError) {
                    console.warn("Could not reset server conversation state, continuing anyway:", resetError);
                }
            } catch (loadError) {
                console.error(`Error loading conversation ${conversationId}:`, loadError);
                this.messagingComponent.addInfoMessage(`Failed to load conversation: ${loadError.message}`, false, true);
                
                // Reset to a safe state
                this.currentConversationId = 'current';
                this.messagingComponent.autoSaveCompleted = false;
                await this.loadConversationList();
            }
        } catch (error) {
            console.error('Failed to switch conversation:', error);
            this.messagingComponent.addInfoMessage(
                'Error: Failed to load conversation. Please try again or start a new one.', false, true
            );
            
            // Reset to a safe state
            this.currentConversationId = 'current';
            this.messagingComponent.autoSaveCompleted = false;
            
            // Update the conversation list
            await this.loadConversationList();
        }
    }
    
    // Helper method to load conversation messages into UI
    loadMessagesIntoUI(conversation) {
        if (conversation.messages && conversation.messages.length > 0) {
            conversation.messages.forEach(message => {
                if (message.role === 'system') return; // Skip system messages
                
                const isUser = message.role === 'user';
                
                // Handle both simple string content and complex content structures
                let content = message.content;
                let hasImage = false;
                
                // Check if content is an array (multimodal content)
                if (Array.isArray(content)) {
                    // Extract text content and check for images
                    const textParts = content.filter(part => part.type === 'text');
                    const imageParts = content.filter(part => part.type === 'image_url');
                    
                    if (textParts.length > 0) {
                        content = textParts[0].text || '';
                    } else {
                        content = '';
                    }
                    
                    hasImage = imageParts.length > 0;
                }
                
                // Add the message to the UI
                const messageElement = this.messagingComponent.messageRenderer.addMessage(content, isUser, hasImage);
                if (messageElement && content) {
                    const bubble = messageElement.querySelector('.message-bubble');
                    if (bubble) {
                        bubble.setAttribute('data-markdown', content);
                        messageElement.setAttribute('data-markdown', content);
                    }
                }
            });
            
            // Hide welcome message
            const welcomeMessage = document.getElementById('welcomeMessage');
            if (welcomeMessage) {
                welcomeMessage.classList.add('hidden');
            }
        }
    }
    
    updateActiveConversation(conversationId) {
        if (!this.chatHistory) return;
        
        // Remove active class from all items
        const items = this.chatHistory.querySelectorAll('.chat-item');
        items.forEach(item => item.classList.remove('active'));
        
        // Add active class to the selected item
        const activeItem = this.chatHistory.querySelector(`[data-id="${conversationId}"]`);
        if (activeItem) {
            activeItem.classList.add('active');
        }
    }
    
    async createNewConversation() {
        try {
            // If current conversation has messages, save it before creating a new one
            if (this.messagingComponent.hasMessages()) {
                try {
                    console.log('Saving current conversation...');
                    
                    // Explicitly call saveCurrentConversation and wait for it to complete
                    const savedConversation = await this.saveCurrentConversation();
                    if (savedConversation) {
                        console.log('Successfully saved current conversation:', savedConversation);
                    } else {
                        console.log('User cancelled saving the conversation');
                    }
                } catch (error) {
                    console.error('Failed to save current conversation, but continuing with new conversation:', error);
                    // Continue even if saving fails
                }
            }
            
            // Now reset the conversation on server
            await resetConversation();
            
            // Clear messages and reset to a fresh conversation
            this.messagingComponent.clearMessages(true);
            
            // Make sure the welcome message is visible
            const welcomeMessage = document.getElementById('welcomeMessage');
            if (welcomeMessage) {
                welcomeMessage.classList.remove('hidden');
            }
            
            // Update the UI to show current conversation as active
            this.currentConversationId = 'current';
            this.updateActiveConversation('current');
            
            // Reset the auto-save flag in messaging component
            if (this.messagingComponent.autoSaveCompleted !== undefined) {
                this.messagingComponent.autoSaveCompleted = false;
            }
            
            // Refresh the conversation list to show the newly saved conversation
            // This will add the "Current Conversation" item since currentConversationId = 'current'
            try {
                await this.loadConversationList();
            } catch (error) {
                console.error('Failed to refresh conversation list:', error);
            }
        } catch (error) {
            console.error('Failed to create new conversation:', error);
            alert('There was an error creating a new conversation. Please try again.');
        }
    }
    
    async saveCurrentConversation() {
        try {
            // Generate default name based on first user message
            let conversationName = `Conversation ${new Date().toLocaleString()}`;
            
            // Get the first message as a default title
            const firstMessage = this.messagingComponent.getFirstUserMessage();
            if (firstMessage) {
                conversationName = firstMessage.substring(0, 30) + (firstMessage.length > 30 ? '...' : '');
            }
            
            // Use the generated name directly without prompting user
            try {
                const messages = this.getCurrentMessages();
                const result = this.storageManager.saveConversation(conversationName, messages);
                console.log('Conversation saved successfully:', result);
                
                // Refresh the list to show the new conversation
                try {
                    await this.loadConversationList();
                } catch (listError) {
                    console.error('Failed to refresh conversation list:', listError);
                }
                
                return result;
            } catch (apiError) {
                console.error('Error saving conversation:', apiError);
                throw apiError;
            }
        } catch (error) {
            console.error('Failed to save conversation:', error);
            return null;
        }
    }
    
    async renameConversation(conversationId) {
        const item = this.chatHistory.querySelector(`[data-id="${conversationId}"]`);
        if (!item) return;
        
        const nameElement = item.querySelector('.chat-name');
        const currentName = nameElement.textContent;
        
        const newName = prompt('Enter a new name for this conversation:', currentName);
        if (!newName || newName === currentName) return;
        
        try {
            const result = this.storageManager.renameConversation(conversationId, newName);
            if (result) {
                nameElement.textContent = newName;
            } else {
                alert('Failed to rename conversation. Please try again.');
            }
        } catch (error) {
            console.error('Failed to rename conversation:', error);
            alert('Failed to rename conversation. Please try again.');
        }
    }
    
    async confirmDeleteConversation(conversationId) {
        if (conversationId === 'current') {
            this.messagingComponent.addInfoMessage('Cannot delete the current conversation.', false);
            return;
        }
        
        if (confirm('Are you sure you want to delete this conversation? This action cannot be undone.')) {
            try {
                // Show deletion in progress
                this.messagingComponent.addInfoMessage(`Deleting conversation...`, true);
                
                // Delete from local storage
                const success = this.storageManager.deleteConversation(conversationId);
                
                if (success) {
                    // If we just deleted the active conversation, switch to new
                    if (conversationId === this.currentConversationId) {
                        console.log('Deleted active conversation, creating new one');
                        await this.createNewConversation();
                    } else {
                        // Otherwise just refresh the list
                        await this.loadConversationList();
                    }
                    
                    // Clear any temporary messages
                    this.messagingComponent.clearTemporaryInfoMessages();
                } else {
                    this.messagingComponent.addInfoMessage('Failed to delete conversation. Please try again.', false, true);
                }
            } catch (error) {
                console.error('Failed to delete conversation:', error);
                this.messagingComponent.addInfoMessage('Failed to delete conversation. Please try again.', false, true);
            }
        }
    }
    
    // Add a new method to rename the current conversation
    async renameCurrentConversation() {
        try {
            // Skip generating new names for already-saved conversations
            if (this.currentConversationId !== 'current') {
                console.log('Skipping auto-rename for existing conversation:', this.currentConversationId);
                return null;
            }
            
            // Generate a name using the first user message
            let conversationName = `Conversation ${new Date().toLocaleString()}`;
            const firstMessage = this.messagingComponent.getFirstUserMessage();
            if (firstMessage) {
                conversationName = firstMessage.substring(0, 30) + (firstMessage.length > 30 ? '...' : '');
            }
            
            // Just update the UI directly without saving to backend yet
            // This avoids creating a duplicate conversation
            const currentItem = this.chatHistory.querySelector('[data-id="current"] .chat-name');
            if (currentItem) {
                currentItem.textContent = conversationName;
                console.log('Current conversation renamed to:', conversationName);
                // No need to refresh the list which would cause duplication
                return { name: conversationName };
            }
            
            return null;
        } catch (error) {
            console.error('Failed to rename conversation:', error);
            throw error;
        }
    }
    
    // Get current message content with improved reliability
    getCurrentMessages() {
        const messages = [];
        try {
            const messageGroups = this.messagingComponent.messagesContainer.querySelectorAll('.message-group');
            
            messageGroups.forEach(group => {
                // Skip the welcome message, tool messages, and info messages
                if (group.classList.contains('welcome-message') || 
                    group.classList.contains('tool-message') ||
                    group.classList.contains('info-message')) {
                    return;
                }
                
                // Determine role
                const isUser = group.classList.contains('user-message');
                const role = isUser ? 'user' : 'assistant';
                
                // Get content - prefer markdown data attribute for the most accurate content
                const markdownContent = group.getAttribute('data-markdown');
                
                if (markdownContent) {
                    messages.push({
                        role: role,
                        content: markdownContent
                    });
                    return;
                }
                
                // Fall back to bubble content if no markdown attribute
                const bubble = group.querySelector('.message-bubble');
                if (bubble) {
                    const bubbleMarkdown = bubble.getAttribute('data-markdown');
                    
                    if (bubbleMarkdown) {
                        messages.push({
                            role: role,
                            content: bubbleMarkdown
                        });
                        return;
                    }
                    
                    // Last resort: use text content
                    const content = bubble.textContent.trim();
                    if (content) {
                        messages.push({
                            role: role,
                            content: content
                        });
                    }
                }
            });
            
            // Validate message structure for proper conversation format
            return this.validateMessageSequence(messages);
            
        } catch (error) {
            console.error('Error getting current messages:', error);
        }
        
        return messages;
    }
    
    // Validate and fix message sequence if needed
    validateMessageSequence(messages) {
        if (messages.length === 0) return messages;
        
        const validMessages = [];
        
        // If first message isn't from user, add a placeholder
        if (messages[0].role !== 'user') {
            validMessages.push({
                role: 'user',
                content: 'Hello'
            });
        }
        
        // Add all messages, ensuring proper alternation
        let lastRole = validMessages.length > 0 ? validMessages[0].role : null;
        
        for (const message of messages) {
            // Only add if this creates a valid pair pattern
            if ((lastRole === 'user' && message.role === 'assistant') ||
                (lastRole === 'assistant' && message.role === 'user') ||
                (lastRole === null && message.role === 'user')) {
                validMessages.push(message);
                lastRole = message.role;
            } else if (lastRole === message.role) {
                // Combine with previous message of same role instead of skipping
                const prevMessage = validMessages[validMessages.length - 1];
                prevMessage.content += '\n\n' + message.content;
            }
        }
        
        // Ensure we end with an assistant message (for better UI)
        if (validMessages.length > 0 && validMessages[validMessages.length - 1].role === 'user') {
            validMessages.push({
                role: 'assistant',
                content: 'I was in the middle of responding...'
            });
        }
        
        return validMessages;
    }
}