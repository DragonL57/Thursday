import { updateSettings, getSettings } from '../utils/api.js';

export class SettingsManager {
    constructor(elements, messagingComponent) {
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
        
        // Save settings
        if (this.saveSettingsButton) {
            this.saveSettingsButton.addEventListener('click', () => this.saveSettings());
        }
    }
    
    async fetchCurrentSettings() {
        try {
            const settings = await getSettings();
            
            // Update UI with current settings
            if (settings.model) {
                this.modelSelect.value = settings.model;
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
    
    async saveSettings() {
        const settings = {
            model: this.modelSelect.value,
            temperature: parseFloat(this.temperatureSlider.value),
            max_tokens: parseInt(this.maxTokensInput.value),
            save_history: this.saveChatHistory.checked
        };
        
        try {
            await updateSettings(settings);
            this.settingsModal.classList.remove('active');
            this.messagingComponent.addMessage('Settings updated successfully!');
        } catch (error) {
            console.error('Error saving settings:', error);
            this.messagingComponent.addMessage(`Failed to update settings: ${error.message}`);
        }
    }
}
