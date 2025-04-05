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
 * @param {Function} callbacks.onError - Called when an error occurs
 * @param {Function} callbacks.onDone - Called when the stream is complete
 * @returns {Promise<void>}
 */
export async function streamChatMessage(message, imageData = null, callbacks = {}) {
    const { onToken, onToolCall, onToolUpdate, onFinalResponse, onError, onDone } = callbacks;
    
    // Create a new AbortController for this request
    currentController = new AbortController();
    const signal = currentController.signal;
    
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
        
        // Create event source from response body
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let buffer = '';
        let currentContent = '';
        
        while (true) {
            const { value, done } = await reader.read();
            
            if (done) {
                if (typeof onDone === 'function') {
                    onDone();
                }
                break;
            }
            
            buffer += decoder.decode(value, { stream: true });
            
            // Process complete events in the buffer
            let eventEnd = buffer.indexOf('\n\n');
            while (eventEnd >= 0) {
                const eventData = buffer.substring(0, eventEnd).trim();
                buffer = buffer.substring(eventEnd + 2);
                
                // Parse SSE data format
                if (eventData.startsWith('data: ')) {
                    try {
                        const parsedData = JSON.parse(eventData.substring(6));
                        
                        // Handle different event types
                        switch (parsedData.event) {
                            case 'token':
                                if (typeof onToken === 'function') {
                                    onToken(parsedData.data);
                                    currentContent += parsedData.data;
                                }
                                break;
                                
                            case 'tool_call':
                                if (typeof onToolCall === 'function') {
                                    onToolCall(parsedData.data);
                                }
                                break;
                                
                            case 'tool_update':
                                if (typeof onToolUpdate === 'function') {
                                    onToolUpdate(parsedData.data);
                                }
                                break;
                                
                            case 'final':
                                if (typeof onFinalResponse === 'function') {
                                    onFinalResponse(parsedData.data);
                                }
                                break;
                                
                            case 'error':
                                if (typeof onError === 'function') {
                                    onError(parsedData.data);
                                }
                                break;
                                
                            case 'done':
                                if (typeof onDone === 'function') {
                                    onDone();
                                }
                                break;
                        }
                    } catch (e) {
                        console.error('Error parsing SSE data:', e);
                    }
                }
                
                eventEnd = buffer.indexOf('\n\n');
            }
        }
    } catch (error) {
        // Check if this is an abort error
        if (error.name === 'AbortError') {
            console.log('Request was aborted');
        } else {
            console.error('Error streaming chat message:', error);
            if (typeof onError === 'function') {
                onError(error.message);
            }
        }
        
        if (typeof onDone === 'function') {
            onDone();
        }
    } finally {
        // Clear the current controller reference
        currentController = null;
    }
}

/**
 * Reset the conversation on the server
 * @returns {Promise<void>}
 */
export async function resetConversation() {
    try {
        await fetchWithRetry('/reset', { method: 'POST' });
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
