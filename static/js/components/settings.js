import { updateSettings, getSettings } from '../utils/api.js';

export class SettingsManager {
    constructor(elements, messagingComponent, themeManager) {
        this.settingsButton = elements.settingsButton;
        this.settingsModal = elements.settingsModal;
        this.closeModalButtons = elements.closeModalButtons;
        this.saveSettingsButton = elements.saveSettingsButton;
        this.temperatureSlider = elements.temperatureSlider;
        this.temperatureValue = elements.temperatureValue;
        this.maxTokensInput = elements.maxTokensInput;
        this.providerSelect = elements.providerSelect;
        this.modelSelect = elements.modelSelect;
        this.saveChatHistory = elements.saveChatHistory;
        this.messagingComponent = messagingComponent;
        this.themeManager = themeManager;
        
        this.init();
        this.fetchCurrentSettings();
    }
    
    init() {
        // Open settings modal - only if settingsButton exists
        if (this.settingsButton) {
            this.settingsButton.addEventListener('click', () => {
                if (this.settingsModal) {
                    this.settingsModal.classList.add('active');
                }
            });
        }
        
        // Close settings modal
        if (this.closeModalButtons) {
            this.closeModalButtons.forEach(button => {
                button.addEventListener('click', () => {
                    if (this.settingsModal) {
                        this.settingsModal.classList.remove('active');
                    }
                });
            });
        }
        
        // Update temperature value display
        if (this.temperatureSlider && this.temperatureValue) {
            this.temperatureSlider.addEventListener('input', () => {
                this.temperatureValue.textContent = this.temperatureSlider.value;
            });
        }
        
        // Handle provider selection change
        if (this.providerSelect) {
            this.providerSelect.addEventListener('change', () => {
                this.updateModelOptions();
            });
        }

        // Save settings
        if (this.saveSettingsButton) {
            this.saveSettingsButton.addEventListener('click', () => {
                this.saveSettings();
                // Apply theme from settings
                if (this.themeManager) {
                    this.themeManager.applyThemeFromSettings();
                }
            });
        }
    }
    
    updateModelOptions() {
        const selectedProvider = this.providerSelect.value;
        const options = Array.from(this.modelSelect.options);
        
        // Show only models for selected provider
        options.forEach(option => {
            if (option.dataset.provider === selectedProvider) {
                option.style.display = '';
            } else {
                option.style.display = 'none';
            }
        });
        
        // Select first available model for provider
        const firstAvailableOption = options.find(option => 
            option.dataset.provider === selectedProvider && option.style.display !== 'none'
        );
        if (firstAvailableOption) {
            this.modelSelect.value = firstAvailableOption.value;
        }
    }

    async fetchCurrentSettings() {
        try {
            const settings = await getSettings();
            
            // Update UI with current settings
            if (settings.provider) {
                this.providerSelect.value = settings.provider;
                this.updateModelOptions();
            }

            if (settings.model) {
                // Only set model if it's available for current provider
                const modelOption = Array.from(this.modelSelect.options)
                    .find(option => option.value === settings.model && 
                                  option.dataset.provider === settings.provider);
                if (modelOption) {
                    this.modelSelect.value = settings.model;
                }
            }
            
            if (settings.temperature !== undefined) {
                // Ensure the temperature is properly formatted
                const tempValue = parseFloat(settings.temperature);
                this.temperatureSlider.value = tempValue;
                this.temperatureValue.textContent = tempValue;
                
                // Log to confirm we're getting the right value
                console.log('Server temperature setting:', tempValue);
            }
            
            if (settings.max_tokens !== undefined) {
                this.maxTokensInput.value = settings.max_tokens;
                console.log('Server max_tokens setting:', settings.max_tokens);
            }
            
            if (settings.save_history !== undefined) {
                this.saveChatHistory.checked = settings.save_history;
            }
            
            console.log('Loaded server settings:', settings);
        } catch (error) {
            console.error('Error fetching settings:', error);
        }
    }
    
    async updateModelSilently(settings) {
        try {
            // Only update necessary fields
            const update = {
                provider: settings.provider,
                model: settings.model
            };
            
            // Keep current values for other fields
            if (this.temperatureSlider) {
                update.temperature = parseFloat(this.temperatureSlider.value);
            }
            
            if (this.maxTokensInput) {
                update.max_tokens = parseInt(this.maxTokensInput.value);
            }
            
            if (this.saveChatHistory) {
                update.save_history = this.saveChatHistory.checked;
            }
            
            // Update settings via API
            await updateSettings(update);
            
            // Update the UI to reflect the change
            if (settings.provider && this.providerSelect) {
                this.providerSelect.value = settings.provider;
            }
            
            if (settings.model && this.modelSelect) {
                // Update the model select if the option exists
                const modelOption = Array.from(this.modelSelect.options)
                    .find(option => option.value === settings.model);
                    
                if (modelOption) {
                    this.modelSelect.value = settings.model;
                }
            }
            
            return true;
        } catch (error) {
            console.error('Error updating model silently:', error);
            return false;
        }
    }
    
    async saveSettings() {
        const settings = {
            provider: this.providerSelect.value,
            model: this.modelSelect.value,
            temperature: parseFloat(this.temperatureSlider.value),
            max_tokens: parseInt(this.maxTokensInput.value),
            save_history: this.saveChatHistory.checked
        };
        
        try {
            await updateSettings(settings);
            this.settingsModal.classList.remove('active');
            // Remove toast notification - just close the modal silently
        } catch (error) {
            console.error('Error saving settings:', error);
            alert('Failed to update settings. Please try again.');
        }
    }
}
