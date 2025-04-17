export class ModelSelector {
    constructor(settingsManager) {
        this.settingsManager = settingsManager;
        this.dropdownButton = null;
        this.dropdownContent = null;
        this.currentModelName = null;
        this.isInitialized = false;
        this.currentModel = 'gemini/gemini-2.0-flash'; // Default model
        
        // Create the dropdown elements
        this.createDropdown();
        
        // Load models from settings
        this.loadModels();
    }
    
    createDropdown() {
        // Create the main container
        this.dropdownButton = document.createElement('div');
        this.dropdownButton.className = 'model-selector-dropdown';
        
        // Create the button
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'model-selector-button';
        
        // Create the model name span with default Gemini 2.0 Flash
        this.currentModelName = document.createElement('span');
        this.currentModelName.className = 'current-model-name';
        this.currentModelName.textContent = 'Gemini 2.0 Flash';
        this.currentModelName.title = 'Gemini 2.0 Flash';
        
        // Create the dropdown icon
        const icon = document.createElement('span');
        icon.className = 'material-icons-round model-selector-icon';
        icon.textContent = 'expand_more';
        
        // Create the dropdown content
        this.dropdownContent = document.createElement('div');
        this.dropdownContent.className = 'model-dropdown-content';
        
        // Assemble the elements
        button.appendChild(this.currentModelName);
        button.appendChild(icon);
        this.dropdownButton.appendChild(button);
        this.dropdownButton.appendChild(this.dropdownContent);
        
        // Add click handler to toggle dropdown
        button.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.toggleDropdown();
        });
        
        // Add click handler to close dropdown when clicking outside
        document.addEventListener('click', () => {
            this.closeDropdown();
        });
    }
    
    async loadModels() {
        try {
            console.log('Loading models from settings...');
            // Get current settings to determine available models and current model
            const settings = await this.settingsManager.fetchCurrentSettings();
            console.log('Settings loaded:', settings);
            
            if (settings && settings.model) {
                this.currentModel = settings.model;
                console.log('Current model set to:', this.currentModel);
            } else {
                console.log('No model found in settings, using default');
                this.currentModel = 'openai';
            }
            
            // Update the current model name
            this.updateCurrentModelDisplay();
            
            // Clear dropdown content
            this.dropdownContent.innerHTML = '';
            
            // Add Pollinations models
            this.addModelOption('openai', 'OpenAI', 'pollinations');
            this.addModelOption('mistral', 'Mistral', 'pollinations');
            this.addModelOption('openai-large', 'OpenAI Large', 'pollinations');
            
            this.isInitialized = true;
            console.log('Model selector initialized with Pollinations options');
            
        } catch (error) {
            console.error('Error loading models:', error);
            // Even if there's an error, still create the dropdown option
            this.dropdownContent.innerHTML = '';
            this.addModelOption('gemini/gemini-2.0-flash', 'Gemini 2.0 Flash', 'litellm');
            this.isInitialized = true;
        }
    }
    
    // Helper to add a model option to the dropdown
    addModelOption(value, name, provider) {
        const modelOption = document.createElement('div');
        modelOption.className = `model-option ${value === this.currentModel ? 'active' : ''}`;
        modelOption.textContent = name;
        modelOption.dataset.value = value;
        modelOption.dataset.provider = provider;
        
        // Add click handler
        modelOption.addEventListener('click', (e) => {
            e.stopPropagation();
            this.selectModel(value, provider);
            this.closeDropdown();
        });
        
        this.dropdownContent.appendChild(modelOption);
    }
    
    // Get a cleaned display name for the model
    getDisplayName(fullName) {
        // Remove provider prefix if present
        const withoutProvider = fullName.replace(/^LiteLLM:\s*/, '');
        return withoutProvider;
    }
    
    updateCurrentModelDisplay() {
        if (!this.currentModel) {
            this.currentModelName.textContent = 'OpenAI';
            return;
        }
        
        // Directly map the known model values to display names
        if (this.currentModel === 'openai') {
            this.currentModelName.textContent = 'OpenAI';
            this.currentModelName.title = 'OpenAI';
        } else if (this.currentModel === 'mistral') {
            this.currentModelName.textContent = 'Mistral';
            this.currentModelName.title = 'Mistral';
        } else if (this.currentModel === 'openai-large') {
            this.currentModelName.textContent = 'OpenAI Large';
            this.currentModelName.title = 'OpenAI Large';
        } else {
            // Fallback for any other model value
            const modelName = this.currentModel.split('/').pop() || this.currentModel;
            this.currentModelName.textContent = modelName;
            this.currentModelName.title = this.currentModel;
        }
    }
    
    async selectModel(modelValue, providerValue) {
        try {
            // Update the dropdown UI first
            this.currentModel = modelValue;
            this.updateCurrentModelDisplay();
            
            // Update all model options
            const options = this.dropdownContent.querySelectorAll('.model-option');
            options.forEach(option => {
                option.classList.toggle('active', option.dataset.value === modelValue);
            });
            
            // Update the model in settings and the select element
            const settings = {
                provider: providerValue,
                model: modelValue
            };
            
            // Call API to update model without closing the settings modal
            await this.settingsManager.updateModelSilently(settings);
            
            // Also update the select element if it exists
            const modelSelect = document.getElementById('modelSelect');
            if (modelSelect) {
                modelSelect.value = modelValue;
            }
            
            // Dispatch event for model change so other components can react
            const event = new CustomEvent('modelChanged', {
                detail: { provider: providerValue, model: modelValue }
            });
            document.dispatchEvent(event);
            
            console.log(`Model switched to ${modelValue} (${providerValue})`);
        } catch (error) {
            console.error('Error switching model:', error);
        }
    }
    
    // Add a method to get the current model
    getCurrentModel() {
        return this.currentModel;
    }
    
    toggleDropdown() {
        console.log('Toggling dropdown, current state:', this.dropdownContent.classList.contains('active'));
        const wasActive = this.dropdownContent.classList.contains('active');
        this.dropdownContent.classList.toggle('active');
        
        // Force display value changes along with class toggle
        this.dropdownContent.style.display = wasActive ? 'none' : 'flex';
        
        // Force a reflow to ensure the dropdown is visible
        if (!wasActive) {
            this.dropdownContent.getBoundingClientRect();
        }
    }
    
    closeDropdown() {
        this.dropdownContent.classList.remove('active');
        this.dropdownContent.style.display = 'none';
    }
    
    // Mount the dropdown to a specific element
    mount(element) {
        if (element && this.dropdownButton) {
            element.prepend(this.dropdownButton);
        }
    }
}
