export class ThemeManager {
    constructor() {
        this.darkModeEnabled = localStorage.getItem('darkMode') === 'true';
        this.init();
    }
    
    init() {
        // Set initial theme
        if (this.darkModeEnabled) {
            document.body.classList.add('dark-mode');
            if (document.getElementById('darkTheme')) {
                document.getElementById('darkTheme').checked = true;
            }
        }
        
        // Add event listeners to radio buttons
        const lightTheme = document.getElementById('lightTheme');
        const darkTheme = document.getElementById('darkTheme');
        
        if (lightTheme && darkTheme) {
            lightTheme.addEventListener('change', () => {
                if (lightTheme.checked) this.setTheme(false);
            });
            
            darkTheme.addEventListener('change', () => {
                if (darkTheme.checked) this.setTheme(true);
            });
        }
    }
    
    setTheme(isDark) {
        this.darkModeEnabled = isDark;
        document.body.classList.toggle('dark-mode', isDark);
        localStorage.setItem('darkMode', isDark);
        
        // Update radio buttons if they exist
        const lightTheme = document.getElementById('lightTheme');
        const darkTheme = document.getElementById('darkTheme');
        
        if (lightTheme && darkTheme) {
            lightTheme.checked = !isDark;
            darkTheme.checked = isDark;
        }
    }
    
    // Method to apply theme based on settings when saving
    applyThemeFromSettings() {
        const darkTheme = document.getElementById('darkTheme');
        if (darkTheme) {
            this.setTheme(darkTheme.checked);
        }
    }
}
