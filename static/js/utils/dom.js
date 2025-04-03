/**
 * Utility functions for DOM manipulation
 */

/**
 * Adjust the textarea height based on content
 * @param {HTMLTextAreaElement} textarea - The textarea element
 * @param {HTMLButtonElement} sendButton - The send button to enable/disable
 */
export function adjustTextareaHeight(textarea, sendButton) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    
    // Enable/disable send button based on input
    if (sendButton) {
        sendButton.disabled = textarea.value.trim() === '';
    }
}

/**
 * Scroll the container to the bottom
 * @param {HTMLElement} container - The container to scroll
 */
export function scrollToBottom(container) {
    container.scrollTop = container.scrollHeight;
}
