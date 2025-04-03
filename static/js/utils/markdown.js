/**
 * Configure markdown renderer with code highlighting
 */
export function setupMarkdown() {
    marked.use({
        renderer: {
            code(code, language) {
                const validLanguage = hljs.getLanguage(language) ? language : 'plaintext';
                const highlightedCode = hljs.highlight(code, { language: validLanguage }).value;
                
                return `
                    <div class="code-block">
                        <div class="code-header">
                            <span class="language-indicator">${validLanguage}</span>
                            <span class="copy-code" onclick="copyCode(this)">
                                <span class="material-icons-round" style="font-size: 16px">content_copy</span>
                                Copy
                            </span>
                        </div>
                        <pre><code class="hljs ${validLanguage}">${highlightedCode}</code></pre>
                    </div>
                `;
            }
        }
    });
}

/**
 * Copy code to clipboard
 * @param {HTMLElement} button - The copy button element
 */
export function copyCode(button) {
    const codeBlock = button.closest('.code-block').querySelector('code');
    const textToCopy = codeBlock.textContent;
    
    navigator.clipboard.writeText(textToCopy).then(() => {
        const originalText = button.innerHTML;
        button.innerHTML = '<span class="material-icons-round" style="font-size: 16px">check</span> Copied!';
        setTimeout(() => {
            button.innerHTML = originalText;
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy text:', err);
    });
}

// Make copyCode available globally
window.copyCode = copyCode;
