/**
 * Utility for exporting chat as PDF
 */

export class PDFExporter {
    constructor(messagesContainer) {
        this.messagesContainer = messagesContainer;
    }

    /**
     * Export chat to PDF using the browser's print functionality
     */
    exportToPDF() {
        try {
            console.log("Starting PDF export process");
            
            // Get the current theme (dark/light mode)
            const isDarkMode = document.body.classList.contains('dark-mode');
            
            // Prepare HTML content for print
            const content = this._prepareContentForPrint(isDarkMode);
            
            // Create a new window for printing with more explicit settings
            const printWindow = window.open('', '_blank', 'width=800,height=600,toolbar=0,menubar=0,location=0');
            if (!printWindow) {
                alert('Please allow pop-ups to export chat as PDF');
                return;
            }
            
            // Set document.title so the PDF gets a nice filename
            const chatTitle = document.querySelector('.chat-header h2')?.textContent || 'Chat Conversation';
            printWindow.document.title = `${chatTitle} - Export`;
            
            // Write to new window
            printWindow.document.open();
            printWindow.document.write(content);
            printWindow.document.close();
            
            // Create a more robust loading mechanism
            const maxRetries = 10;
            let retryCount = 0;
            
            const attemptPrint = () => {
                console.log(`Print attempt ${retryCount + 1}/${maxRetries}`);
                
                if (printWindow.document.readyState !== 'complete') {
                    if (retryCount < maxRetries) {
                        retryCount++;
                        console.log(`Document not ready, retrying in ${retryCount * 300}ms...`);
                        setTimeout(attemptPrint, retryCount * 300); // Exponential backoff
                        return;
                    } else {
                        console.warn("Max retries reached, attempting to print anyway");
                    }
                }
                
                try {
                    console.log("Document ready, printing...");
                    // Add a slight delay to ensure styles are applied
                    setTimeout(() => {
                        printWindow.focus(); // Focus the window before printing
                        printWindow.print();
                        
                        // Close the window after print dialog is closed (or after a timeout)
                        setTimeout(() => {
                            console.log("Closing print window");
                            printWindow.close();
                        }, 1000);
                    }, 500);
                } catch (e) {
                    console.error("Error during printing:", e);
                    alert("There was an error when printing. Please try again.");
                    printWindow.close();
                }
            };
            
            // Start printing process after a short delay to ensure the window is ready
            setTimeout(attemptPrint, 500);
            
        } catch (error) {
            console.error("Error in exportToPDF:", error);
            alert("Failed to export as PDF. Please try again.");
        }
    }

    /**
     * Prepare HTML content for printing
     * @param {boolean} isDarkMode - Whether dark mode is enabled
     * @returns {string} HTML content ready for printing
     */
    _prepareContentForPrint(isDarkMode) {
        try {
            console.log("Preparing content for print");
            // Copy all necessary styles
            const styles = this._getStyles(isDarkMode);
            
            // Get chat title or use default
            const chatTitle = document.querySelector('.chat-header h2')?.textContent || 'Chat Conversation';
            
            // Clone the messages container to avoid modifying the original
            const messagesClone = this.messagesContainer.cloneNode(true);
            
            // Clean up the clone for printing
            this._cleanupForPrinting(messagesClone);
            
            // Generate the print HTML with additional styling and scripts to ensure visibility
            return `
                <!DOCTYPE html>
                <html>
                <head>
                    <title>${chatTitle} - Export</title>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <style>${styles}</style>
                    <script>
                        // This script ensures content visibility
                        document.addEventListener('DOMContentLoaded', function() {
                            console.log("PDF document loaded");
                            document.body.style.visibility = 'visible';
                            document.body.style.opacity = '1';
                            // Force reflow to ensure styles are applied
                            document.body.offsetHeight;
                        });
                    </script>
                </head>
                <body class="${isDarkMode ? 'dark-mode' : ''}" style="visibility: visible !important; opacity: 1 !important;">
                    <div class="print-container">
                        <h1>${chatTitle}</h1>
                        <div class="print-timestamp">Exported on ${new Date().toLocaleString()}</div>
                        <div class="print-messages">
                            ${messagesClone.innerHTML}
                        </div>
                    </div>
                </body>
                </html>
            `;
        } catch (error) {
            console.error("Error preparing content for print:", error);
            throw error;
        }
    }

    /**
     * Get all necessary styles for the print layout
     * @param {boolean} isDarkMode - Whether dark mode is enabled
     * @returns {string} Combined CSS styles
     */
    _getStyles(isDarkMode) {
        // Basic print styles
        const printStyles = `
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background-color: ${isDarkMode ? '#1e1e1e' : '#ffffff'};
                color: ${isDarkMode ? '#ffffff' : '#000000'};
                padding: 20px;
                margin: 0;
            }
            .print-container {
                max-width: 800px;
                margin: 0 auto;
            }
            .print-timestamp {
                color: ${isDarkMode ? '#aaaaaa' : '#666666'};
                margin-bottom: 20px;
                font-style: italic;
                font-size: 0.9rem;
            }
            
            /* Message group styles */
            .message-group {
                margin-bottom: 1.5rem;
                page-break-inside: avoid;
                display: flex;
                flex-direction: column;
                width: 100%;
                position: relative;
            }
            
            /* Message content containers */
            .message-content {
                flex: 1;
                min-width: 0;
                width: 100%;
            }
            
            .message-content-container {
                max-width: 800px;
                margin: 0 auto;
                width: 100%;
                position: relative;
                display: flex;
                flex-direction: column;
            }
            
            /* Message bubbles */
            .message-bubble {
                padding: 10px 15px;
                border-radius: 8px;
                max-width: 85%;
                white-space: pre-wrap;
                word-break: break-word;
            }
            
            /* User message styles */
            .user-message {
                background-color: ${isDarkMode ? 'rgba(42, 63, 84, 0.1)' : 'rgba(230, 242, 255, 0.2)'};
                padding: 10px 0;
                width: 100%;
            }
            
            .user-message .message-content-container {
                align-items: flex-end;
            }
            
            .user-message .message-bubble {
                background-color: ${isDarkMode ? '#2a3f54' : '#e6f2ff'};
                margin-left: auto;
            }
            
            /* Assistant message styles */
            .assistant-message {
                background-color: ${isDarkMode ? 'rgba(50, 50, 50, 0.1)' : 'rgba(240, 240, 240, 0.2)'};
                padding: 10px 0;
                width: 100%;
            }
            
            .assistant-message .message-content-container {
                align-items: flex-start;
            }
            
            .assistant-message .message-bubble {
                background-color: ${isDarkMode ? '#323232' : '#f0f0f0'};
            }
            
            /* Tool message styles */
            .tool-message {
                background-color: ${isDarkMode ? 'rgba(40, 60, 80, 0.1)' : 'rgba(240, 250, 255, 0.2)'};
                padding: 10px 0;
                width: 100%;
                font-family: monospace;
                font-size: 0.9em;
            }
            
            .tool-message .message-bubble {
                background-color: transparent;
                width: 100%;
                max-width: 100%;
            }
            
            /* Tool list styles */
            .tool-list {
                padding: 6px;
                margin-bottom: 8px;
                background-color: ${isDarkMode ? 'rgba(68, 85, 102, 0.1)' : 'rgba(68, 85, 102, 0.03)'};
                border-radius: 8px;
                border: 1px solid ${isDarkMode ? 'rgba(68, 85, 102, 0.2)' : 'rgba(68, 85, 102, 0.1)'};
                display: flex;
                flex-direction: column;
                gap: 0.4rem;
                width: 100%;
                overflow: visible;
                margin-bottom: 1rem;
            }
            
            .tool-list-header {
                font-size: 0.75rem;
                color: ${isDarkMode ? '#80cbc4' : '#10a37f'};
                font-weight: 500;
                padding: 0.25rem 0;
                border-bottom: 1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'};
                margin-bottom: 0.5rem;
            }
            
            /* Tool container styles */
            .tool-container {
                background-color: ${isDarkMode ? 'rgba(68, 85, 102, 0.1)' : 'rgba(68, 85, 102, 0.04)'};
                border: 1px solid ${isDarkMode ? 'rgba(68, 85, 102, 0.2)' : 'rgba(68, 85, 102, 0.1)'};
                border-radius: 6px;
                border-left: 2px solid ${isDarkMode ? '#80cbc4' : '#10a37f'};
                padding: 0.4rem 0.6rem;
                margin-bottom: 0.5rem;
                width: 100%;
                box-sizing: border-box;
            }
            
            /* Tool header styles */
            .tool-header {
                display: flex;
                align-items: center;
                gap: 0.3rem;
                font-size: 0.8rem;
                position: relative;
                margin-bottom: 0.5rem;
                font-weight: bold;
            }
            
            .tool-name {
                color: ${isDarkMode ? '#80cbc4' : '#10a37f'};
                font-weight: bold;
            }
            
            .tool-args {
                color: ${isDarkMode ? '#aaaaaa' : '#666666'};
                font-size: 0.8rem;
                overflow: hidden;
                text-overflow: ellipsis;
                font-style: italic;
            }
            
            .status-indicator {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-left: auto;
            }
            
            .tool-container[data-status="completed"] .status-indicator {
                background-color: ${isDarkMode ? '#80cbc4' : '#10a37f'};
            }
            
            .tool-container[data-status="error"] .status-indicator {
                background-color: #d32f2f;
            }
            
            /* Tool result styles */
            .tool-result {
                background-color: ${isDarkMode ? 'rgba(30, 30, 30, 0.4)' : 'rgba(68, 85, 102, 0.03)'};
                border-radius: 4px;
                margin-top: 0.2rem;
                padding: 0.4rem 0.6rem;
                border: 1px solid ${isDarkMode ? 'rgba(60, 60, 60, 0.3)' : 'rgba(68, 85, 102, 0.1)'};
                width: 100%;
                box-sizing: border-box;
            }
            
            .tool-result pre {
                margin: 0;
                font-family: monospace;
                font-size: 0.75rem;
                line-height: 1.3;
                white-space: pre-wrap;
            }
            
            .tool-result code {
                background: none;
                padding: 0;
                white-space: pre-wrap;
                word-break: break-word;
                color: ${isDarkMode ? '#ffffff' : '#000000'};
            }
            
            .tool-result.error {
                background-color: ${isDarkMode ? 'rgba(211, 47, 47, 0.15)' : 'rgba(211, 47, 47, 0.08)'};
                border-left: 2px solid rgba(211, 47, 47, 0.5);
            }
            
            .tool-result.error code {
                color: #d32f2f;
            }
            
            .tool-result.encoding-error {
                background-color: ${isDarkMode ? 'rgba(255, 152, 0, 0.15)' : 'rgba(255, 152, 0, 0.08)'};
                border-left: 3px solid rgba(255, 152, 0, 0.8);
                position: relative;
                padding-top: 42px;
                margin-top: 8px;
            }
            
            .tool-result.encoding-error::before {
                content: "⚠️ Encoding Issue Detected";
                position: absolute;
                top: 8px;
                left: 8px;
                font-size: 0.85rem;
                color: #ff9800;
                font-weight: bold;
            }
            
            /* Speaker labels */
            .user-label, .assistant-label, .tool-label {
                font-weight: bold;
                margin-bottom: 5px;
                font-size: 0.9rem;
            }
            
            .user-label {
                text-align: right;
                color: ${isDarkMode ? '#8ab4f8' : '#1a73e8'};
            }
            
            .assistant-label {
                text-align: left;
                color: ${isDarkMode ? '#aaaaaa' : '#666666'};
            }
            
            .tool-label {
                text-align: left;
                color: ${isDarkMode ? '#80cbc4' : '#009688'};
            }
            
            /* Code blocks */
            pre {
                white-space: pre-wrap;
                background-color: ${isDarkMode ? '#2d2d2d' : '#f6f8fa'};
                border-radius: 4px;
                padding: 10px;
                overflow-x: auto;
            }
            
            code {
                font-family: monospace;
                font-size: 0.9em;
            }
            
            /* Blockquotes - Fix for markdown quotes */
            blockquote {
                border-left: 3px solid ${isDarkMode ? '#555555' : '#dfe2e5'};
                color: ${isDarkMode ? '#bbbbbb' : '#444444'};
                padding-left: 1em;
                margin-left: 0;
                margin-right: 0;
                font-style: italic;
                background-color: ${isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)'};
                padding: 0.5rem 1rem;
                border-radius: 0 4px 4px 0;
            }
            
            /* Images */
            img {
                max-width: 100%;
                height: auto;
                border-radius: 6px;
                border: 1px solid ${isDarkMode ? '#555555' : '#dddddd'};
            }
            
            /* Message image container */
            .message-image {
                display: block;
                width: 200px;
                max-height: 300px;
                overflow: hidden;
                border-radius: 8px;
                margin: 0.5rem 0;
            }
            
            /* Hide elements not needed for print */
            .copy-markdown-button, .retry-button,
            .message-buttons-container, .suggestion-chips, .tool-list-toggle {
                display: none !important;
            }
            
            /* Ensure markdown content renders properly */
            p {
                margin-top: 0.5em;
                margin-bottom: 0.5em;
            }
            
            ul, ol {
                margin-left: 1.5em;
                margin-top: 0.5em;
                margin-bottom: 0.5em;
            }
            
            @media print {
                body {
                    background-color: transparent !important;
                }
                .print-container {
                    max-width: 100%;
                }
                
                /* Ensure colored backgrounds are preserved during print */
                .user-message, .assistant-message, .tool-message, 
                .tool-container, .tool-result, blockquote {
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                    color-adjust: exact !important;
                }
                
                /* Force page breaks between sections if needed */
                .page-break-after {
                    page-break-after: always;
                }
            }
        `;
        
        return printStyles;
    }

    /**
     * Clean up the DOM for printing
     * @param {HTMLElement} container - The container element to clean
     */
    _cleanupForPrinting(container) {
        try {
            console.log("Cleaning up DOM for printing");
            // Remove buttons and UI controls
            const elementsToRemove = container.querySelectorAll(
                '.copy-markdown-button, .retry-button, .message-buttons-container, ' +
                '.tool-list-toggle, .suggestion-chips'
            );
            elementsToRemove.forEach(el => el.remove());
            
            // Remove empty message groups and bubbles
            const emptyMessages = container.querySelectorAll('.message-group');
            emptyMessages.forEach(msg => {
                const bubble = msg.querySelector('.message-bubble');
                if (bubble && !bubble.textContent.trim()) {
                    // If this is an empty bubble with no content, remove the entire message
                    msg.remove();
                }
            });

            // Make sure messages are visible and have content
            const messageGroups = container.querySelectorAll('.message-group');
            console.log(`Found ${messageGroups.length} message groups to export`);
            
            if (messageGroups.length === 0) {
                // Add a fallback message if no messages are found
                const fallbackMsg = document.createElement('div');
                fallbackMsg.className = 'message-group assistant-message';
                fallbackMsg.innerHTML = `
                    <div class="message-content">
                        <div class="message-content-container">
                            <div class="message-bubble">
                                <p>There are no messages to export or the content couldn't be loaded properly.</p>
                            </div>
                        </div>
                    </div>
                `;
                container.appendChild(fallbackMsg);
                console.warn("No message groups found, added fallback message");
            }
            
            // Add labels to clearly identify speakers
            const userMessages = container.querySelectorAll('.user-message');
            const assistantMessages = container.querySelectorAll('.assistant-message:not(.welcome-message)');
            const toolMessages = container.querySelectorAll('.tool-message');
            
            userMessages.forEach(msg => {
                const label = document.createElement('div');
                label.className = 'user-label';
                label.textContent = 'You';
                const contentContainer = msg.querySelector('.message-content-container');
                if (contentContainer) {
                    contentContainer.insertBefore(label, contentContainer.firstChild);
                }
            });
            
            assistantMessages.forEach(msg => {
                const label = document.createElement('div');
                label.className = 'assistant-label';
                label.textContent = 'Assistant';
                const contentContainer = msg.querySelector('.message-content-container');
                if (contentContainer) {
                    contentContainer.insertBefore(label, contentContainer.firstChild);
                }
            });
            
            toolMessages.forEach(msg => {
                const label = document.createElement('div');
                label.className = 'tool-label';
                label.textContent = 'Tools';
                const contentContainer = msg.querySelector('.message-content-container');
                if (contentContainer) {
                    contentContainer.insertBefore(label, contentContainer.firstChild);
                }
            });
            
            // Make sure all tool lists are expanded and visible
            const toolLists = container.querySelectorAll('.tool-list');
            toolLists.forEach(list => {
                // Make sure the list is expanded
                list.classList.remove('collapsed');
                
                // Make sure header is properly formatted for PDF
                let header = list.querySelector('.tool-list-header');
                if (header) {
                    // Remove any toggle elements from the header
                    const toggleElement = header.querySelector('.tool-list-toggle');
                    if (toggleElement) toggleElement.remove();
                } else {
                    // If header doesn't exist, create one
                    header = document.createElement('div');
                    header.className = 'tool-list-header';
                    header.textContent = 'Tools used to generate response';
                    list.insertBefore(header, list.firstChild);
                }
                
                // Make sure all tool containers are expanded
                const toolContainers = list.querySelectorAll('.tool-container');
                toolContainers.forEach(container => {
                    container.classList.remove('collapsed');
                    
                    // Make sure results are visible
                    const results = container.querySelectorAll('.tool-result');
                    results.forEach(result => result.classList.remove('hidden'));
                    
                    // Enhance tool headers for better readability in PDF
                    const toolHeader = container.querySelector('.tool-header');
                    if (toolHeader) {
                        // Make sure any status indicators show final state
                        const statusIndicator = toolHeader.querySelector('.status-indicator');
                        if (statusIndicator) {
                            if (container.getAttribute('data-status') === 'pending') {
                                container.setAttribute('data-status', 'completed');
                            }
                        }
                        
                        // Make tool names and args more readable
                        const toolName = toolHeader.querySelector('.tool-name');
                        if (toolName) toolName.style.fontWeight = 'bold';
                        
                        const toolArgs = toolHeader.querySelector('.tool-args');
                        if (toolArgs) toolArgs.style.fontStyle = 'italic';
                    }
                });
            });
            
            // Fix blockquote styling in the message bubbles
            const blockquotes = container.querySelectorAll('blockquote');
            blockquotes.forEach(quote => {
                quote.style.borderLeft = '3px solid var(--border-color, #dfe2e5)';
                quote.style.paddingLeft = '1em';
                quote.style.fontStyle = 'italic';
                quote.style.color = isDarkMode ? '#bbbbbb' : '#444444';
            });
            
            // Remove hidden elements
            const hiddenElements = container.querySelectorAll('.hidden');
            hiddenElements.forEach(el => {
                if (el.classList.contains('tool-result')) {
                    el.classList.remove('hidden'); // Make tool results visible
                } else if (el.classList.contains('welcome-message')) {
                    el.remove(); // Remove welcome message
                } else {
                    el.remove(); // Remove other hidden elements
                }
            });
            
            // Add striping for better readability
            const allMessageGroups = container.querySelectorAll('.message-group');
            allMessageGroups.forEach((group, index) => {
                // Ensure striping is preserved
                if (group.classList.contains('user-message')) {
                    group.style.backgroundColor = index % 2 === 0 ? 'rgba(230, 242, 255, 0.2)' : 'rgba(230, 242, 255, 0.1)';
                } else if (group.classList.contains('assistant-message')) {
                    group.style.backgroundColor = index % 2 === 0 ? 'rgba(240, 240, 240, 0.2)' : 'rgba(240, 240, 240, 0.1)';
                } else if (group.classList.contains('tool-message')) {
                    group.style.backgroundColor = index % 2 === 0 ? 'rgba(240, 250, 255, 0.2)' : 'rgba(240, 250, 255, 0.1)';
                }
            });
        } catch (error) {
            console.error("Error cleaning up DOM for printing:", error);
        }
    }
}
