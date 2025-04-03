export class SidebarManager {
    constructor(toggleButton, sidebar) {
        this.toggleButton = toggleButton;
        this.sidebar = sidebar;
        
        this.init();
    }
    
    init() {
        // Add event listener for sidebar toggle
        this.toggleButton.addEventListener('click', () => this.toggleSidebar());
    }
    
    toggleSidebar() {
        this.sidebar.classList.toggle('open');
    }
}
