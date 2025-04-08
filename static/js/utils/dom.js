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
 * Scroll an element to the bottom with smooth animation
 * @param {HTMLElement} element - The element to scroll
 * @param {boolean} force - Force immediate scroll without animation for large content changes
 */
export function scrollToBottom(element, force = false) {
    if (!element) return;
    
    const scrollOptions = {
        top: element.scrollHeight,
        behavior: force ? 'auto' : 'smooth'
    };
    
    // Check if we need to scroll (only if near bottom already or force=true)
    const isNearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 100;
    
    if (isNearBottom || force) {
        try {
            element.scrollTo(scrollOptions);
        } catch (e) {
            // Fallback for browsers that don't support smooth scrolling
            element.scrollTop = element.scrollHeight;
        }
    }
}

/**
 * Adds auto-scroll behavior to an element based on content changes
 * @param {HTMLElement} element - The element to observe
 * @param {number} threshold - Distance from bottom to trigger auto-scroll (pixels)
 */
export function enableAutoScroll(element, threshold = 100) {
    if (!element || !window.MutationObserver) return;
    
    // Track if user is manually scrolling
    let userScrolling = false;
    
    // Start observing content changes
    const observer = new MutationObserver((mutations) => {
        if (!userScrolling) {
            const isNearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < threshold;
            
            if (isNearBottom) {
                // Wait a tiny bit for the DOM to settle
                setTimeout(() => {
                    scrollToBottom(element);
                }, 10);
            }
        }
    });
    
    // Observe any changes to the element's children or subtree
    observer.observe(element, { 
        childList: true, 
        subtree: true,
        characterData: true,
        attributes: true
    });
    
    // Detect when user is manually scrolling
    element.addEventListener('mousewheel', () => {
        userScrolling = true;
        // Reset after a short delay of inactivity
        clearTimeout(element._scrollTimer);
        element._scrollTimer = setTimeout(() => {
            userScrolling = false;
        }, 500);
    }, { passive: true });
    
    // Also monitor touch events for mobile
    element.addEventListener('touchmove', () => {
        userScrolling = true;
        clearTimeout(element._scrollTimer);
        element._scrollTimer = setTimeout(() => {
            userScrolling = false;
        }, 500);
    }, { passive: true });
    
    // Initial scroll to bottom
    scrollToBottom(element);
    
    // Return the observer so it can be disconnected later if needed
    return observer;
}
