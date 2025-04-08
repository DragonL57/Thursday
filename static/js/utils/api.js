/**
 * API-related functions
 */

/**
 * Sleep for the specified duration
 * @param {number} ms - Time to sleep in milliseconds
 * @returns {Promise<void>}
 */
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Make an API request with automatic retries
 * @param {string} url - The URL to fetch
 * @param {Object} options - Fetch options
 * @param {number} retries - Maximum number of retries
 * @param {number} baseDelay - Base delay in ms before retrying
 * @param {number} maxDelay - Maximum delay in ms
 * @returns {Promise<Response>} - The fetch response
 */
async function fetchWithRetry(url, options, retries = 3, baseDelay = 1000, maxDelay = 10000) {
    let lastError;
    
    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const response = await fetch(url, options);
            
            // For rate limit errors (429), retry with appropriate backoff
            if (response.status === 429) {
                // Get retry-after header or use default backoff
                const retryAfter = response.headers.get('Retry-After');
                const delayMs = retryAfter ? parseInt(retryAfter) * 1000 : 3000;
                
                console.warn(`Rate limited. Retrying in ${delayMs/1000} seconds...`);
                await sleep(delayMs);
                continue;
            }
            
            // For bad gateway or server errors, retry with shorter delay
            if (response.status === 502 || response.status === 503 || response.status === 504) {
                if (attempt < retries) {
                    const delayMs = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
                    console.warn(`Server error (${response.status}). Retrying in ${delayMs/1000} seconds...`);
                    await sleep(delayMs);
                    continue;
                }
            }
            
            return response;
        } catch (error) {
            lastError = error;
            
            if (attempt < retries) {
                // Exponential backoff for network errors
                const delayMs = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
                console.warn(`Network error. Retrying in ${delayMs/1000} seconds...`, error);
                await sleep(delayMs);
            }
        }
    }
    
    throw lastError || new Error('Maximum retries reached');
}

/**
 * Send a message to the backend and handle streaming responses
 * @param {string} message - The message to send
 * @param {string|null} imageData - Optional base64 image data
 * @param {Function} onToolCall - Callback function when a tool call is received
 * @param {Function} onFinalResponse - Callback function when the final response is received
 * @returns {Promise<Object>} - The response data
 */
export async function sendChatMessage(message, imageData = null, onToolCall, onFinalResponse) {
    try {
        // Construct request payload with or without image
        const payload = { message };
        if (imageData) {
            payload.imageData = imageData;
        }
        
        const response = await fetchWithRetry('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        
        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }
        
        const responseData = await response.json();
        
        // If we have tool calls, process them first
        if (responseData.tool_calls && responseData.tool_calls.length > 0 && typeof onToolCall === 'function') {
            for (const toolCall of responseData.tool_calls) {
                // Call the callback for each tool call
                onToolCall(toolCall);
            }
        }
        
        // Then process the final response
        if (typeof onFinalResponse === 'function') {
            onFinalResponse(responseData.response);
        }
        
        return responseData;
    } catch (error) {
        console.error('Error sending chat message:', error);
        throw error;
    }
}

// Add AbortController to handle request cancellation
let currentController = null;

/**
 * Abort the current request if one is in progress
 */
export function abortCurrentRequest() {
    if (currentController) {
        currentController.abort();
        currentController = null;
    }
}

/**
 * Stream chat messages using server-sent events
 * @param {string} message - The message to send
 * @param {string|null} imageData - Optional base64 image data
 * @param {Object} callbacks - Callback functions for different events
 * @param {Function} callbacks.onToken - Called when a token is received (for incremental updates)
 * @param {Function} callbacks.onToolCall - Called when a tool call is received
 * @param {Function} callbacks.onToolUpdate - Called when a tool call is updated
 * @param {Function} callbacks.onFinalResponse - Called when the final response is received
 * @param {Function} callbacks.onInfo - Called when info messages are received
 * @param {Function} callbacks.onError - Called when an error occurs
 * @param {Function} callbacks.onDone - Called when the stream is complete
 * @param {Function} callbacks.onRecursionDepth - Called when recursion depth event is received
 * @returns {Promise<void>}
 */
export async function streamChatMessage(message, imageData = null, callbacks = {}) {
    const { onToken, onToolCall, onToolUpdate, onFinalResponse, onInfo, onError, onDone, onRecursionDepth } = callbacks;
    
    // Create a new AbortController for this request
    currentController = new AbortController();
    const signal = currentController.signal;
    
    // Track recursion depth for notifying observers properly
    let currentRecursionDepth = 0;
    
    // Initialize the accumulatedToken variable at the top level
    let accumulatedToken = '';
    
    // Keep track of tool calls we've seen by ID and signature
    const toolCalls = new Map();
    const toolSignatures = new Set();
    const processedToolUpdates = new Set();
    
    // Track the last seen response to prevent duplicates
    let lastSentResponse = '';
    // Track if a final response has been sent
    let finalResponseSent = false;
    
    try {
        // Construct request payload with or without image
        const payload = { message };
        if (imageData) {
            payload.imageData = imageData;
        }
        
        const response = await fetch('/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal // Add the abort signal
        });

        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }

        console.log('Stream connected, waiting for tokens...');

        // Create a reader for the stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        // Process the stream
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            // Decode the data
            const text = decoder.decode(value, {stream: true});
            buffer += text;
            
            // Process complete SSE messages
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';  // Keep the last incomplete chunk in the buffer
            
            for (const line of lines) {
                if (!line.trim()) continue;
                
                // Log only the first 40 chars of received chunks to avoid console spam
                console.log('Received SSE chunk:', line.substring(0, 40) + (line.length > 40 ? '...' : ''));
                
                // Handle Server-Sent Events format
                if (line.startsWith('data: ')) {
                    const data = line.substring(6);
                    
                    // Handle [DONE] event
                    if (data === '[DONE]') {
                        if (typeof onDone === 'function' && !finalResponseSent) {
                            finalResponseSent = true;
                            onDone();
                        }
                        console.log('Done event received');
                        continue;
                    }
                    
                    try {
                        const parsedData = JSON.parse(data);
                        
                        // Handle different event types
                        switch (parsedData.event) {
                            case 'start':
                                console.log('Stream started');
                                accumulatedToken = '';
                                break;
                                
                            case 'token':
                                // First token indicates we're beginning to generate the response
                                // Notify the tool handler that final response is generating
                                if (window.messagingComponent && 
                                    window.messagingComponent.toolCallHandler &&
                                    typeof window.messagingComponent.toolCallHandler.setFinalResponseGenerating === 'function') {
                                    window.messagingComponent.toolCallHandler.setFinalResponseGenerating(true);
                                }
                                
                                if (typeof onToken === 'function') {
                                    // Process token without accumulating here - let component handle accumulation
                                    const tokenData = parsedData.data || '';
                                    onToken(tokenData);
                                }
                                break;
                                
                            case 'tool_call':
                                if (typeof onToolCall === 'function') {
                                    const toolCall = parsedData.data;
                                    
                                    // Create a unique signature for this tool call to detect duplicates
                                    const toolSignature = `${toolCall.name}:${toolCall.args.replace(/["\s]/g, '')}`;
                                    
                                    // Only process this tool call if we haven't seen it before
                                    if (!toolSignatures.has(toolSignature)) {
                                        toolSignatures.add(toolSignature);
                                        toolCalls.set(toolCall.id, toolCall);
                                        
                                        // Send the tool call to UI
                                        console.log('Tool call detected:', toolCall);
                                        onToolCall(toolCall);
                                    } else {
                                        console.log('Skipping duplicate tool call:', toolSignature);
                                    }
                                }
                                break;
                                
                            case 'tool_update':
                                if (typeof onToolUpdate === 'function') {
                                    const toolUpdate = parsedData.data;
                                    
                                    // Create a unique key for this tool update
                                    const updateKey = `${toolUpdate.id}_${toolUpdate.status}_${toolUpdate.result?.substring(0, 50) || ''}`;
                                    
                                    // Only process this update if we haven't seen it before
                                    if (!processedToolUpdates.has(updateKey)) {
                                        processedToolUpdates.add(updateKey);
                                        
                                        // Update our tracking
                                        if (toolUpdate.id && toolCalls.has(toolUpdate.id)) {
                                            toolCalls.set(toolUpdate.id, {
                                                ...toolCalls.get(toolUpdate.id),
                                                ...toolUpdate
                                            });
                                        }
                                        
                                        // Send the update to UI
                                        console.log('Tool call updated:', toolUpdate);
                                        onToolUpdate(toolUpdate);
                                    }
                                }
                                break;
                                
                            case 'info':
                                console.log(`Info event received: ${parsedData.data}`);
                                if (typeof onInfo === 'function') {
                                    // Pass the temp flag if it exists
                                    onInfo(parsedData.data, parsedData.temp === true);
                                }
                                break;
                                
                            case 'clear_temp_info':
                                console.log('Clear temporary info message event received');
                                if (typeof callbacks.onClearTempInfo === 'function') {
                                    callbacks.onClearTempInfo();
                                }
                                break;
                                
                            case 'recursion_depth':
                                console.log(`Recursion depth event: ${parsedData.data}`);
                                // Send recursion depth event if changed
                                if (parsedData.data !== currentRecursionDepth) {
                                    currentRecursionDepth = parsedData.data;
                                    if (typeof onRecursionDepth === 'function') {
                                        onRecursionDepth(currentRecursionDepth);
                                    }
                                }
                                break;
                                
                            case 'final':
                                console.log(`Final response received: ${parsedData.data}`);
                                
                                // Prevent duplicate responses
                                if (!finalResponseSent && lastSentResponse !== parsedData.data) {
                                    lastSentResponse = parsedData.data;
                                    finalResponseSent = true;
                                    if (typeof onFinalResponse === 'function') {
                                        onFinalResponse(parsedData.data);
                                    }
                                } else {
                                    console.log('Skipping duplicate final response');
                                }
                                break;
                                
                            case 'done':
                                console.log('Done event received');
                                if (typeof onDone === 'function' && !finalResponseSent) {
                                    finalResponseSent = true;
                                    onDone();
                                }
                                break;
                                
                            default:
                                console.log(`Unknown event type: ${parsedData.event}`);
                        }
                    } catch (error) {
                        console.error('Error parsing SSE data:', error, data);
                        if (typeof onError === 'function') {
                            onError(`Error parsing stream data: ${error.message}`);
                        }
                    }
                }
            }
        }
        
        // If we have accumulated tokens, send a final response
        if (accumulatedToken && typeof onFinalResponse === 'function' && !finalResponseSent) {
            // But only if it hasn't been sent already
            if (lastSentResponse !== accumulatedToken) {
                finalResponseSent = true;
                onFinalResponse(accumulatedToken);
            }
        }
        
        console.log('Stream completed');
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Request was aborted');
        } else {
            console.error('Error streaming chat message:', error);
            if (typeof onError === 'function') {
                onError(error.message);
            }
        }
    }
}

/**
 * Reset the conversation on the server
 * @returns {Promise<void>}
 */
export async function resetConversation() {
    try {
        // Try the new URL structure first
        await fetchWithRetry('/chat/reset', { method: 'POST' })
            .catch(async (err) => {
                if (err?.status === 404) {
                    // Fall back to the legacy URL if the new one isn't found
                    console.log('Falling back to legacy reset endpoint');
                    await fetchWithRetry('/reset', { method: 'POST' });
                } else {
                    throw err;
                }
            });
    } catch(err) {
        console.error('Failed to reset conversation on server:', err);
        throw err;
    }
}

/**
 * Update settings on the server
 * @param {Object} settings - The settings to update
 * @returns {Promise<Object>} - The response data
 */
export async function updateSettings(settings) {
    const response = await fetchWithRetry('/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
    });
    
    if (!response.ok) {
        throw new Error('Failed to update settings');
    }
    
    return await response.json();
}

/**
 * Fetch current settings from the server
 * @returns {Promise<Object>} The current settings
 */
export async function getSettings() {
    try {
        const response = await fetch('/api/settings');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching settings:', error);
        throw error;
    }
}
