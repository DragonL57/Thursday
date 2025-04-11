import { scrollToBottom } from '../../utils/dom.js';

export class MessageRenderer {
    constructor(messagingComponent) {
        this.messagingComponent = messagingComponent;
        // Add a tracking Set to prevent duplicate event listeners
        this._processedCopyButtons = new Set();
        // Track active tool status indicators
        this._activeToolIndicators = new Map();
        // Add a tracking set for retry buttons
        this._processedRetryButtons = new Set();
    }
    
    // Add message to the UI
    addMessage(content, isUser = false, hasImage = false) {
        const component = this.messagingComponent;
        
        // Hide welcome message if it exists
        const welcomeMessage = document.getElementById('welcomeMessage');
        if (welcomeMessage) {
            welcomeMessage.classList.add('hidden');
        }
        
        // Skip creating empty user messages without images
        if (isUser && !content && !hasImage && !component.currentImageData) {
            console.log('Skipping empty user message without image');
            return null;
        }
        
        const messageGroup = document.createElement('div');
        messageGroup.className = isUser ? 'message-group user-message' : 'message-group assistant-message';
        
        // Create message containers
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        const contentContainer = document.createElement('div');
        contentContainer.className = 'message-content-container';
        
        const messageBubble = document.createElement('div');
        messageBubble.className = 'message-bubble';
        
        // Add text content if available
        if (content) {
            if (isUser) {
                // For user messages, use a simple paragraph
                const textParagraph = document.createElement('p');
                textParagraph.textContent = content;
                messageBubble.appendChild(textParagraph);
            } else {
                // For assistant messages, render markdown
                messageBubble.innerHTML = marked.parse(this.preserveLineBreaks(content));
            }
        }
        
        // Add image if exists (with improved styling)
        if (isUser && hasImage && component.currentImageData) {
            const messageImage = document.createElement('div');
            messageImage.className = 'message-image';
            
            const img = document.createElement('img');
            img.src = component.currentImageData;
            img.alt = 'Attached image';
            img.loading = 'lazy';
            
            messageImage.appendChild(img);
            messageBubble.appendChild(messageImage);
        } else if (hasImage && Array.isArray(content)) {
            // Handle multimodal message from assistant (array format)
            const imageParts = content.filter(part => 
                part.type === 'image_url' || 
                (part.image_url && typeof part.image_url === 'object')
            );
            
            if (imageParts.length > 0) {
                imageParts.forEach(imagePart => {
                    const imageUrl = imagePart.image_url?.url || imagePart.url;
                    if (imageUrl) {
                        const messageImage = document.createElement('div');
                        messageImage.className = 'message-image';
                        
                        const img = document.createElement('img');
                        img.src = imageUrl;
                        img.alt = 'Image';
                        img.loading = 'lazy';
                        
                        messageImage.appendChild(img);
                        messageBubble.appendChild(messageImage);
                    }
                });
            }
        }
        
        // Assemble the DOM structure
        contentContainer.appendChild(messageBubble);
        messageContent.appendChild(contentContainer);
        messageGroup.appendChild(messageContent);
        
        // IMPORTANT: Remove the duplicate copy button creation here - we'll add it later with addCopyButton
        // DO NOT ADD COPY BUTTON HERE
        
        // Add to messages container
        component.messagesContainer.appendChild(messageGroup);
        
        // Store markdown content
        if (content) {
            messageGroup.setAttribute('data-markdown', content);
        }
        
        // Apply syntax highlighting and LaTeX rendering
        if (!isUser) {
            messageBubble.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
            
            renderMathInElement(messageBubble, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "$", right: "$", display: false}
                ]
            });
        }
        
        // Set up copy button - we use this single call to prevent duplicates
        this.addCopyButton(messageGroup, contentContainer);
        
        // Scroll to bottom
        scrollToBottom(component.messagesContainer);
        
        // If assistant message, save reference for updating
        if (!isUser) {
            component.currentAssistantMessage = messageGroup;
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
    updateAssistantMessage(content, isStreaming = false) {
        const component = this.messagingComponent;
        if (!component.currentAssistantMessage) return;
        
        const messageBubble = component.currentAssistantMessage.querySelector('.message-bubble');
        if (!messageBubble) return;
        
        // Remove thinking indicator if it exists
        const thinkingIndicator = messageBubble.querySelector('.message-thinking');
        if (thinkingIndicator) {
            thinkingIndicator.remove();
        }
        
        // If streaming starts, remove all tool indicators
        if (isStreaming && content && content.length > 0) {
            this.clearToolStatusIndicators();
        }
        
        // Store any existing buttons before updating content
        const buttonsContainer = component.currentAssistantMessage.querySelector('.message-buttons-container');
        
        if (isStreaming) {
            // When streaming, always use the provided content directly
            component.currentAssistantMessage.setAttribute('data-markdown', content);
            messageBubble.setAttribute('data-content', content);
            
            try {
                // Render markdown directly without any preprocessing
                let markdownContent = messageBubble.querySelector('.markdown-content');
                
                if (!markdownContent) {
                    markdownContent = document.createElement('div');
                    markdownContent.className = 'markdown-content';
                    messageBubble.appendChild(markdownContent);
                }
                
                // Check for duplicated content before rendering
                if (this._isDuplicatedContent(content)) {
                    const fixedContent = this._removeDuplicateContent(content);
                    markdownContent.innerHTML = marked.parse(fixedContent);
                } else {
                    markdownContent.innerHTML = marked.parse(content);
                }
                
                // Apply formatting
                this._applyFormatting(markdownContent);
            } catch (error) {
                console.error('Error parsing markdown:', error);
                messageBubble.textContent = content;
            }
        } else {
            // Original non-streaming behavior
            let fullContent = component.currentAssistantMessage.getAttribute('data-markdown') || '';
            
            // Track the length before adding the new content
            const previousLength = fullContent.length;
            
            if (fullContent.length === 0) {
                fullContent = content;
            } else if (!fullContent.includes(content)) {
                fullContent += content;
            }
            
            // Always update data attributes
            component.currentAssistantMessage.setAttribute('data-markdown', fullContent);
            messageBubble.setAttribute('data-content', fullContent);
            
            // Only update UI if content changed
            const contentChanged = fullContent.length > previousLength || previousLength === 0;
            
            if (contentChanged) {
                try {
                    messageBubble.innerHTML = `<div class="markdown-content">${marked.parse(fullContent)}</div>`;
                    this._applyFormatting(messageBubble);
                } catch (error) {
                    console.error('Error parsing markdown:', error);
                    messageBubble.textContent = fullContent;
                }
            }
        }
        
        // Re-add copy button if this is an assistant message
        const contentContainer = component.currentAssistantMessage.querySelector('.message-content-container');
        if (contentContainer && !buttonsContainer) {
            // Check if this is an actual assistant message (not a tool message)
            if (!component.currentAssistantMessage.classList.contains('tool-message') && 
                !component.currentAssistantMessage.hasAttribute('data-tool-container')) {
                this.addCopyButton(component.currentAssistantMessage, contentContainer);
            }
        }
        
        scrollToBottom(component.messagesContainer);
    }
    
    // Special method to fix list rendering issues
    _fixListFormatting(element) {
        // Find all potential list items that might be rendered incorrectly
        const listItems = element.querySelectorAll('p');
        
        listItems.forEach(item => {
            // Check if this paragraph actually starts with a list marker
            const text = item.textContent || '';
            if (text.trim().startsWith('- ') || text.trim().match(/^\d+\.\s/)) {
                // This should be a list item - fix it
                const listType = text.trim().startsWith('- ') ? 'ul' : 'ol';
                
                // Create a list element
                const list = document.createElement(listType);
                
                // Create a list item with the text (removing the marker)
                const li = document.createElement('li');
                if (text.trim().startsWith('- ')) {
                    li.textContent = text.trim().substring(2);
                } else {
                    li.textContent = text.trim().replace(/^\d+\.\s/, '');
                }
                
                // Replace the paragraph with a proper list
                list.appendChild(li);
                
                // If possible, replace the paragraph with the list
                if (item.parentNode) {
                    item.parentNode.replaceChild(list, item);
                }
            }
        });
    }
    
    // Apply formatting including code highlighting and math rendering
    _applyFormatting(element) {
        // Apply code syntax highlighting
        element.querySelectorAll('pre code').forEach((block) => {
            try {
                // Check for encoding gibberish in tool results
                if (block.closest('.tool-result') && 
                    this._detectEncodingIssues(block.textContent)) {
                    
                    const toolResult = block.closest('.tool-result');
                    if (toolResult) {
                        toolResult.classList.add('encoding-error');
                    }
                }
                
                hljs.highlightElement(block);
            } catch (e) {
                console.warn('Error highlighting code block:', e);
            }
        });
        
        // Apply math rendering
        try {
            if (typeof renderMathInElement === 'function') {
                renderMathInElement(element, {
                    delimiters: [
                        {left: "$$", right: "$$", display: true},
                        {left: "$", right: "$$", display: false},
                        {left: "\\[", right: "\\]", display: true},
                        {left: "\\(", right: "\\)", display: false}
                    ],
                    throwOnError: false,
                    strict: false
                });
            }
        } catch (e) {
            console.warn('Error rendering LaTeX:', e);
        }
    }
    
    // Escape dollar signs in monetary amounts to prevent LaTeX processing
    escapeDollarSigns(content) {
        // Look for patterns like $100, $433.9 billion, etc. and escape the dollar sign
        return content.replace(/\$(\d+(\.\d+)?\s*(billion|million|trillion|thousand|B|M|T|K)?)/g, '\\$$$1');
    }
    
    // Helper method to determine if a message should have a copy button
    _shouldShowCopyButton(messageGroup, messageElement) {
        // Never show copy button on tool messages or containers
        if (messageGroup.classList.contains('tool-message') || 
            messageGroup.hasAttribute('data-tool-container') ||
            messageGroup.hasAttribute('data-no-copy') ||
            messageElement.hasAttribute('data-no-copy')) {
            return false;
        }

        // Never show copy button if any parent is a tool message
        let parent = messageElement.parentElement;
        while (parent) {
            if (parent.classList.contains('tool-message') || 
                parent.hasAttribute('data-tool-container') ||
                parent.hasAttribute('data-no-copy')) {
                return false;
            }
            parent = parent.parentElement;
        }

        // Never show copy button if this is a system message or info message
        if (messageGroup.classList.contains('info-message') ||
            messageGroup.classList.contains('system-message')) {
            return false;
        }

        // Never show copy button if the message is empty
        const content = messageGroup.getAttribute('data-markdown') || messageElement.textContent;
        if (!content || content.trim().length === 0) {
            return false;
        }

        // Only show copy button for user messages and assistant messages
        return messageGroup.classList.contains('user-message') || 
               messageGroup.classList.contains('assistant-message');
    }

    // Add the copy button only to appropriate messages
    addCopyButton(messageGroup, messageElement) {
        // First check if this message should have a copy button
        if (!this._shouldShowCopyButton(messageGroup, messageElement)) {
            return;
        }
        
        // Store the raw markdown content as a data attribute for later copying
        const markdownContent = messageGroup.getAttribute('data-markdown') || messageElement.textContent;
        messageGroup.setAttribute('data-markdown', markdownContent);
        
        // Create a unique ID if not already present
        if (!messageGroup.id) {
            messageGroup.id = 'msg-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);
        }
        
        // Create or get the buttons container
        let buttonsContainer = messageElement.querySelector('.message-buttons-container');
        if (!buttonsContainer) {
            buttonsContainer = document.createElement('div');
            buttonsContainer.className = 'message-buttons-container';
            messageElement.appendChild(buttonsContainer);
        }
        
        // Add retry button only for user messages
        if (messageGroup.classList.contains('user-message')) {
            const retryButton = this.createRetryButton(messageGroup);
            if (retryButton) {
                buttonsContainer.appendChild(retryButton);
            }
        }
        
        // Check if copy button already exists
        let copyButton = buttonsContainer.querySelector('.copy-markdown-button');
        if (copyButton) {
            return; // Don't add another copy button
        }
        
        // Create copy button
        copyButton = document.createElement('div');
        copyButton.className = 'copy-markdown-button';
        copyButton.innerHTML = '<span class="material-icons-round">content_copy</span>';
        copyButton.setAttribute('title', 'Copy message');
        
        const buttonId = `copy-btn-${messageGroup.id}`;
        copyButton.setAttribute('data-btn-id', buttonId);
        
        // Only add event listener if not already processed
        if (!this._processedCopyButtons.has(buttonId)) {
            this._processedCopyButtons.add(buttonId);
            copyButton.addEventListener('click', (e) => {
                e.stopPropagation();
                e.stopImmediatePropagation();
                console.log('Copy button clicked:', messageGroup.id);
                this.copyToClipboard(messageGroup);
            });
        }
        
        buttonsContainer.appendChild(copyButton);
    }

    // Create a retry button for user messages
    createRetryButton(messageGroup) {
        const retryButton = document.createElement('div');
        retryButton.className = 'retry-button';
        retryButton.innerHTML = '<span class="material-icons-round">refresh</span>';
        retryButton.setAttribute('title', 'Regenerate response');
        
        const buttonId = `retry-btn-${messageGroup.id}`;
        retryButton.setAttribute('data-btn-id', buttonId);
        
        // Only add event listener if not already processed
        if (!this._processedRetryButtons.has(buttonId)) {
            this._processedRetryButtons.add(buttonId);
            
            retryButton.addEventListener('click', async (e) => {
                e.stopPropagation(); // Prevent event bubbling
                e.stopImmediatePropagation(); // Stop immediate propagation
                console.log('Retry button clicked:', messageGroup.id);
                
                // Get the message content - with enhanced extraction to prevent duplicates
                let content;
                
                // First try to get the markdown attribute which should be most accurate
                if (messageGroup.hasAttribute('data-markdown')) {
                    content = messageGroup.getAttribute('data-markdown');
                    console.log('Got message content from data-markdown attribute');
                } 
                // Fall back to paragraph text content which is how user messages are usually formatted
                else {
                    const paragraphElement = messageGroup.querySelector('.message-bubble p');
                    if (paragraphElement) {
                        content = paragraphElement.textContent.trim();
                        console.log('Got message content from paragraph element');
                    } 
                    // Last resort - get from entire message bubble
                    else {
                        const messageBubble = messageGroup.querySelector('.message-bubble');
                        content = messageBubble ? messageBubble.textContent.trim() : '';
                        console.log('Got message content from message bubble');
                    }
                }
                
                if (!content) {
                    console.error('No content found for retry');
                    return;
                }
                
                // Enhanced duplication cleaning
                // First check for simple duplicated line - very common in chat UIs
                if (content.includes('\n\n')) {
                    const lines = content.split('\n\n').filter(line => line.trim());
                    if (lines.length >= 2 && this.stringSimilarity(lines[0], lines[1]) > 0.9) {
                        content = lines[0]; // Keep just the first instance
                        console.log('Detected and fixed exact duplicate lines');
                    }
                }
                
                // Then apply general duplicate cleaning
                content = this.removeDuplicateContent(content);
                console.log(`Cleaned message for retry: "${content.substring(0, 50)}${content.length > 50 ? '...' : ''}"`);
                
                // Check if an image was attached to this message
                const messageImage = messageGroup.querySelector('.message-image img');
                let imageData = null;
                
                if (messageImage && messageImage.src) {
                    // If the image is a base64 data URL, use it directly
                    if (messageImage.src.startsWith('data:')) {
                        imageData = messageImage.src;
                    }
                }
                
                // Find and remove the next assistant message if it exists
                let nextElement = messageGroup.nextElementSibling;
                while (nextElement) {
                    if (nextElement.classList.contains('assistant-message') || 
                        nextElement.classList.contains('tool-message') ||
                        nextElement.classList.contains('info-message')) {
                        
                        nextElement.remove();
                        nextElement = messageGroup.nextElementSibling;
                    } else {
                        break;
                    }
                }
                
                // Resend the message
                try {
                    // Add a temporary loading message
                    this.messagingComponent.addInfoMessage('Regenerating response...', true);
                    
                    // Pass true as the third parameter (skipUserMessage) AND fourth parameter (isRetry)
                    await this.messagingComponent.sendMessage(content, imageData, true, true);
                    
                    // Clear the temporary message
                    this.messagingComponent.clearTemporaryInfoMessages();
                } catch (error) {
                    console.error('Error regenerating response:', error);
                    this.messagingComponent.addInfoMessage('Failed to regenerate response. Please try again.', false, true);
                }
            });
        }
        
        return retryButton;
    }

    // Completely rewritten copy function specifically for Linux compatibility
    copyToClipboard(messageGroup) {
        console.log('Copy function called for:', messageGroup.id || 'unknown-id');
        
        // Debounce to prevent accidental double execution
        if (messageGroup._copyInProgress) {
            console.log('Copy operation already in progress, preventing duplicate execution');
            return;
        }
        
        // Set a temporary flag to prevent duplicate operations
        messageGroup._copyInProgress = true;
        setTimeout(() => { messageGroup._copyInProgress = false; }, 500);
        
        // Get the content from the data attribute - only from the message group
        const markdownContent = messageGroup.getAttribute('data-markdown');
        
        if (!markdownContent) {
            console.error('No markdown content found to copy. data-markdown attribute is missing or empty.');
            return;
        }
        
        // Check if content appears duplicated and fix it
        const cleanedContent = this.removeDuplicateContent(markdownContent);
        
        // Make the log clearer to avoid confusion about duplication
        const previewLength = 30;
        console.log(
            `Content to copy (${cleanedContent.length} chars) - PREVIEW: "${
                cleanedContent.substring(0, previewLength)
            }${cleanedContent.length > previewLength ? '...' : ''}"`
        );
        
        try {
            console.log('Try direct clipboard API first (most reliable)');
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(cleanedContent)
                    .then(() => {
                        console.log('✅ Copy succeeded using Clipboard API');
                        this.showCopyFeedback(messageGroup);
                    })
                    .catch(err => {
                        console.error('❌ Clipboard API failed, error:', err);
                        console.log('Falling back to execCommand method');
                        this.fallbackCopyMethod(messageGroup, cleanedContent);
                    });
            } else {
                console.log('Clipboard API not available, using fallback method');
                this.fallbackCopyMethod(messageGroup, cleanedContent);
            }
        } catch (err) {
            console.error('❌ Unexpected error in copyToClipboard:', err);
            this.showManualCopyDialog(cleanedContent);
        }
    }
    
    // New helper function to clean up any duplicated content
    removeDuplicateContent(content) {
        if (!content) return '';
        
        // Check for exact duplicates (whole content repeated)
        const halfLength = Math.floor(content.length / 2);
        if (content.length % 2 === 0 && content.substring(0, halfLength) === content.substring(halfLength)) {
            console.log('Detected exact duplicate content, removing duplicate half');
            return content.substring(0, halfLength);
        }
        
        // Check for duplicated lines (common in chat interfaces)
        const lines = content.split('\n').filter(line => line.trim());
        if (lines.length >= 2) {
            // Check for immediate duplicated lines - very common pattern
            if (lines[0] === lines[1]) {
                console.log('Found duplicated first line, removing duplicate');
                return lines[0];
            }
        }
        
        // Check for common cases - entire paragraphs duplicated adjacently
        const paragraphs = content.split('\n\n');
        if (paragraphs.length > 1) {
            const uniqueParagraphs = [];
            let prevParagraph = '';
            
            for (const paragraph of paragraphs) {
                // Skip empty paragraphs
                if (!paragraph.trim()) {
                    uniqueParagraphs.push(paragraph);
                    continue;
                }
                
                // Skip if this paragraph is very similar to the previous one
                if (this.stringSimilarity(paragraph, prevParagraph) >= 0.9) {
                    console.log('Skipping duplicate paragraph');
                    continue;
                }
                
                uniqueParagraphs.push(paragraph);
                prevParagraph = paragraph;
            }
            
            return uniqueParagraphs.join('\n\n');
        }
        
        return content;
    }
    
    // Helper method to calculate string similarity (0-1 where 1 is identical)
    stringSimilarity(s1, s2) {
        if (s1 === s2) return 1.0;
        if (!s1 || !s2) return 0.0;
        
        // Simple similarity based on length for efficiency
        const maxLength = Math.max(s1.length, s2.length);
        if (maxLength === 0) return 1.0;
        
        // Calculate Levenshtein distance (simplified)
        let distance = 0;
        const minLength = Math.min(s1.length, s2.length);
        
        for (let i = 0; i < minLength; i++) {
            if (s1[i] !== s2[i]) distance++;
        }
        
        // Add difference in length
        distance += Math.abs(s1.length - s2.length);
        
        // Return similarity score
        return 1.0 - (distance / maxLength);
    }
    
    // Separate fallback method for better organization
    fallbackCopyMethod(messageGroup, markdownContent) {
        console.log('Starting fallback copy method');
        
        // Create a visible textarea temporarily
        const textarea = document.createElement('textarea');
        textarea.value = markdownContent;
        
        // Style for better visibility during debugging
        textarea.style.position = 'fixed';
        textarea.style.top = '20px';
        textarea.style.left = '20px';
        textarea.style.width = '50px';
        textarea.style.height = '50px';
        textarea.style.padding = '5px';
        textarea.style.border = '2px solid red'; // Visible for debugging
        textarea.style.zIndex = '9999';
        
        console.log('Appending textarea to document body');
        document.body.appendChild(textarea);
        
        try {
            // Focus the element first
            console.log('Focusing textarea');
            textarea.focus();
            
            console.log('Selecting text in textarea');
            textarea.select();
            
            // Check if text is actually selected
            const selectionSuccessful = document.getSelection().toString().length > 0;
            console.log('Selection successful?', selectionSuccessful);
            
            // Execute the copy command
            console.log('Executing copy command');
            const copySuccessful = document.execCommand('copy');
            console.log('Copy command result:', copySuccessful ? '✅ Success' : '❌ Failed');
            
            if (copySuccessful) {
                this.showCopyFeedback(messageGroup);
            } else {
                console.log('execCommand failed, showing manual dialog');
                this.showManualCopyDialog(markdownContent);
            }
        } catch (err) {
            console.error('❌ Error in fallback copy method:', err);
            this.showManualCopyDialog(markdownContent);
        } finally {
            console.log('Removing textarea from DOM');
            // Leave it in DOM slightly longer to ensure copy completes
            setTimeout(() => {
                if (document.body.contains(textarea)) {
                    document.body.removeChild(textarea);
                }
            }, 100);
        }
    }

    // Show feedback when copy succeeds
    showCopyFeedback(messageGroup) {
        console.log('Showing copy feedback');
        // Create a new feedback element each time
        const button = messageGroup.querySelector('.copy-markdown-button');
        if (!button) return;
        
        // Remove any existing feedback elements
        const existingFeedback = button.querySelector('.copy-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }
        
        // Create and append new feedback element with inline styles for reliability
        const feedback = document.createElement('div');
        feedback.className = 'copy-feedback';
        feedback.textContent = 'Copied!';
        feedback.style.position = 'absolute';
        feedback.style.top = '-20px';
        feedback.style.left = '50%';
        feedback.style.transform = 'translateX(-50%) translateY(0)';
        feedback.style.backgroundColor = 'var(--primary-color, #10a37f)';
        feedback.style.color = 'white';
        feedback.style.padding = '2px 6px';
        feedback.style.borderRadius = '4px';
        feedback.style.fontSize = '0.7rem';
        feedback.style.opacity = '0';
        feedback.style.transition = 'all 0.2s ease';
        
        button.appendChild(feedback);
        
        // Force a reflow to ensure the transition works
        void feedback.offsetWidth;
        
        // Show the feedback
        feedback.style.opacity = '1';
        feedback.style.transform = 'translateX(-50%) translateY(-80%)';
        
        // Hide and remove after delay
        setTimeout(() => {
            feedback.style.opacity = '0';
            setTimeout(() => {
                if (button.contains(feedback)) {
                    button.removeChild(feedback);
                }
            }, 300);
        }, 1500);
    }

    // Show manual copy dialog when automatic methods fail
    showManualCopyDialog(markdownContent) {
        const modal = document.createElement('div');
        modal.style.position = 'fixed';
        modal.style.left = '0';
        modal.style.top = '0';
        modal.style.width = '100%';
        modal.style.height = '100%';
        modal.style.backgroundColor = 'rgba(0,0,0,0.7)';
        modal.style.zIndex = '10000';
        modal.style.display = 'flex';
        modal.style.alignItems = 'center';
        modal.style.justifyContent = 'center';
        
        const content = document.createElement('div');
        content.style.backgroundColor = 'var(--bg-color, white)';
        content.style.color = 'var(--text-color, black)';
        content.style.padding = '20px';
        content.style.borderRadius = '8px';
        content.style.width = '80%';
        content.style.maxWidth = '800px';
        content.style.maxHeight = '80%';
        content.style.overflow = 'auto';
        
        content.innerHTML = `
            <h3 style="margin-top:0">Copy this text:</h3>
            <p style="margin:0 0 10px">Select all text (Ctrl+A) and copy (Ctrl+C)</p>
            <textarea style="width:100%; height:200px; margin-bottom:10px; padding:10px; border:1px solid #ccc; border-radius:4px; background: var(--bg-secondary, white); color: var(--text-color, black);">${markdownContent}</textarea>
            <div style="text-align:right">
                <button style="padding:8px 16px; background:var(--primary-color, #10a37f); color:white; border:none; border-radius:4px; cursor:pointer">Close</button>
            </div>
        `;
        
        modal.appendChild(content);
        document.body.appendChild(modal);
        
        // Select all text in the textarea
        const modalTextarea = modal.querySelector('textarea');
        modalTextarea.focus();
        modalTextarea.select();
        
        // Try to copy again when the textarea is clicked
        modalTextarea.addEventListener('click', () => {
            modalTextarea.select();
            try {
                document.execCommand('copy');
            } catch (e) {
                console.error('Secondary copy attempt failed:', e);
            }
        });
        
        // Close button event
        modal.querySelector('button').addEventListener('click', () => {
            document.body.removeChild(modal);
        });
    }

    // Add tool status indicator to show which tool is currently running
    addToolStatusIndicator(toolCall) {
        const component = this.messagingComponent;
        
        // Initialize assistant message if it doesn't exist yet
        if (!component.currentAssistantMessage) {
            console.log("Creating new assistant message bubble for tool status");
            component.currentAssistantMessage = this.addMessage('', false);
        }
        
        // Check if we already have an indicator for this tool call
        if (this._activeToolIndicators.has(toolCall.id)) {
            return this._activeToolIndicators.get(toolCall.id);
        }
        
        // Create a virtual indicator object for tracking (but don't show in UI)
        const virtualIndicator = { 
            id: toolCall.id, 
            name: toolCall.name,
            parentNode: null,
            classList: { 
                add: () => {}, 
                remove: () => {} 
            }
        };
        
        // Store in our map for later reference
        this._activeToolIndicators.set(toolCall.id, virtualIndicator);
        
        // Return the virtual indicator object
        return virtualIndicator;
    }

    // Update tool status indicator (e.g., when tool completes)
    updateToolStatusIndicator(toolCall) {
        if (!this._activeToolIndicators.has(toolCall.id)) {
            return;
        }
        
        // Get the indicator (real or virtual)
        const indicator = this._activeToolIndicators.get(toolCall.id);
        
        // Mark as completed
        if (toolCall.status === 'completed' || toolCall.status === 'error') {
            // If the indicator has DOM methods, use them
            if (indicator.classList && typeof indicator.classList.add === 'function') {
                indicator.classList.add('completed');
            }
            
            // Remove from tracking after a delay
            setTimeout(() => {
                this._activeToolIndicators.delete(toolCall.id);
            }, 500);
        }
    }

    // Clear all tool status indicators
    clearToolStatusIndicators() {
        // Just clear the map - no need to remove elements since they're virtual
        this._activeToolIndicators.clear();
    }

    // Add a helper method to detect duplicated content
    _isDuplicatedContent(content) {
        if (!content || content.length < 10) return false;
        
        // Look for repeated phrases (more than 10 chars) that appear consecutively
        const halfLength = Math.floor(content.length / 2);
        if (content.length > 20 && content.substring(0, halfLength) === content.substring(halfLength, halfLength*2)) {
            return true;
        }
        
        // Look for repeated sentences
        const sentences = content.split('. ');
        if (sentences.length >= 2) {
            // Check if any sentence is repeated immediately after itself
            for (let i = 0; i < sentences.length - 1; i++) {
                if (sentences[i].length > 10 && sentences[i] === sentences[i+1]) {
                    return true;
                }
            }
        }
        
        return false;
    }

    // Add a helper method to detect encoding issues
    _detectEncodingIssues(content) {
        if (!content || typeof content !== 'string') return false;
        
        // Skip short content
        if (content.length < 50) return false;
        
        // Take a sample from the beginning
        const sample = content.substring(0, 300);
        
        // Count unusual characters (non-ASCII and not common punctuation)
        const unusualChars = sample.replace(/[\x20-\x7E\s\n\r\t]/g, '').length;
        const ratio = unusualChars / sample.length;
        
        // Look for patterns that indicate gibberish
        const hasRandomPunctuation = /[^\w\s\n\r\t]{5,}/g.test(sample);
        const hasUnreadableSequences = /[\x00-\x1F\x7F-\xFF]{5,}/g.test(sample);
        
        // Check for replacement characters which indicate encoding problems
        const replacementCharRatio = (sample.match(/�/g) || []).length / sample.length;
        
        // Check if content has very few spaces (unusual for natural text)
        const spaceRatio = (sample.match(/\s/g) || []).length / sample.length;
        const hasAbnormalSpacing = spaceRatio < 0.05 && sample.length > 50;
        
        // Consider it an encoding issue if:
        // 1. There's a high ratio of unusual characters
        // 2. There are sequences of random punctuation or unreadable characters
        // 3. There are many replacement characters
        // 4. The text has abnormally low spacing
        return ratio > 0.2 || 
               hasRandomPunctuation || 
               hasUnreadableSequences || 
               replacementCharRatio > 0.05 ||
               hasAbnormalSpacing;
    }
}
