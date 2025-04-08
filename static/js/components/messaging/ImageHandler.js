export class ImageHandler {
    constructor(messagingComponent) {
        this.messagingComponent = messagingComponent;
        this.imagePreviewContainer = document.getElementById('imagePreviewContainer');
        this.maxSizeMB = 4; // Maximum image size in MB
        this.maxSizeBytes = this.maxSizeMB * 1024 * 1024;
    }
    
    // Handle paste events to capture images
    handlePaste(e) {
        const items = e.clipboardData?.items;
        if (!items) return;
        
        // Look for image items in the clipboard
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                // Convert the image to a File object
                const file = items[i].getAsFile();
                if (file) {
                    this.processImageFile(file);
                    // Prevent the image from being pasted as a blob URL
                    e.preventDefault();
                    break;
                }
            }
        }
    }
    
    // Process an image file and show preview
    processImageFile(file) {
        // Validate file size
        if (!this._validateFileSize(file)) {
            return;
        }
        
        // Process valid file
        this._readAndStoreImage(file);
    }
    
    // Format image data for API based on selected model provider
    getFormattedImageData() {
        const component = this.messagingComponent;
        if (!component.currentImageData || !component.imageMetadata) {
            return null;
        }
        
        // Get current provider and model information
        const providerInfo = this._getProviderInfo();
        console.log(`Formatting image for provider: ${providerInfo.provider}, model: ${providerInfo.model}`);
        
        // Format based on provider and model
        if (providerInfo.provider === 'pollinations') {
            // Pollinations format - send base64 directly
            return component.currentImageData;
        } else {
            // For LiteLLM providers
            if (providerInfo.model.includes('gemini')) {
                return this._formatForGemini(component.currentImageData);
            } else if (providerInfo.model.includes('github')) {
                // GitHub models need image data as a URL, not base64
                return this._formatForGitHub(component.currentImageData);
            } else {
                // Default format for other LiteLLM models
                return this._formatForStandardLLM(component.currentImageData);
            }
        }
    }
    
    // Show image preview in the UI with improved styling
    showImagePreview(dataUrl) {
        if (!this.imagePreviewContainer) {
            console.error('Image preview container not found');
            return;
        }
        
        // Clear any existing content
        this.imagePreviewContainer.innerHTML = '';
        
        // Create preview elements with better styling
        const imagePreview = document.createElement('div');
        imagePreview.className = 'image-preview';
        
        const img = document.createElement('img');
        img.src = dataUrl;
        img.alt = 'Preview';
        
        // Add control elements
        const removeBtn = this._createRemoveButton();
        const sizeIndicator = this._createSizeIndicator();
        
        // Assemble and show the preview
        imagePreview.appendChild(img);
        imagePreview.appendChild(removeBtn);
        imagePreview.appendChild(sizeIndicator);
        this.imagePreviewContainer.appendChild(imagePreview);
        
        // Show the container
        this.imagePreviewContainer.classList.remove('hidden');
    }
    
    // Clear the current image attachment
    clearImageAttachment() {
        const component = this.messagingComponent;
        
        component.currentImageData = null;
        component.imageMetadata = null;
        
        this.clearImagePreview();
        
        // Disable send button if text is also empty
        if (component.userInput && !component.userInput.value.trim()) {
            component.sendButton.disabled = true;
        }
    }
    
    // New method to just clear the visual preview (without affecting send button)
    clearImagePreview() {
        if (this.imagePreviewContainer) {
            this.imagePreviewContainer.innerHTML = '';
            this.imagePreviewContainer.classList.add('hidden');
        }
    }
    
    // PRIVATE HELPER METHODS
    
    _validateFileSize(file) {
        const component = this.messagingComponent;
        
        if (file.size > this.maxSizeBytes) { 
            component.addInfoMessage(
                `Image is too large. Please use an image smaller than ${this.maxSizeMB}MB.`, 
                false, 
                true
            );
            return false;
        }
        return true;
    }
    
    _readAndStoreImage(file) {
        const component = this.messagingComponent;
        const reader = new FileReader();
        
        reader.onload = (e) => {
            const dataUrl = e.target.result;
            
            // Store the image data with metadata
            component.currentImageData = dataUrl;
            component.imageMetadata = {
                dataUrl: dataUrl,
                originalFile: file,
                size: file.size,
                type: file.type
            };
            
            this.showImagePreview(dataUrl);
            
            // Enable send button even if text is empty
            component.sendButton.disabled = false;
        };
        
        reader.readAsDataURL(file);
    }
    
    _createRemoveButton() {
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'remove-image';
        removeBtn.innerHTML = '×';
        removeBtn.title = 'Remove image';
        
        // Add event listener to remove button
        removeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.clearImageAttachment();
        });
        
        return removeBtn;
    }
    
    _createSizeIndicator() {
        const sizeIndicator = document.createElement('span');
        sizeIndicator.className = 'image-size-indicator';
        
        // Add size info if available
        if (this.messagingComponent.imageMetadata) {
            const size = (this.messagingComponent.imageMetadata.size / (1024 * 1024)).toFixed(1);
            sizeIndicator.textContent = `${size} MB`;
        }
        
        return sizeIndicator;
    }
    
    _getProviderInfo() {
        const providerSelect = document.getElementById('providerSelect');
        const modelSelect = document.getElementById('modelSelect');
        
        return {
            provider: providerSelect ? providerSelect.value : 'pollinations',
            model: modelSelect ? modelSelect.value : ''
        };
    }
    
    _formatForGemini(imageData) {
        console.log('Using Gemini-specific format for image');
        
        try {
            // Validate the image data format
            if (!imageData.startsWith('data:image/')) {
                console.error('Invalid image format for Gemini');
                return null;
            }
            
            // Check image size limitation
            const approximateSizeInMB = (imageData.length * 0.75) / (1024 * 1024);
            console.log(`Approximate image size: ${approximateSizeInMB.toFixed(2)} MB`);
            
            if (approximateSizeInMB > 10) {
                console.warn('Image may be too large for Gemini API');
            }
            
            // For Gemini, we just need the raw data URL - the backend will handle formatting
            return imageData;
            
        } catch (error) {
            console.error('Error formatting image for Gemini:', error);
            return null;
        }
    }
    
    // New method specifically for GitHub models
    _formatForGitHub(imageData) {
        console.log('Using GitHub-specific format for image');
        
        try {
            // Validate the image data format
            if (!imageData.startsWith('data:image/')) {
                console.error('Invalid image format for GitHub model');
                return null;
            }
            
            // GitHub API seems to require public URLs, not base64
            // For now, we'll send only the base64 and let the backend
            // handle the conversion or error gracefully
            console.log('Sending base64 image to backend for GitHub model processing');
            
            // Just return the raw image data and let backend handle it
            return imageData;
        } catch (error) {
            console.error('Error formatting image for GitHub:', error);
            return null;
        }
    }
    
    _formatForStandardLLM(imageData) {
        console.log('Using standard LiteLLM format for image');
        
        return [{
            type: 'image_url',
            image_url: {
                url: imageData
            }
        }];
    }
}
