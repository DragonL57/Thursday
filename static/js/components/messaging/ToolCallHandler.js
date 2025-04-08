import { scrollToBottom } from '../../utils/dom.js';

export class ToolCallHandler {
    constructor(messagingComponent) {
        this.messagingComponent = messagingComponent;
        this.toolCalls = new Map(); // Track active tool calls by ID
        this.currentToolsList = null; // Container for the current message's tool list
        this.currentMessageContainer = null; // Reference to the container element
        this.isFinalResponseGenerating = false; // Track if final response is generating
        this.lastAddedToolId = null; // Track the most recently added tool
        console.log('ToolCallHandler initialized');
    }
    
    // Create tool list container
    createToolsListContainer() {
        const component = this.messagingComponent;
        
        if (!this.currentToolsList) {
            console.log('Creating new tools list container');
            
            const messageContainer = document.createElement('div');
            messageContainer.className = 'tool-message';
            messageContainer.setAttribute('data-placement', 'after-user');
            
            const contentContainer = document.createElement('div');
            contentContainer.className = 'message-content-container';
            
            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';
            
            const list = document.createElement('div');
            list.className = 'tool-list';
            list.setAttribute('data-has-header', 'true'); // Mark list as having a header
            
            // Create an explicit header element that will always be visible
            const header = document.createElement('div');
            header.className = 'tool-list-header';
            header.textContent = 'Tools used to generate response';
            header.setAttribute('data-clickable', 'true'); // Mark header as clickable
            
            // Add the toggle arrow
            const toggleArrow = document.createElement('span');
            toggleArrow.className = 'tool-list-toggle';
            toggleArrow.innerHTML = '▼';
            header.appendChild(toggleArrow);
            
            // Insert the header at the beginning
            list.appendChild(header);
            
            // Add a more robust click handler
            this._addToolListClickHandler(list, header, toggleArrow);
            
            bubble.appendChild(list);
            contentContainer.appendChild(bubble);
            messageContainer.appendChild(contentContainer);
            
            // Place the tool list after the last user message instead of before assistant message
            const userMessages = component.messagesContainer.querySelectorAll('.user-message');
            if (userMessages.length > 0) {
                const lastUserMessage = userMessages[userMessages.length - 1];
                // Insert after the last user message
                if (lastUserMessage.nextSibling) {
                    component.messagesContainer.insertBefore(messageContainer, lastUserMessage.nextSibling);
                } else {
                    component.messagesContainer.appendChild(messageContainer);
                }
            } else {
                // If no user message, append to the end
                component.messagesContainer.appendChild(messageContainer);
            }
            
            // Store references
            this.currentMessageContainer = messageContainer;
            this.currentToolsList = list;
        }
        
        return this.currentToolsList;
    }
    
    // New helper method for adding click handlers
    _addToolListClickHandler(list, header, toggleArrow) {
        // Instead of cloning, directly add click handlers to avoid losing references
        // First remove existing handlers if any
        if (header) {
            const newHeader = header.cloneNode(true);
            if (header.parentNode) {
                header.parentNode.replaceChild(newHeader, header);
                header = newHeader;
            }
            toggleArrow = header.querySelector('.tool-list-toggle');
        }
        
        // Define a more reliable click handler
        const toggleCollapse = (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            console.log('Tool list clicked, toggling collapse state');
            
            // Toggle class
            list.classList.toggle('collapsed');
            
            // Explicitly control visibility based on collapsed state
            const isCollapsed = list.classList.contains('collapsed');
            console.log(`List is now ${isCollapsed ? 'collapsed' : 'expanded'}`);
            
            // Get all direct children except the header
            const children = Array.from(list.children).filter(
                child => !child.classList.contains('tool-list-header')
            );
            
            // Directly manipulate display style for more reliable toggling
            children.forEach(child => {
                child.style.display = isCollapsed ? 'none' : 'block';
                child.style.opacity = isCollapsed ? '0' : '1';
                child.style.height = isCollapsed ? '0' : 'auto';
            });
            
            // Adjust list height directly
            list.style.maxHeight = isCollapsed ? '35px' : '500px';
            
            // Ensure scroll position is good when expanding
            if (!isCollapsed) {
                setTimeout(() => {
                    this.smoothScrollToElement(list);
                }, 50);
            }
        };
        
        // Add listeners with explicit styling for visibility
        if (header) {
            // Remove old handlers if any
            header.removeEventListener('click', header._toggleHandler);
            
            // Store handler reference
            header._toggleHandler = toggleCollapse;
            header.addEventListener('click', header._toggleHandler);
            
            // Ensure it's visibly clickable
            header.style.cursor = 'pointer';
            header.style.pointerEvents = 'auto';
            header.style.zIndex = '20';
            header.style.userSelect = 'none';
            header.setAttribute('title', 'Click to toggle tools display');
        }
        
        if (toggleArrow) {
            // Remove old handlers if any
            toggleArrow.removeEventListener('click', toggleArrow._toggleHandler);
            
            // Store handler reference
            toggleArrow._toggleHandler = toggleCollapse;
            toggleArrow.addEventListener('click', toggleArrow._toggleHandler);
            
            // Ensure it's visibly clickable
            toggleArrow.style.cursor = 'pointer';
            toggleArrow.style.pointerEvents = 'auto';
            toggleArrow.style.zIndex = '21';
        }
        
        // Mark that we've added the handler
        list._hasClickHandler = true;
        
        return list;
    }
    
    // Add tool to list
    addToolCallToList(toolCall) {
        if (!toolCall?.name) return null;
        
        const list = this.createToolsListContainer();
        if (!list) return null;
        
        // Reset final response flag when new tools are being added
        this.isFinalResponseGenerating = false;
        
        // Ensure the list is expanded while tools are being added
        list.classList.remove('collapsed');
        
        // Check for existing tool
        const existingItem = document.getElementById(`tool-${toolCall.id}`);
        if (existingItem) return this.updateToolInList(toolCall);
        
        // If we have a last added tool ID and it's different from this one,
        // collapse the previous tool (if it's not an error)
        if (this.lastAddedToolId && this.lastAddedToolId !== toolCall.id) {
            const previousTool = document.getElementById(`tool-${this.lastAddedToolId}`);
            if (previousTool && previousTool.getAttribute('data-status') !== 'error') {
                previousTool.classList.add('collapsed');
            }
        }
        
        // Remember this as the last added tool
        this.lastAddedToolId = toolCall.id;
        
        // Create tool container - don't add collapsed class initially to show tool while processing
        const container = document.createElement('div');
        container.className = 'tool-container new-tool'; // Add new-tool class for animation
        container.id = `tool-${toolCall.id}`;
        container.setAttribute('data-status', 'pending');
        
        // Add click event to toggle collapse state for this specific tool
        container.addEventListener('click', (e) => {
            // Don't handle clicks on interactive elements inside the container
            if (e.target.closest('a, button, input, textarea, select, option')) {
                return;
            }
            container.classList.toggle('collapsed');
            e.stopPropagation(); // Prevent triggering parent tool-list collapse
        });
        
        // Create header with tool name and args
        const header = document.createElement('div');
        header.className = 'tool-header';
        
        const name = document.createElement('span');
        name.className = 'tool-name';
        name.textContent = toolCall.name;
        
        const args = document.createElement('span');
        args.className = 'tool-args';
        args.textContent = `(${this._formatArguments(toolCall.args)})`;
        
        const status = document.createElement('span');
        status.className = 'status-indicator';
        
        header.appendChild(name);
        header.appendChild(args);
        header.appendChild(status);
        
        // Create result section
        const result = document.createElement('div');
        result.className = 'tool-result hidden';
        result.innerHTML = '<pre><code>Processing...</code></pre>';
        
        // Assemble and add to list
        container.appendChild(header);
        container.appendChild(result);
        list.appendChild(container);
        
        this.toolCalls.set(toolCall.id, { element: container, data: toolCall });
        
        // Collapse all other tools except for error tools
        this.collapseOlderTools(toolCall.id);
        
        // Scroll smoothly to the new tool
        this.smoothScrollToElement(container);
        
        // Ensure proper positioning after user message
        this.repositionToolList();
        
        // Remove the animation class after animation completes to prevent issues with future state changes
        setTimeout(() => {
            container.classList.remove('new-tool');
        }, 400);
        
        return container;
    }
    
    // Smooth scroll to an element
    smoothScrollToElement(element) {
        if (!element) return;
        
        setTimeout(() => {
            element.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'nearest',
                inline: 'nearest'
            });
        }, 50);
    }
    
    // Helper method to collapse older tools
    collapseOlderTools(currentToolId) {
        if (!this.currentToolsList) return;
        
        this.toolCalls.forEach((tool, toolId) => {
            // Skip the current tool and tools with error status
            if (toolId === currentToolId || tool.data.status === 'error') {
                return;
            }
            
            // Only collapse tools that are in the current list
            if (tool.element.parentNode === this.currentToolsList) {
                tool.element.classList.add('collapsed');
            }
        });
    }
    
    // Update tool in list
    updateToolInList(toolCall) {
        if (!toolCall?.id) return null;
        
        const container = document.getElementById(`tool-${toolCall.id}`);
        if (!container) return this.addToolCallToList(toolCall);
        
        // This is the currently active tool, make sure it's uncollapsed
        if (toolCall.id === this.lastAddedToolId && toolCall.status === 'pending') {
            container.classList.remove('collapsed');
            this.smoothScrollToElement(container);
        }
        
        // Update status
        if (toolCall.status) {
            container.setAttribute('data-status', toolCall.status);
            
            // When a tool completes and it's the last added tool,
            // keep it expanded if it has results to show
            if (toolCall.status === 'completed' && toolCall.id === this.lastAddedToolId) {
                if (toolCall.result) {
                    container.classList.remove('collapsed');
                    this.smoothScrollToElement(container);
                }
            }
            
            // Keep expanded while pending, only allow collapsing when completed
            if (toolCall.status === 'pending') {
                container.classList.remove('collapsed');
            }
        }
        
        // Update result if provided
        if (toolCall.result != null) {
            const result = container.querySelector('.tool-result');
            if (result) {
                result.classList.remove('hidden');
                
                let content = toolCall.result.toString();
                
                // Format JSON
                if ((content.startsWith('{') && content.endsWith('}')) || 
                    (content.startsWith('[') && content.endsWith(']'))) {
                    try {
                        content = JSON.stringify(JSON.parse(content), null, 2);
                    } catch (e) {} // Keep original if parsing fails
                }
                
                // Add error styling if needed
                if (toolCall.status === 'error' || content.includes('Error:')) {
                    result.classList.add('error');
                    // Auto-expand on error for visibility
                    container.classList.remove('collapsed');
                    this.smoothScrollToElement(container);
                }
                
                result.innerHTML = `<pre><code>${this._escapeHTML(content)}</code></pre>`;
                
                // Apply syntax highlighting
                if (window.hljs) {
                    const code = result.querySelector('code');
                    if (code) window.hljs.highlightElement(code);
                }
            }
        }
        
        // If this tool just finished and we're not in final response generation yet,
        // it might have been the last tool in a sequence, so check if we need to collapse all tools
        if ((toolCall.status === 'completed' || toolCall.status === 'error') && 
            !this.isFinalResponseGenerating) {
            this.checkAllToolsComplete();
        }
        
        // Update stored data
        if (this.toolCalls.has(toolCall.id)) {
            this.toolCalls.set(toolCall.id, {
                element: container,
                data: {...this.toolCalls.get(toolCall.id).data, ...toolCall}
            });
        }
        
        // Check if all tools are completed or have errors
        this.checkAllToolsComplete();
        
        return container;
    }
    
    // Check if all tools are completed and collapse the container if appropriate
    checkAllToolsComplete() {
        if (!this.currentToolsList) return;
        
        // Count total tools and completed/error tools
        let totalTools = 0;
        let completedTools = 0;
        let hasActiveTools = false;
        
        this.toolCalls.forEach(tool => {
            if (tool.element.parentNode === this.currentToolsList) {
                totalTools++;
                if (tool.data.status === 'completed' || tool.data.status === 'error') {
                    completedTools++;
                }
                // Check if any tool is still pending
                if (tool.data.status === 'pending') {
                    hasActiveTools = true;
                }
            }
        });
        
        // If any tools are still active/pending, don't proceed with collapsing
        if (hasActiveTools) {
            return;
        }
        
        // Only collapse if all tools are complete AND final response is generating
        if (totalTools > 0 && completedTools === totalTools && this.isFinalResponseGenerating) {
            setTimeout(() => {
                // Make sure the element still exists
                if (this.currentToolsList && this.currentToolsList.parentNode) {
                    console.log('All tools complete and final response generating - collapsing tool list');
                    
                    // Make extra sure the header exists and is clickable BEFORE collapsing
                    this.ensureToolListClickable();
                    
                    // Add collapsed class after ensuring header is ready
                    this.currentToolsList.classList.add('collapsed');
                    
                    // Double-check clickability after collapsing
                    setTimeout(() => this.ensureToolListClickable(), 50);
                    
                    // Also collapse each individual tool but maintain their structure
                    this.toolCalls.forEach(tool => {
                        if (tool.element.parentNode === this.currentToolsList) {
                            // Don't collapse tools with errors - keep them visible
                            if (tool.data.status !== 'error') {
                                tool.element.classList.add('collapsed');
                            }
                        }
                    });
                }
            }, 1000); // Delay of 1 second after all tools complete
        }
    }
    
    // Method to mark that final response is generating
    setFinalResponseGenerating(isGenerating) {
        console.log(`Setting final response generating: ${isGenerating}`);
        
        // Store previous state to detect changes
        const wasGenerating = this.isFinalResponseGenerating;
        this.isFinalResponseGenerating = isGenerating;
        
        // Ensure header is not accidentally removed
        if (this.currentToolsList) {
            // Force tool list to stay visible and properly interactive
            this.currentToolsList.style.display = 'flex';
            
            // Always ensure the header is present and clickable
            this.ensureToolListClickable();
            
            // When final response is done generating
            if (wasGenerating && !isGenerating) {
                console.log('Final response generation completed, ensuring header is still clickable');
                
                // Enforce min-height to ensure visibility
                this.currentToolsList.style.minHeight = '35px';
                
                // Set explicit display styles on header
                const header = this.currentToolsList.querySelector('.tool-list-header');
                if (header) {
                    header.style.display = 'flex';
                    header.style.opacity = '1';
                    header.style.visibility = 'visible';
                    header.style.pointerEvents = 'auto';
                    
                    // Add direct click handler
                    header.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        this.toggleToolList();
                    };
                }
                
                // Double-check the header visibility after delays to ensure it stays clickable
                setTimeout(() => this.ensureToolListClickable(), 100);
                setTimeout(() => this.ensureToolListClickable(), 500);
                setTimeout(() => this.ensureToolListClickable(), 1000);
                setTimeout(() => {
                    // Final check and repair
                    this.repairToolListClickability();
                }, 1500);
            }
        }
        
        // If final response is generating and all tools are completed, check for collapsing
        if (isGenerating) {
            this.checkAllToolsComplete();
        } else if (this.currentToolsList) {
            // If not generating, ensure tool list is properly interactive
            this.ensureToolListClickable();
        }
    }
    
    // Enhanced method to ensure the tool list remains clickable
    ensureToolListClickable() {
        if (!this.currentToolsList) return;
        
        console.log('Ensuring tool list header is clickable');
        
        // Make sure the header exists and is visible
        let headerText = this.currentToolsList.querySelector('.tool-list-header');
        
        if (!headerText) {
            console.log("Header not found, creating it");
            // If header doesn't exist, create it
            headerText = document.createElement('div');
            headerText.className = 'tool-list-header';
            headerText.textContent = 'Tools used to generate response';
            headerText.style.cursor = 'pointer';
            
            // Add the toggle arrow
            const toggleArrow = document.createElement('span');
            toggleArrow.className = 'tool-list-toggle';
            toggleArrow.innerHTML = '▼';
            headerText.appendChild(toggleArrow);
            
            // Insert at the beginning of the list
            if (this.currentToolsList.firstChild) {
                this.currentToolsList.insertBefore(headerText, this.currentToolsList.firstChild);
            } else {
                this.currentToolsList.appendChild(headerText);
            }
            
            // Update header reference
            this.currentToolsList.setAttribute('data-has-header', 'true');
        }
        
        // Make header explicitly visible with important flags (important when collapsed)
        headerText.style.opacity = '1';
        headerText.style.visibility = 'visible';
        headerText.style.display = 'flex';
        headerText.style.pointerEvents = 'auto';
        headerText.style.zIndex = '20';
        headerText.style.position = 'relative';
        headerText.style.cursor = 'pointer';
        headerText.style.userSelect = 'none';
        headerText.setAttribute('title', 'Click to toggle tools display');
        
        // Force the header to be at the top
        if (headerText.parentNode !== this.currentToolsList || headerText !== this.currentToolsList.firstChild) {
            this.currentToolsList.insertBefore(headerText, this.currentToolsList.firstChild);
        }
        
        // Re-add click handlers to be sure they work
        const toggleArrow = headerText.querySelector('.tool-list-toggle');
        this._addToolListClickHandler(this.currentToolsList, headerText, toggleArrow);
        
        // Add debug class for visual identification
        headerText.classList.add('debug-clickable');
        
        // Add direct click handler on the header itself for redundancy
        headerText.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('Direct header click detected');
            this.toggleToolList();
        };
    }
    
    // New method for direct toggling of tool list
    toggleToolList() {
        if (!this.currentToolsList) return;
        
        const isCollapsed = this.currentToolsList.classList.contains('collapsed');
        console.log(`Directly toggling tool list, current state: ${isCollapsed ? 'collapsed' : 'expanded'}`);
        
        // Toggle the class
        this.currentToolsList.classList.toggle('collapsed');
        const newState = this.currentToolsList.classList.contains('collapsed');
        
        // Directly manipulate all children for more reliable toggling
        const children = Array.from(this.currentToolsList.children).filter(
            child => !child.classList.contains('tool-list-header')
        );
        
        children.forEach(child => {
            child.style.display = newState ? 'none' : 'block';
            child.style.opacity = newState ? '0' : '1';
            child.style.height = newState ? '0' : 'auto';
        });
        
        // Set height directly
        this.currentToolsList.style.maxHeight = newState ? '35px' : '500px';
        
        if (!newState) {
            // When expanding, ensure scrolling works
            setTimeout(() => {
                this.smoothScrollToElement(this.currentToolsList);
            }, 50);
        }
    }
    
    // New method to repair clickability after any issues
    repairToolListClickability() {
        if (!this.currentToolsList) return;
        
        const header = this.currentToolsList.querySelector('.tool-list-header');
        if (header) {
            // Add a strong debug style to make sure we can see it
            header.style.border = '1px dashed blue';
            
            // Add fresh click handler that bypasses event system
            header.onclick = (e) => {
                e.preventDefault(); 
                e.stopPropagation();
                
                // Force the toggle directly
                this.toggleToolList();
                
                // For debugging
                console.log('Emergency click handler triggered');
                return false;
            };
        }
    }
    
    // Reset the tools list for a new conversation turn
    resetToolsList() {
        console.log('Preserving tool list for continuity');
        
        // Reset tracking variables
        this.isFinalResponseGenerating = false;
        this.lastAddedToolId = null;
        
        // Instead of removing, we'll just reset tracking variables
        // but leave the DOM elements in place
        this.currentToolsList = null;
        this.currentMessageContainer = null;
        // Keep the Map of tool calls to maintain history
    }
    
    // Method to ensure proper positioning of tool list
    repositionToolList() {
        if (this.currentMessageContainer) {
            // Find the last user message
            const userMessages = this.messagingComponent.messagesContainer.querySelectorAll('.user-message');
            if (userMessages.length > 0) {
                const lastUserMessage = userMessages[userMessages.length - 1];
                
                // Move the tool list after the last user message
                if (lastUserMessage.nextSibling !== this.currentMessageContainer) {
                    if (lastUserMessage.nextSibling) {
                        this.messagingComponent.messagesContainer.insertBefore(
                            this.currentMessageContainer, 
                            lastUserMessage.nextSibling
                        );
                    } else {
                        this.messagingComponent.messagesContainer.appendChild(this.currentMessageContainer);
                    }
                }
            }
        }
    }
    
    // COMPATIBILITY METHODS - Completely replaced with our new approach
    
    // This now points to the list-based method
    createToolCallElement(toolCall) {
        console.log('createToolCallElement called - redirecting to addToolCallToList');
        return this.addToolCallToList(toolCall);
    }
    
    // This now points to the list-based update method
    updateToolCall(toolCall) {
        console.log('updateToolCall called - redirecting to updateToolInList');
        return this.updateToolInList(toolCall);
    }
    
    // LEGACY METHOD - Now completely replaced, but kept for backward compatibility
    addToolCallMessage(toolCall) {
        console.log('addToolCallMessage called - redirecting to addToolCallToList');
        return this.addToolCallToList(toolCall);
    }
    
    // Helper method to format arguments nicely
    _formatArguments(argsString) {
        if (!argsString || argsString === '{}') {
            return '';
        }
        
        try {
            const args = JSON.parse(argsString);
            const formattedArgs = [];
            
            for (const [key, value] of Object.entries(args)) {
                let displayValue;
                
                if (typeof value === 'string') {
                    // Truncate long strings
                    if (value.length > 30) {
                        displayValue = `"${value.substring(0, 27)}..."`;
                    } else {
                        displayValue = `"${value}"`;
                    }
                } else if (value === null) {
                    displayValue = 'null';
                } else if (Array.isArray(value)) {
                    displayValue = '[...]';
                } else if (typeof value === 'object') {
                    displayValue = '{...}';
                } else {
                    displayValue = String(value);
                }
                
                formattedArgs.push(`${key}: ${displayValue}`);
            }
            
            return formattedArgs.join(', ');
        } catch (e) {
            // If parsing fails, just return a placeholder
            return '...';
        }
    }
    
    // Helper method to escape HTML for safe display
    _escapeHTML(str) {
        if (typeof str !== 'string') {
            return String(str);
        }
        return str
    }
}
