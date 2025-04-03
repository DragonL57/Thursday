import { updateSettings } from '../utils/api.js';

export class SettingsManager {
    constructor(elements, messagingComponent) {
        this.settingsButton = elements.settingsButton;
        this.settingsModal = elements.settingsModal;
        this.closeModalButtons = elements.closeModalButtons;
        this.saveSettingsButton = elements.saveSettingsButton;
        this.temperatureSlider = elements.temperatureSlider;
        this.temperatureValue = elements.temperatureValue;
        this.modelSelect = elements.modelSelect;
        this.saveChatHistory = elements.saveChatHistory;
        this.messagingComponent = messagingComponent;
        
        this.init();
    }
    
    init() {
        // Open settings modal
        this.settingsButton.addEventListener('click', () => {
            this.settingsModal.classList.add('active');
        });
        
        // Close settings modal
        this.closeModalButtons.forEach(button => {
            button.addEventListener('click', () => {
                this.settingsModal.classList.remove('active');
            });
        });
        
        // Update temperature value display
        this.temperatureSlider.addEventListener('input', () => {
            this.temperatureValue.textContent = this.temperatureSlider.value;
        });
        
        // Save settings
        this.saveSettingsButton.addEventListener('click', () => this.saveSettings());
    }
    
    async saveSettings() {
        const settings = {
            model: this.modelSelect.value,
            temperature: parseFloat(this.temperatureSlider.value),
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
