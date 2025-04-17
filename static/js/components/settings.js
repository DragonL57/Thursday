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
        this.modelSelect = elements.modelSelect;
        this.saveChatHistory = elements.saveChatHistory;
        this.messagingComponent = messagingComponent;
        this.themeManager = themeManager;
        
        this.init();
        this.fetchCurrentSettings();
    }
    
    init() {
        // Open settings modal
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

    async fetchCurrentSettings() {
        try {
            const settings = await getSettings();
            
            // Ensure we get a valid object back
            if (!settings) {
                throw new Error('Invalid settings returned from API');
            }
            
            // Update model select
            if (settings.model && this.modelSelect) {
                // Make sure the option exists in the select element
                let optionExists = false;
                Array.from(this.modelSelect.options).forEach(option => {
                    if (option.value === settings.model) {
                        optionExists = true;
                    }
                });
                
                if (optionExists) {
                    this.modelSelect.value = settings.model;
                } else {
                    console.warn(`Model ${settings.model} not found in select options`);
                    // Set to default if the option doesn't exist
                    this.modelSelect.value = 'openai';
                }
            }
            
            // Update temperature
            if (settings.temperature !== undefined && this.temperatureSlider && this.temperatureValue) {
                const tempValue = parseFloat(settings.temperature);
                this.temperatureSlider.value = tempValue;
                this.temperatureValue.textContent = tempValue;
            }
            
            // Update max tokens
            if (settings.max_tokens !== undefined && this.maxTokensInput) {
                this.maxTokensInput.value = settings.max_tokens;
            }
            
            // Update save history checkbox
            if (settings.save_history !== undefined && this.saveChatHistory) {
                this.saveChatHistory.checked = settings.save_history;
            }
            
            return settings;
        } catch (error) {
            console.error('Error fetching settings:', error);
            return {
                provider: 'pollinations',
                model: 'openai',
                temperature: 1,
                max_tokens: 8192,
                save_history: true
            };
        }
    }
    
    async updateModelSilently(settings) {
        try {
            // Only update necessary fields
            const update = {
                provider: 'pollinations', // Always set to pollinations
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
            
            // Update the select element if it exists and the option is available
            if (settings.model && this.modelSelect) {
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
        // Ensure we have the model select element
        if (!this.modelSelect) {
            console.error('Model select element not found');
            alert('Settings could not be saved: model selection not available');
            return;
        }

        const settings = {
            provider: 'pollinations', // Always set to pollinations
            model: this.modelSelect.value,
            temperature: parseFloat(this.temperatureSlider.value),
            max_tokens: parseInt(this.maxTokensInput.value),
            save_history: this.saveChatHistory.checked
        };
        
        try {
            await updateSettings(settings);
            this.settingsModal.classList.remove('active');
            console.log('Settings saved successfully');
        } catch (error) {
            console.error('Error saving settings:', error);
            alert('Failed to update settings. Please try again.');
        }
    }
}
