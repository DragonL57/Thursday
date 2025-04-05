/**
 * Emergency debug tools for fixing tool call display issues
 */

// Create a global event listener to catch and display all SSE events
document.addEventListener('DOMContentLoaded', function() {
    // Create debug panel
    const debugPanel = document.createElement('div');
    debugPanel.id = 'tool-debug-panel';
    debugPanel.style.position = 'fixed';
    debugPanel.style.bottom = '10px';
    debugPanel.style.left = '10px';
    debugPanel.style.zIndex = '9999';
    debugPanel.style.background = '#ff6600';
    debugPanel.style.color = 'white';
    debugPanel.style.padding = '10px';
    debugPanel.style.borderRadius = '5px';
    debugPanel.style.fontSize = '12px';
    debugPanel.style.fontFamily = 'monospace';
    debugPanel.style.cursor = 'pointer';
    debugPanel.textContent = '🛠️ DEBUG TOOLS';
    debugPanel.onclick = toggleDebugConsole;
    
    // Create debug console
    const debugConsole = document.createElement('div');
    debugConsole.id = 'tool-debug-console';
    debugConsole.style.position = 'fixed';
    debugConsole.style.bottom = '50px';
    debugConsole.style.left = '10px';
    debugConsole.style.width = '400px';
    debugConsole.style.maxWidth = '80vw';
    debugConsole.style.height = '300px';
    debugConsole.style.maxHeight = '50vh';
    debugConsole.style.background = 'rgba(0,0,0,0.9)';
    debugConsole.style.color = '#00ff00';
    debugConsole.style.padding = '10px';
    debugConsole.style.borderRadius = '5px';
    debugConsole.style.overflow = 'auto';
    debugConsole.style.fontFamily = 'monospace';
    debugConsole.style.fontSize = '12px';
    debugConsole.style.display = 'none';
    debugConsole.style.zIndex = '9998';
    
    // Add close button to console
    const closeButton = document.createElement('button');
    closeButton.textContent = 'Close';
    closeButton.style.position = 'absolute';
    closeButton.style.top = '5px';
    closeButton.style.right = '5px';
    closeButton.style.background = '#ff6600';
    closeButton.style.color = 'white';
    closeButton.style.border = 'none';
    closeButton.style.borderRadius = '3px';
    closeButton.style.padding = '3px 8px';
    closeButton.style.cursor = 'pointer';
    closeButton.onclick = function(e) {
        e.stopPropagation();
        debugConsole.style.display = 'none';
    };
    
    // Add actions section
    const actionsSection = document.createElement('div');
    actionsSection.style.marginBottom = '10px';
    actionsSection.style.padding = '5px';
    actionsSection.style.borderBottom = '1px solid #444';
    
    // Add refresh button
    const refreshButton = document.createElement('button');
    refreshButton.textContent = 'Check Tool Elements';
    refreshButton.style.background = '#008800';
    refreshButton.style.color = 'white';
    refreshButton.style.border = 'none';
    refreshButton.style.borderRadius = '3px';
    refreshButton.style.padding = '3px 8px';
    refreshButton.style.marginRight = '5px';
    refreshButton.style.cursor = 'pointer';
    refreshButton.onclick = checkToolElements;
    
    // Add force tool display button
    const forceToolButton = document.createElement('button');
    forceToolButton.textContent = 'Force Tool Display';
    forceToolButton.style.background = '#880000';
    forceToolButton.style.color = 'white';
    forceToolButton.style.border = 'none';
    forceToolButton.style.borderRadius = '3px';
    forceToolButton.style.padding = '3px 8px';
    forceToolButton.style.cursor = 'pointer';
    forceToolButton.onclick = forceToolDisplay;
    
    actionsSection.appendChild(refreshButton);
    actionsSection.appendChild(forceToolButton);
    
    // Add logs section
    const logsSection = document.createElement('div');
    logsSection.id = 'debug-logs';
    logsSection.style.height = 'calc(100% - 40px)';
    logsSection.style.overflowY = 'auto';
    
    // Build the console
    debugConsole.appendChild(closeButton);
    debugConsole.appendChild(actionsSection);
    debugConsole.appendChild(logsSection);
    
    // Add emergency auto-checker button
    const emergencyButton = document.createElement('button');
    emergencyButton.textContent = '🆘 EMERGENCY CHECK NOW';
    emergencyButton.style.background = '#ff0000';
    emergencyButton.style.color = 'white';
    emergencyButton.style.border = 'none';
    emergencyButton.style.borderRadius = '3px';
    emergencyButton.style.padding = '5px 10px';
    emergencyButton.style.margin = '10px 0';
    emergencyButton.style.fontWeight = 'bold';
    emergencyButton.style.cursor = 'pointer';
    emergencyButton.onclick = function() {
        log('🔎 Performing emergency check', 'warning');
        checkToolElements();
        forceScanMessages();
    };
    
    actionsSection.appendChild(emergencyButton);
    
    // Add powerful stream event analyzer
    const streamAnalyzerBtn = document.createElement('button');
    streamAnalyzerBtn.textContent = '📊 Analyze Stream Events';
    streamAnalyzerBtn.style.background = '#8800ff';
    streamAnalyzerBtn.style.color = 'white';
    streamAnalyzerBtn.style.border = 'none';
    streamAnalyzerBtn.style.borderRadius = '3px';
    streamAnalyzerBtn.style.padding = '5px 10px';
    streamAnalyzerBtn.style.margin = '10px 0';
    streamAnalyzerBtn.style.fontWeight = 'bold';
    streamAnalyzerBtn.style.cursor = 'pointer';
    streamAnalyzerBtn.onclick = analyzeStreamEvents;
    
    actionsSection.appendChild(streamAnalyzerBtn);
    
    // Add tool seeker to find missing tools
    const toolSeekerBtn = document.createElement('button');
    toolSeekerBtn.textContent = '🔍 Force Find & Create Tools';
    toolSeekerBtn.style.background = '#ff0088';
    toolSeekerBtn.style.color = 'white';
    toolSeekerBtn.style.border = 'none';
    toolSeekerBtn.style.borderRadius = '3px';
    toolSeekerBtn.style.padding = '5px 10px';
    toolSeekerBtn.style.margin = '0 0 10px 0';
    toolSeekerBtn.style.fontWeight = 'bold';
    toolSeekerBtn.style.cursor = 'pointer';
    toolSeekerBtn.onclick = seekAndCreateTools;
    
    actionsSection.appendChild(toolSeekerBtn);
    
    // Add everything to the DOM
    document.body.appendChild(debugPanel);
    document.body.appendChild(debugConsole);
    
    // Initialize event listener for tool check
    if (window.messagingComponent) {
        log('MessagingComponent found in window');
    } else {
        log('WARNING: MessagingComponent not found in window', 'error');
    }
    
    // Automatically check for tool elements every 5 seconds
    setInterval(checkToolElements, 5000);
    
    // Add a monitor that actively checks for tool calls every second
    const toolMonitor = setInterval(() => {
        if (window.TOOL_DEBUG_TRACKER) {
            const tracker = window.TOOL_DEBUG_TRACKER;
            
            // Check if we have tool calls that haven't been displayed
            if (tracker.lastToolCall) {
                const toolId = tracker.lastToolCall.id;
                const toolElement = document.getElementById(`tool-message-${toolId}`);
                const emergencyToolElement = document.getElementById(`emergency-tool-${toolId}`);
                
                if (!toolElement && !emergencyToolElement) {
                    log('🚨 Found undisplayed tool call - forcing display', 'warning');
                    forceToolDisplay();
                }
            }
        }
    }, 1000);
    
    // Add aggressive event interception for SSE events
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const result = originalFetch.apply(this, args);
        
        // Check if this is a streaming request
        if (args[0] && args[0].includes && args[0].includes('/chat/stream')) {
            log('📡 Intercepted streaming request', 'info');
            
            // Monitor the response
            result.then(response => {
                if (response && response.body && response.body.getReader) {
                    log('🔍 Monitoring response stream', 'info');
                    
                    const originalGetReader = response.body.getReader;
                    response.body.getReader = function() {
                        const reader = originalGetReader.apply(response.body);
                        
                        const originalRead = reader.read;
                        reader.read = function() {
                            return originalRead.apply(reader).then(result => {
                                if (result.value) {
                                    const text = new TextDecoder().decode(result.value);
                                    if (text.includes('tool_call') || text.includes('tool_update')) {
                                        log('⚡ TOOL EVENT DETECTED in raw stream!', 'warning');
                                        log(text);
                                    }
                                }
                                return result;
                            });
                        };
                        
                        return reader;
                    };
                }
            });
        }
        
        return result;
    };
    
    // Make debug panel more visible
    debugPanel.style.border = '3px solid red';
    debugPanel.style.boxShadow = '0 0 10px rgba(255,0,0,0.5)';
});

// Add a function to force scan all messages for potential tool calls
function forceScanMessages() {
    log('🔬 Scanning all messages for potential tool calls', 'info');
    
    // Scan for potential tool calls in message content
    const allMessages = document.querySelectorAll('.message-bubble');
    allMessages.forEach(msg => {
        const text = msg.textContent;
        if (text.includes('Tool') && (text.includes('Execution') || text.includes('Result'))) {
            log('🔎 Found potential tool call in message text', 'warning');
            log(text);
        }
    });
    
    // Check if we have any tool tracker data
    if (window.TOOL_DEBUG_TRACKER && window.TOOL_DEBUG_TRACKER.lastToolCall) {
        log('✅ Found tool call in tracker - forcing display', 'info');
        forceToolDisplay();
    }
}

function toggleDebugConsole() {
    const console = document.getElementById('tool-debug-console');
    console.style.display = console.style.display === 'none' ? 'block' : 'none';
}

function log(message, type = 'info') {
    const logsSection = document.getElementById('debug-logs');
    if (!logsSection) return;
    
    const logEntry = document.createElement('div');
    const timestamp = new Date().toLocaleTimeString();
    
    logEntry.style.marginBottom = '5px';
    logEntry.style.borderLeft = `3px solid ${type === 'error' ? '#ff0000' : type === 'warning' ? '#ffaa00' : '#00aa00'}`;
    logEntry.style.paddingLeft = '5px';
    
    logEntry.innerHTML = `<span style="color:#aaa">[${timestamp}]</span> ${message}`;
    
    logsSection.appendChild(logEntry);
    logsSection.scrollTop = logsSection.scrollHeight;
}

function checkToolElements() {
    const toolMessages = document.querySelectorAll('.tool-message');
    log(`Found ${toolMessages.length} tool message elements`);
    
    toolMessages.forEach((element, index) => {
        log(`Tool ${index + 1}: id=${element.id}, visibility=${window.getComputedStyle(element).display}`);
    });
    
    if (window.TOOL_DEBUG_TRACKER) {
        log(`Events received: ${window.TOOL_DEBUG_TRACKER.eventsReceived}`);
        log(`Tool calls received: ${window.TOOL_DEBUG_TRACKER.toolCallsReceived}`);
        log(`Tool updates received: ${window.TOOL_DEBUG_TRACKER.toolUpdatesReceived}`);
    }
}

function forceToolDisplay() {
    if (window.TOOL_DEBUG_TRACKER && window.TOOL_DEBUG_TRACKER.lastToolCall) {
        const lastTool = window.TOOL_DEBUG_TRACKER.lastToolCall;
        log(`Forcing display of tool call: ${lastTool.name}`);
        
        // Create a basic tool display element
        const container = document.createElement('div');
        container.className = 'tool-message';
        container.id = `forced-tool-${lastTool.id || Date.now()}`;
        container.style.margin = '15px 0';
        container.style.padding = '10px';
        container.style.border = '3px solid red';
        container.style.borderRadius = '5px';
        container.style.backgroundColor = '#ffeeee';
        
        container.innerHTML = `
            <div style="font-weight:bold;margin-bottom:5px">🛠️ FORCED TOOL: ${lastTool.name}</div>
            <div style="font-family:monospace;white-space:pre-wrap;background:#eee;padding:5px;margin-bottom:5px">
                ${JSON.stringify(lastTool.args || {}, null, 2)}
            </div>
            ${lastTool.result ? `
                <div style="margin-top:5px">
                    <div style="font-weight:bold">Result:</div>
                    <div style="font-family:monospace;white-space:pre-wrap;background:#eee;padding:5px;border-left:3px solid #00aa00">
                        ${lastTool.result}
                    </div>
                </div>
            ` : ''}
        `;
        
        // Find a good place to insert it
        const messages = document.getElementById('messages');
        if (messages) {
            if (messages.lastChild) {
                messages.lastChild.after(container);
            } else {
                messages.appendChild(container);
            }
            log('Forced tool display added to DOM');
        } else {
            document.body.appendChild(container);
            log('Messages container not found, added to body instead');
        }
    } else {
        log('No tool call data available to display', 'warning');
    }
}

// Function to analyze all stream events
function analyzeStreamEvents() {
    if (!window.TOOL_DEBUG_TRACKER || !window.TOOL_DEBUG_TRACKER.rawEvents) {
        log('No stream events captured yet', 'error');
        return;
    }
    
    log(`Analyzing ${window.TOOL_DEBUG_TRACKER.rawEvents.length} stream events...`, 'info');
    
    const analyzer = document.createElement('div');
    analyzer.style.position = 'fixed';
    analyzer.style.top = '5%';
    analyzer.style.left = '5%';
    analyzer.style.width = '90%';
    analyzer.style.height = '90%';
    analyzer.style.background = '#000';
    analyzer.style.color = '#0f0';
    analyzer.style.padding = '20px';
    analyzer.style.fontFamily = 'monospace';
    analyzer.style.fontSize = '14px';
    analyzer.style.zIndex = '10001';
    analyzer.style.overflow = 'auto';
    analyzer.style.border = '3px solid #8800ff';
    analyzer.style.boxShadow = '0 0 20px rgba(136,0,255,0.5)';
    
    // Add close button
    const closeBtn = document.createElement('button');
    closeBtn.textContent = 'Close';
    closeBtn.style.position = 'absolute';
    closeBtn.style.top = '10px';
    closeBtn.style.right = '10px';
    closeBtn.style.padding = '5px 15px';
    closeBtn.style.background = '#8800ff';
    closeBtn.style.color = 'white';
    closeBtn.style.border = 'none';
    closeBtn.style.borderRadius = '3px';
    closeBtn.style.fontWeight = 'bold';
    closeBtn.style.cursor = 'pointer';
    closeBtn.onclick = () => analyzer.remove();
    
    analyzer.appendChild(closeBtn);
    
    // Add header
    const header = document.createElement('h2');
    header.textContent = '🔬 Stream Event Analyzer';
    header.style.color = '#8800ff';
    header.style.borderBottom = '1px solid #8800ff';
    header.style.paddingBottom = '10px';
    analyzer.appendChild(header);
    
    // Add summary
    const summary = document.createElement('div');
    summary.innerHTML = `
        <div style="margin-bottom:20px;">
            <p>Total Events: ${window.TOOL_DEBUG_TRACKER.eventsReceived}</p>
            <p>Tool Calls Detected: ${window.TOOL_DEBUG_TRACKER.toolCallsReceived}</p>
            <p>Tool Updates Detected: ${window.TOOL_DEBUG_TRACKER.toolUpdatesReceived}</p>
        </div>
    `;
    analyzer.appendChild(summary);
    
    // Add event list with search capability
    const searchBox = document.createElement('input');
    searchBox.type = 'text';
    searchBox.placeholder = 'Search events (e.g. "tool_call")';
    searchBox.style.width = '100%';
    searchBox.style.padding = '5px';
    searchBox.style.marginBottom = '10px';
    searchBox.style.background = '#333';
    searchBox.style.color = '#0f0';
    searchBox.style.border = '1px solid #8800ff';
    analyzer.appendChild(searchBox);
    
    // Event container
    const eventsContainer = document.createElement('div');
    eventsContainer.style.marginTop = '20px';
    
    // Process events
    let eventHtml = '';
    let toolEventCount = 0;
    window.TOOL_DEBUG_TRACKER.rawEvents.forEach((event, index) => {
        let eventType = 'other';
        let highlightStyle = '';
        
        if (event.includes('tool_call')) {
            eventType = 'toolCall';
            highlightStyle = 'background:#ff0; color:#000;';
            toolEventCount++;
        } else if (event.includes('tool_update')) {
            eventType = 'toolUpdate';
            highlightStyle = 'background:#0ff; color:#000;';
            toolEventCount++;
        }
        
        eventHtml += `
            <div class="event-item" data-type="${eventType}" style="margin-bottom:10px; padding:5px; border-left:3px solid #555;">
                <div style="font-weight:bold; color:#0f0;">Event #${index + 1}</div>
                <pre style="margin:5px 0; ${highlightStyle} padding:3px; max-height:100px; overflow:auto;">${event}</pre>
                <button class="parse-event" data-index="${index}" style="background:#555; color:#fff; border:none; padding:2px 5px; cursor:pointer; font-size:12px;">Parse</button>
            </div>
        `;
    });
    
    // Alert if no tool events found
    if (toolEventCount === 0) {
        eventHtml = `
            <div style="padding:10px; background:#800; color:#fff; margin:10px 0; text-align:center;">
                ❌ No tool_call or tool_update events found in the stream!
            </div>
        ` + eventHtml;
    } else {
        eventHtml = `
            <div style="padding:10px; background:#080; color:#fff; margin:10px 0; text-align:center;">
                ✅ Found ${toolEventCount} tool-related events in the stream
            </div>
        ` + eventHtml;
    }
    
    eventsContainer.innerHTML = eventHtml;
    analyzer.appendChild(eventsContainer);
    
    // Add search functionality
    searchBox.addEventListener('input', () => {
        const searchTerm = searchBox.value.toLowerCase();
        const eventItems = eventsContainer.querySelectorAll('.event-item');
        
        eventItems.forEach(item => {
            if (item.textContent.toLowerCase().includes(searchTerm)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    });
    
    // Add parse event functionality
    eventsContainer.addEventListener('click', (e) => {
        if (e.target.classList.contains('parse-event')) {
            const index = parseInt(e.target.getAttribute('data-index'));
            const eventText = window.TOOL_DEBUG_TRACKER.rawEvents[index];
            
            try {
                // Try to parse the JSON from the SSE data format
                const jsonData = JSON.parse(eventText.substring(eventText.indexOf('{')));
                
                // Create a modal to display the parsed data
                alert(`Parsed data: ${JSON.stringify(jsonData, null, 2)}`);
                console.log('Parsed event data:', jsonData);
                
                // If this is a tool call or update, try to create UI for it
                if (jsonData.event === 'tool_call' && jsonData.data) {
                    if (confirm('Create UI for this tool call?')) {
                        if (window.messagingComponent && window.messagingComponent.addToolCallMessage) {
                            window.messagingComponent.addToolCallMessage(jsonData.data);
                        } else {
                            createFallbackToolUI(jsonData.data, 'call');
                        }
                    }
                } else if (jsonData.event === 'tool_update' && jsonData.data) {
                    if (confirm('Create UI for this tool update?')) {
                        if (window.messagingComponent && window.messagingComponent.updateToolCall) {
                            window.messagingComponent.updateToolCall(jsonData.data);
                        } else {
                            createFallbackToolUI(jsonData.data, 'update');
                        }
                    }
                }
            } catch (error) {
                console.error('Failed to parse event:', error);
                alert(`Failed to parse event: ${error.message}`);
            }
        }
    });
    
    // Add to document
    document.body.appendChild(analyzer);
    log('Stream event analyzer opened', 'info');
}

// Function to actively seek and create tools from raw events
function seekAndCreateTools() {
    if (!window.TOOL_DEBUG_TRACKER || !window.TOOL_DEBUG_TRACKER.rawEvents) {
        log('No stream events captured yet', 'error');
        return;
    }
    
    log('Scanning for tool calls in raw events...', 'info');
    
    // Keep track of created tools
    const createdTools = new Set();
    let foundToolCalls = 0;
    let createdToolCalls = 0;
    
    // Scan all raw events
    window.TOOL_DEBUG_TRACKER.rawEvents.forEach((event) => {
        if (event.includes('tool_call')) {
            foundToolCalls++;
            
            try {
                const dataStart = event.indexOf('{');
                if (dataStart !== -1) {
                    const jsonData = JSON.parse(event.substring(dataStart));
                    
                    // Check if this is a tool call event with data
                    if (jsonData.event === 'tool_call' && jsonData.data) {
                        const toolCall = jsonData.data;
                        const toolId = toolCall.id;
                        
                        // Only create if we haven't already done so
                        if (toolId && !createdTools.has(toolId)) {
                            // Find existing UI elements
                            const existingElement = document.getElementById(`tool-message-${toolId}`);
                            const existingEmergencyElement = document.getElementById(`emergency-tool-${toolId}`);
                            const existingDirectElement = document.getElementById(`direct-tool-${toolId}-call`);
                            
                            if (!existingElement && !existingEmergencyElement && !existingDirectElement) {
                                log(`Creating UI for tool: ${toolCall.name} (${toolId})`, 'info');
                                
                                // Try to create tool UI in multiple ways
                                if (window.messagingComponent && window.messagingComponent.addToolCallMessage) {
                                    window.messagingComponent.addToolCallMessage(toolCall);
                                } else if (window.createEmergencyToolCall) {
                                    window.createEmergencyToolCall(toolCall);
                                } else {
                                    // Last resort: Create a basic tool UI directly
                                    createBasicToolUI(toolCall);
                                }
                                
                                createdTools.add(toolId);
                                createdToolCalls++;
                            }
                        }
                    }
                }
            } catch (error) {
                console.error('Error processing tool call event:', error);
            }
        }
    });
    
    // Now process tool updates
    window.TOOL_DEBUG_TRACKER.rawEvents.forEach((event) => {
        if (event.includes('tool_update')) {
            try {
                const dataStart = event.indexOf('{');
                if (dataStart !== -1) {
                    const jsonData = JSON.parse(event.substring(dataStart));
                    
                    // Check if this is a tool update event with data
                    if (jsonData.event === 'tool_update' && jsonData.data) {
                        const toolUpdate = jsonData.data;
                        const toolId = toolUpdate.id;
                        
                        // Find existing UI elements
                        const existingElement = document.getElementById(`tool-message-${toolId}`);
                        const existingEmergencyElement = document.getElementById(`emergency-tool-${toolId}`);
                        
                        if (existingElement) {
                            log(`Updating UI for tool: ${toolUpdate.name} (${toolId})`, 'info');
                            if (window.messagingComponent && window.messagingComponent.updateToolCall) {
                                window.messagingComponent.updateToolCall(toolUpdate);
                            }
                        } else if (existingEmergencyElement) {
                            log(`Updating emergency UI for tool: ${toolUpdate.name} (${toolId})`, 'info');
                            if (window.updateEmergencyToolCall) {
                                window.updateEmergencyToolCall(toolUpdate);
                            }
                        } else {
                            // Create a new tool UI with completed status
                            log(`Creating completed tool UI: ${toolUpdate.name} (${toolId})`, 'info');
                            if (window.messagingComponent && window.messagingComponent.addToolCallMessage) {
                                window.messagingComponent.addToolCallMessage(toolUpdate);
                                window.messagingComponent.updateToolCall(toolUpdate);
                            } else if (window.createEmergencyToolCall) {
                                window.createEmergencyToolCall(toolUpdate);
                                window.updateEmergencyToolCall(toolUpdate);
                            } else {
                                createBasicToolUI(toolUpdate, true);
                            }
                        }
                    }
                }
            } catch (error) {
                console.error('Error processing tool update event:', error);
            }
        }
    });
    
    log(`Found ${foundToolCalls} tool calls, created ${createdToolCalls} new tool UIs`, createdToolCalls > 0 ? 'info' : 'warning');
}

// Create a very basic tool UI directly in the DOM
function createBasicToolUI(toolData, isCompleted = false) {
    const messagesContainer = document.getElementById('messages');
    if (!messagesContainer) {
        log('Cannot find messages container', 'error');
        return;
    }
    
    const toolElement = document.createElement('div');
    toolElement.id = `basic-tool-${toolData.id}`;
    toolElement.style.margin = '20px 0';
    toolElement.style.padding = '10px';
    toolElement.style.border = `5px solid ${isCompleted ? '#00c853' : '#ff0000'}`;
    toolElement.style.borderRadius = '10px';
    toolElement.style.backgroundColor = isCompleted ? '#e8f5e9' : '#fff9c4';
    toolElement.style.position = 'relative';
    toolElement.style.zIndex = '1000';
    
    // Parse args for display
    let args = '{}';
    try {
        if (typeof toolData.args === 'string') {
            args = JSON.parse(toolData.args);
            args = JSON.stringify(args, null, 2);
        } else {
            args = JSON.stringify(toolData.args || {}, null, 2);
        }
    } catch (e) {
        args = String(toolData.args || '{}');
    }
    
    // Add content
    toolElement.innerHTML = `
        <div style="text-align:center; font-size:18px; font-weight:bold; margin-bottom:10px; color:${isCompleted ? '#00c853' : '#ff0000'};">
            ${isCompleted ? '✅ TOOL COMPLETED' : '🛠️ TOOL EXECUTION'}
        </div>
        <div style="font-size:16px; font-weight:bold; background:${isCompleted ? '#00c853' : '#ff0000'}; color:white; padding:8px; border-radius:5px; margin-bottom:10px;">
            ${toolData.name}
        </div>
        <div style="background:#ffffff; padding:10px; border-radius:5px; border:1px solid #ddd; margin-bottom:10px;">
            <div style="font-weight:bold; margin-bottom:5px;">Arguments:</div>
            <pre style="margin:0; white-space:pre-wrap; overflow-x:auto; background:#f5f5f5; padding:5px; border-radius:3px;">${args}</pre>
        </div>
        ${toolData.result ? `
            <div style="background:#e8f5e9; padding:10px; border-radius:5px; border:1px solid #81c784;">
                <div style="font-weight:bold; margin-bottom:5px;">Result:</div>
                <pre style="margin:0; white-space:pre-wrap; overflow-x:auto; background:#f1f8e9; padding:5px; border-radius:3px;">${toolData.result}</pre>
            </div>
        ` : ''}
        <div style="text-align:right; margin-top:10px; color:#666; font-size:12px;">
            ID: ${toolData.id}
        </div>
    `;
    
    // Add to the messages container
    if (messagesContainer.firstChild) {
        messagesContainer.insertBefore(toolElement, messagesContainer.firstChild);
    } else {
        messagesContainer.appendChild(toolElement);
    }
    
    // Force scroll to make it visible
    toolElement.scrollIntoView({behavior: 'smooth'});
    
    return toolElement;
}

// Expose to the window for testing
window.debugTools = {
    log,
    checkToolElements,
    forceToolDisplay
};
