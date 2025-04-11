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
        
        console.log('Using Gemini image format');
        return component.currentImageData;
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
        img.style.maxHeight = '150px';
        img.style.maxWidth = '100%';
        img.style.borderRadius = '8px';
        
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
        removeBtn.style.position = 'absolute';
        removeBtn.style.top = '5px';
        removeBtn.style.right = '5px';
        removeBtn.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        removeBtn.style.color = 'white';
        removeBtn.style.borderRadius = '50%';
        removeBtn.style.width = '24px';
        removeBtn.style.height = '24px';
        removeBtn.style.display = 'flex';
        removeBtn.style.alignItems = 'center';
        removeBtn.style.justifyContent = 'center';
        removeBtn.style.cursor = 'pointer';
        removeBtn.style.border = 'none';
        
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
        sizeIndicator.style.position = 'absolute';
        sizeIndicator.style.bottom = '5px';
        sizeIndicator.style.left = '5px';
        sizeIndicator.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        sizeIndicator.style.color = 'white';
        sizeIndicator.style.padding = '2px 6px';
        sizeIndicator.style.borderRadius = '4px';
        sizeIndicator.style.fontSize = '12px';
        
        // Add size info if available
        if (this.messagingComponent.imageMetadata) {
            const size = (this.messagingComponent.imageMetadata.size / (1024 * 1024)).toFixed(1);
            sizeIndicator.textContent = `${size} MB`;
        }
        
        return sizeIndicator;
    }
}
