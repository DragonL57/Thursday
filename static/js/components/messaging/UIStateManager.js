import { abortCurrentRequest } from '../../utils/api.js';

export class UIStateManager {
    constructor(messagingComponent) {
        this.messagingComponent = messagingComponent;
    }
    
    // Set UI state for generating/not generating
    setGeneratingState(isGenerating) {
        const component = this.messagingComponent;
        component.isProcessing = isGenerating;
        
        // Update input field state
        component.userInput.disabled = isGenerating;
        const inputWrapper = component.userInput.closest('.input-wrapper');
        if (isGenerating) {
            inputWrapper.classList.add('generating');
        } else {
            inputWrapper.classList.remove('generating');
        }
        
        // Update button appearance
        if (isGenerating) {
            component.sendButton.classList.remove('send-button');
            component.sendButton.classList.add('stop-button');
            component.sendButton.querySelector('.material-icons-round').textContent = 'close';
            component.sendButton.title = 'Stop generation';
            // Explicitly enable the button when in stop mode
            component.sendButton.disabled = false;
            // Force enable with a small delay to ensure it takes effect
            setTimeout(() => {
                component.sendButton.disabled = false;
            }, 10);
        } else {
            component.sendButton.classList.remove('stop-button');
            component.sendButton.classList.add('send-button');
            component.sendButton.querySelector('.material-icons-round').textContent = 'send';
            component.sendButton.title = 'Send message';
            component.sendButton.disabled = !component.userInput.value.trim() && !component.currentImageData;
        }
        
        // Hide the standalone loading indicator
        component.loadingIndicator.classList.add('hidden');
    }
    
    // Stop ongoing generation
    stopGeneration() {
        // Abort the current API request
        abortCurrentRequest();
        
        // Reset UI state
        this.setGeneratingState(false);
        
        // Only add a note that generation was stopped if the message is still being generated
        // and doesn't already have a stopped note
        if (this.messagingComponent.currentAssistantMessage && 
            this.messagingComponent.isProcessing) {
            
            const messageBubble = this.messagingComponent.currentAssistantMessage.querySelector('.message-bubble');
            if (messageBubble && !messageBubble.querySelector('.generation-stopped-note')) {
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
        
        // Clear reference to current assistant message to prevent it from getting a stopped note later
        this.messagingComponent.currentAssistantMessage = null;
    }
}
