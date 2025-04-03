export class ThemeManager {
    constructor(toggleButton) {
        this.toggleButton = toggleButton;
        this.darkModeEnabled = localStorage.getItem('darkMode') === 'true';
        this.init();
    }
    
    init() {
        // Set initial theme
        if (this.darkModeEnabled) {
            document.body.classList.add('dark-mode');
            this.toggleButton.querySelector('.material-icons-round').textContent = 'light_mode';
        }
        
        // Add event listener for theme toggle
        this.toggleButton.addEventListener('click', () => this.toggleTheme());
    }
    
    toggleTheme() {
        this.darkModeEnabled = !this.darkModeEnabled;
        document.body.classList.toggle('dark-mode', this.darkModeEnabled);
        localStorage.setItem('darkMode', this.darkModeEnabled);
        
        // Update icon
        const icon = this.toggleButton.querySelector('.material-icons-round');
        icon.textContent = this.darkModeEnabled ? 'light_mode' : 'dark_mode';
    }
}
