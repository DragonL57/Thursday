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
            },
            // Add custom handling for paragraphs to preserve LaTeX delimiters
            paragraph(text) {
                return `<p>${text}</p>`;
            }
        },
        extensions: [{
            name: 'latex',
            level: 'inline',
            start(src) { 
                return Math.min(
                    src.indexOf('$') !== -1 ? src.indexOf('$') : Infinity,
                    src.indexOf('[') !== -1 ? src.indexOf('[') : Infinity
                );
            },
            tokenizer(src) {
                // Block LaTeX with $$ delimiters
                const blockMatch = /^\$\$([\s\S]+?)\$\$/.exec(src);
                if (blockMatch) {
                    return {
                        type: 'latex',
                        raw: blockMatch[0],
                        text: blockMatch[1].trim(),
                        displayMode: true
                    };
                }
                
                // Block LaTeX with square brackets
                const blockBracketMatch = /^\[([\s\S]+?)\]/.exec(src);
                if (blockBracketMatch) {
                    return {
                        type: 'latex',
                        raw: blockBracketMatch[0],
                        text: blockBracketMatch[1].trim(),
                        displayMode: true
                    };
                }
                
                // Inline LaTeX with $ delimiters
                const inlineMatch = /^\$([^\$]+?)\$/.exec(src);
                if (inlineMatch) {
                    return {
                        type: 'latex',
                        raw: inlineMatch[0],
                        text: inlineMatch[1].trim(),
                        displayMode: false
                    };
                }
                
                return false;
            },
            renderer(token) {
                try {
                    return katex.renderToString(token.text, {
                        displayMode: token.displayMode,
                        throwOnError: false
                    });
                } catch (e) {
                    console.error('LaTeX rendering error:', e);
                    return token.raw; // Return the original LaTeX code on error
                }
            }
        }]
    });
    
    // Ensure KaTeX auto-render is available
    if (typeof renderMathInElement === 'undefined') {
        window.addEventListener('load', initKaTeXAutoRender);
    } else {
        initKaTeXAutoRender();
    }
}

/**
 * Initialize KaTeX auto-rendering once it's available
 */
function initKaTeXAutoRender() {
    if (typeof renderMathInElement !== 'undefined') {
        renderMathInElement(document.body, {
            delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '$', right: '$', display: false},
                {left: '[', right: ']', display: true}  // Add square brackets as delimiters
            ],
            throwOnError: false
        });
    } else {
        console.warn('KaTeX auto-render not available yet');
        setTimeout(initKaTeXAutoRender, 500); // Try again after 500ms
    }
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
