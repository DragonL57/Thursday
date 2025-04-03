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
async function fetchWithRetry(url, options, retries = 3, baseDelay = 500, maxDelay = 5000) {
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
 * Send a message to the backend
 * @param {string} message - The message to send
 * @returns {Promise<Object>} - The response data
 */
export async function sendChatMessage(message) {
    try {
        const response = await fetchWithRetry('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
        });
        
        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error sending chat message:', error);
        throw error;
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
