export class ModelSelector {
    constructor(settingsManager) {
        this.settingsManager = settingsManager;
        this.dropdownButton = null;
        this.dropdownContent = null;
        this.currentModelName = null;
        this.isInitialized = false;
        this.currentModel = 'openai-large'; // Set default model to Pollinations GPT-4o
        
        // Create the dropdown elements
        this.createDropdown();
        
        // Load models from settings
        this.loadModels();
        
        // Add a fallback to check models after a short delay
        setTimeout(() => {
            if (!this.isInitialized || this.dropdownContent.children.length === 0) {
                console.log('Model dropdown not initialized or empty, trying again...');
                this.loadModelsDirectly();
            }
        }, 1000);
    }
    
    createDropdown() {
        // Create the main container
        this.dropdownButton = document.createElement('div');
        this.dropdownButton.className = 'model-selector-dropdown';
        
        // Create the button
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'model-selector-button';
        
        // Create the model name span with default Pollinations GPT-4o
        this.currentModelName = document.createElement('span');
        this.currentModelName.className = 'current-model-name';
        this.currentModelName.textContent = 'Pollinations: GPT-4o'; // Set default display text
        this.currentModelName.title = 'Pollinations GPT-4o'; // Set default tooltip
        
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
                // Handle migration from integrated model to separate models
                if (settings.model === 'gpt4o-integrated') {
                    // Migrate to the pollinations model by default
                    this.currentModel = 'openai-large';
                    console.log('Migrating from integrated model to:', this.currentModel);
                    
                    // Update the settings silently
                    await this.settingsManager.updateModelSilently({
                        provider: 'pollinations',
                        model: 'openai-large'
                    });
                } else {
                    this.currentModel = settings.model;
                    console.log('Current model set to:', this.currentModel);
                }
            } else {
                console.warn('No model found in settings, using default');
            }
            
            // Update the current model name
            this.updateCurrentModelDisplay();
            
            // Get all model options
            const modelSelect = document.getElementById('modelSelect');
            if (!modelSelect) {
                console.error('Model select element not found in DOM');
                return;
            }
            
            console.log(`Found ${modelSelect.options.length} model options`);
            
            // Clear existing options
            this.dropdownContent.innerHTML = '';
            
            // Add options for each available model
            if (modelSelect.options.length === 0) {
                console.warn('No model options found in select element');
                this.addDefaultModels();
                return;
            }
            
            Array.from(modelSelect.options).forEach(option => {
                console.log(`Adding model option: ${option.textContent} (${option.value})`);
                const modelOption = document.createElement('div');
                modelOption.className = `model-option ${option.value === this.currentModel ? 'active' : ''}`;
                modelOption.textContent = this.getDisplayName(option.textContent);
                modelOption.dataset.value = option.value;
                modelOption.dataset.provider = option.dataset.provider || 'unknown';
                
                // Add click handler
                modelOption.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.selectModel(option.value, option.dataset.provider || 'unknown');
                    this.closeDropdown();
                });
                
                this.dropdownContent.appendChild(modelOption);
            });
            
            this.isInitialized = true;
            console.log('Model selector initialized with', this.dropdownContent.children.length, 'options');
        } catch (error) {
            console.error('Error loading models from settings:', error);
            this.currentModelName.textContent = 'Model selection';
            // Try to load models directly as fallback
            this.loadModelsDirectly();
        }
    }
    
    // New method to load models directly from the DOM
    loadModelsDirectly() {
        console.log('Loading models directly from DOM...');
        const modelSelect = document.getElementById('modelSelect');
        if (!modelSelect) {
            console.error('Model select element not found in DOM');
            this.addDefaultModels();
            return;
        }
        
        // Clear existing options
        this.dropdownContent.innerHTML = '';
        
        if (modelSelect.options.length === 0) {
            console.warn('No model options found when loading directly');
            this.addDefaultModels();
            return;
        }
        
        // Set default current model if needed
        if (!this.currentModel && modelSelect.value) {
            this.currentModel = modelSelect.value;
            console.log('Setting current model from select element:', this.currentModel);
        }
        
        // Add options for each available model
        Array.from(modelSelect.options).forEach(option => {
            console.log(`Adding model option directly: ${option.textContent} (${option.value})`);
            const modelOption = document.createElement('div');
            modelOption.className = `model-option ${option.value === this.currentModel ? 'active' : ''}`;
            modelOption.textContent = this.getDisplayName(option.textContent);
            modelOption.dataset.value = option.value;
            modelOption.dataset.provider = option.dataset.provider || 'unknown';
            
            // Add click handler
            modelOption.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectModel(option.value, option.dataset.provider || 'unknown');
                this.closeDropdown();
            });
            
            this.dropdownContent.appendChild(modelOption);
        });
        
        this.updateCurrentModelDisplay();
        this.isInitialized = true;
        console.log('Model selector initialized directly with', this.dropdownContent.children.length, 'options');
    }
    
    // Add some default models if nothing else works
    addDefaultModels() {
        console.log('Adding default models...');
        const defaultModels = [
            { value: 'openai-large', provider: 'pollinations', name: 'Pollinations: GPT-4o' },
            { value: 'github/gpt-4o', provider: 'litellm', name: 'GitHub: GPT-4o' },
            { value: 'gemini/gemini-2.0-flash', provider: 'litellm', name: 'Gemini 2.0 Flash' }
        ];
        
        // Clear existing options
        this.dropdownContent.innerHTML = '';
        
        // Add default model options
        defaultModels.forEach(model => {
            const modelOption = document.createElement('div');
            modelOption.className = `model-option ${model.value === this.currentModel ? 'active' : ''}`;
            modelOption.textContent = model.name;
            modelOption.dataset.value = model.value;
            modelOption.dataset.provider = model.provider;
            
            // Add click handler
            modelOption.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectModel(model.value, model.provider);
                this.closeDropdown();
            });
            
            this.dropdownContent.appendChild(modelOption);
        });
        
        // Set default current model if needed
        if (!this.currentModel) {
            this.currentModel = defaultModels[0].value;
        }
        
        this.updateCurrentModelDisplay();
    }
    
    // Get a cleaned display name for the model
    getDisplayName(fullName) {
        // First remove provider prefix if present (e.g., "LiteLLM: Gemini 2.0 Flash" -> "Gemini 2.0 Flash")
        const withoutProvider = fullName.replace(/^(LiteLLM|Pollinations):\s*/, '');
        
        // Format GitHub models nicely
        if (withoutProvider.toLowerCase().includes('github')) {
            // Transform "GitHub GPT-4o" to "GitHub: GPT-4o"
            return withoutProvider.replace(/github(\s*)(\/)?\s*(.+)/i, 'GitHub: $3');
        }
        
        return withoutProvider;
    }
    
    updateCurrentModelDisplay() {
        if (!this.currentModel) {
            this.currentModelName.textContent = 'Pollinations: GPT-4o'; // Default to Pollinations GPT-4o
            return;
        }
        
        const modelSelect = document.getElementById('modelSelect');
        if (!modelSelect) {
            // Use a simple name based on the value
            const modelName = this.currentModel.split('/').pop() || this.currentModel;
            this.currentModelName.textContent = modelName;
            this.currentModelName.title = this.currentModel;
            return;
        }
        
        const selectedOption = Array.from(modelSelect.options).find(option => option.value === this.currentModel);
        if (selectedOption) {
            this.currentModelName.textContent = selectedOption.text;
            this.currentModelName.title = selectedOption.text;
        } else {
            this.currentModelName.textContent = this.getDisplayName(this.currentModel);
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
            
            // Update the model in settings
            const settings = {
                provider: providerValue,
                model: modelValue
            };
            
            // Call API to update model without closing the settings modal
            await this.settingsManager.updateModelSilently(settings);
            
            // No need to reload the page or reset conversation
            console.log(`Model switched to ${modelValue} (${providerValue})`);
        } catch (error) {
            console.error('Error switching model:', error);
        }
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
