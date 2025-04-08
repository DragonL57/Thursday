/**
 * Manages conversation storage in the browser's localStorage
 */
export class BrowserStorageManager {
  constructor() {
    this.storagePrefix = 'personal-gem-conversation-';
    this.metadataKey = 'personal-gem-conversations-metadata';
    
    // Initialize metadata if it doesn't exist
    if (!localStorage.getItem(this.metadataKey)) {
      localStorage.setItem(this.metadataKey, JSON.stringify([]));
    }
    
    // Check for storage quota
    this.checkStorageQuota();
  }

  // Check if we're approaching storage limits
  checkStorageQuota() {
    try {
      // Check how much localStorage we're using
      let totalSize = 0;
      for (let key in localStorage) {
        if (localStorage.hasOwnProperty(key)) {
          totalSize += localStorage[key].length * 2; // Approx size in bytes
        }
      }
      
      // Convert to MB for easier understanding
      const usedMB = totalSize / (1024 * 1024);
      console.log(`LocalStorage usage: ~${usedMB.toFixed(2)} MB`);
      
      // Most browsers have ~5MB limit, warn if above 4MB
      if (usedMB > 4) {
        console.warn(`LocalStorage usage warning: ${usedMB.toFixed(2)} MB used (limit ~5MB)`);
      }
    } catch (e) {
      console.error("Error checking storage quota:", e);
    }
  }

  // Save conversation to localStorage
  saveConversation(name, messages, conversationId = null) {
    // Generate an ID if not provided
    const id = conversationId || 'conv-' + Date.now();
    const timestamp = new Date().toISOString();
    
    try {
      // Clean and validate messages to ensure they're serializable
      const cleanedMessages = this.cleanupMessages(messages);
      
      // Save the conversation data
      const conversationData = {
        id: id,
        name: name,
        messages: cleanedMessages,
        timestamp: timestamp
      };
      
      // Serialize to string
      const dataString = JSON.stringify(conversationData);
      
      // Check if this item is too large for localStorage (typically ~2MB)
      if (dataString.length > 1800000) { // Leave some margin below 2MB
        console.warn(`Conversation too large: ${dataString.length} bytes`);
        // Truncate the conversation by removing older messages
        while (dataString.length > 1800000 && conversationData.messages.length > 4) {
          // Keep first system message if present
          const firstMsg = conversationData.messages[0];
          const hasSystem = firstMsg.role === 'system';
          
          // Remove 2 messages (user+assistant pair), but keep system message
          conversationData.messages = hasSystem 
            ? [firstMsg, ...conversationData.messages.slice(3)]
            : conversationData.messages.slice(2);
            
          // Recalculate size
          const newDataString = JSON.stringify(conversationData);
          
          if (newDataString.length >= dataString.length) {
            // We're not making progress, give up and handle error
            throw new Error("Conversation too large to save even after truncating");
          }
          
          // Update for next iteration
          dataString = newDataString;
        }
      }
      
      localStorage.setItem(this.storagePrefix + id, dataString);
      
      // Update the metadata index
      this.updateMetadata(id, name, timestamp);
      
      return conversationData;
    } catch (error) {
      console.error("Failed to save conversation:", error);
      
      // Try a more aggressive approach if regular save failed
      if (messages.length > 4) {
        try {
          console.log("Attempting to save truncated conversation");
          // Keep only the most recent messages (last 2 exchanges)
          const truncatedMessages = messages.slice(-4);
          
          // Add a system message explaining the truncation
          truncatedMessages.unshift({
            role: "system",
            content: "Note: This conversation was truncated due to size constraints."
          });
          
          const truncatedData = {
            id: id,
            name: name + " (truncated)",
            messages: truncatedMessages,
            timestamp: timestamp
          };
          
          localStorage.setItem(this.storagePrefix + id, JSON.stringify(truncatedData));
          this.updateMetadata(id, name + " (truncated)", timestamp);
          
          return truncatedData;
        } catch (fallbackError) {
          console.error("Failed to save even truncated conversation:", fallbackError);
          throw fallbackError;
        }
      }
      
      throw error;
    }
  }

  // Clean up messages to ensure they're JSON serializable
  cleanupMessages(messages) {
    return messages.map(msg => {
      // Create a fresh copy with only essential fields
      const cleanMsg = {
        role: msg.role,
        content: msg.content || ""
      };
      
      // Handle non-string content (like multimodal content arrays)
      if (Array.isArray(cleanMsg.content)) {
        cleanMsg.content = cleanMsg.content.map(item => {
          if (typeof item === 'string') {
            return item;
          } else if (typeof item === 'object') {
            // Keep only serializable properties
            return {
              type: item.type || 'text',
              text: item.text || '',
              // Include minimal image data if present
              ...(item.type === 'image_url' && item.image_url ? {
                image_url: {
                  url: typeof item.image_url === 'object' ? 
                    item.image_url.url || '' : 
                    item.image_url || ''
                }
              } : {})
            };
          }
          // Default fallback
          return String(item);
        });
      } else if (cleanMsg.content === null || cleanMsg.content === undefined) {
        cleanMsg.content = "";
      } else if (typeof cleanMsg.content !== 'string') {
        // Convert to string if not already
        cleanMsg.content = String(cleanMsg.content);
      }
      
      // Add tool fields if present
      if (msg.tool_call_id) {
        cleanMsg.tool_call_id = msg.tool_call_id;
      }
      
      if (msg.name) {
        cleanMsg.name = msg.name;
      }
      
      // Copy tool calls if present (deep copy to ensure clean serialization)
      if (msg.tool_calls && Array.isArray(msg.tool_calls)) {
        cleanMsg.tool_calls = msg.tool_calls.map(tc => {
          if (typeof tc === 'object') {
            return {
              id: tc.id || '',
              type: tc.type || 'function',
              function: {
                name: tc.function?.name || '',
                arguments: tc.function?.arguments || '{}'
              }
            };
          }
          return {};
        });
      }
      
      return cleanMsg;
    });
  }

  // Get all conversations (metadata only)
  getConversations() {
    try {
      const metadata = localStorage.getItem(this.metadataKey);
      if (!metadata) return [];
      
      return JSON.parse(metadata).sort((a, b) => 
        new Date(b.timestamp) - new Date(a.timestamp)
      );
    } catch (error) {
      console.error('Error getting conversations from localStorage:', error);
      return [];
    }
  }

  // Load a specific conversation
  loadConversation(conversationId) {
    try {
      if (conversationId === 'current') {
        return { 
          id: 'current', 
          name: 'Current Conversation', 
          messages: [],
          isExistingConversation: false
        };
      }
      
      const data = localStorage.getItem(this.storagePrefix + conversationId);
      if (!data) return null;
      
      const conversation = JSON.parse(data);
      
      // Validate the loaded conversation
      if (!conversation || !conversation.messages || !Array.isArray(conversation.messages)) {
        console.error("Invalid conversation format loaded from storage");
        return null;
      }
      
      // Add flags to indicate this is a saved conversation
      conversation.isExistingConversation = true;
      conversation.conversationId = conversation.id;
      
      return conversation;
    } catch (error) {
      console.error(`Error loading conversation ${conversationId}:`, error);
      return null;
    }
  }

  // Delete a conversation
  deleteConversation(conversationId) {
    try {
      // Remove the conversation
      localStorage.removeItem(this.storagePrefix + conversationId);
      
      // Update metadata
      this.removeFromMetadata(conversationId);
      
      return true;
    } catch (error) {
      console.error(`Error deleting conversation ${conversationId}:`, error);
      return false;
    }
  }
  
  // Helper method to update metadata when saving a conversation
  updateMetadata(id, name, timestamp) {
    try {
      let metadata = [];
      const metadataStr = localStorage.getItem(this.metadataKey);
      
      if (metadataStr) {
        metadata = JSON.parse(metadataStr);
      }
      
      // Check if this conversation already exists in metadata
      const existingIndex = metadata.findIndex(item => item.id === id);
      
      if (existingIndex >= 0) {
        // Update existing entry
        metadata[existingIndex] = { id, name, timestamp };
      } else {
        // Add new entry
        metadata.push({ id, name, timestamp });
      }
      
      // Save updated metadata
      localStorage.setItem(this.metadataKey, JSON.stringify(metadata));
    } catch (error) {
      console.error('Error updating conversation metadata:', error);
    }
  }
  
  // Helper method to remove from metadata when deleting
  removeFromMetadata(id) {
    try {
      const metadataStr = localStorage.getItem(this.metadataKey);
      if (!metadataStr) return;
      
      let metadata = JSON.parse(metadataStr);
      
      // Filter out the deleted conversation
      metadata = metadata.filter(item => item.id !== id);
      
      // Save updated metadata
      localStorage.setItem(this.metadataKey, JSON.stringify(metadata));
    } catch (error) {
      console.error('Error removing conversation from metadata:', error);
    }
  }
  
  // Update conversation content (rename)
  renameConversation(id, newName) {
    try {
      // Load the conversation
      const data = localStorage.getItem(this.storagePrefix + id);
      if (!data) return null;
      
      const conversation = JSON.parse(data);
      
      // Update the name
      conversation.name = newName;
      
      // Save changes
      localStorage.setItem(this.storagePrefix + id, JSON.stringify(conversation));
      
      // Update metadata
      this.updateMetadata(id, newName, conversation.timestamp);
      
      return conversation;
    } catch (error) {
      console.error(`Error renaming conversation ${id}:`, error);
      return null;
    }
  }
  
  // Update conversation content with new messages - with more robust error handling
  updateConversationContent(id, messages) {
    try {
      // Load the conversation
      const data = localStorage.getItem(this.storagePrefix + id);
      if (!data) return null;
      
      const conversation = JSON.parse(data);
      
      // Clean up messages to ensure they're serializable
      const cleanedMessages = this.cleanupMessages(messages);
      
      // Update the messages
      conversation.messages = cleanedMessages;
      
      // Update the timestamp to show it was modified
      conversation.timestamp = new Date().toISOString();
      
      // Save changes
      localStorage.setItem(this.storagePrefix + id, JSON.stringify(conversation));
      
      // Also update timestamp in metadata
      this.updateMetadata(id, conversation.name, conversation.timestamp);
      
      return conversation;
    } catch (error) {
      console.error(`Error updating conversation content ${id}:`, error);
      return null;
    }
  }
}
