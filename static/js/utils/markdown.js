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
            // Improve paragraph handling to preserve line breaks
            paragraph(text) {
                // Check if the text contains our special linebreak markers
                if (text.includes('<!-- linebreak -->')) {
                    // Replace our markers with proper <br> tags
                    const processedText = text.replace(/<!-- linebreak -->/g, '<br>');
                    return `<p>${processedText}</p>`;
                }
                return `<p>${text}</p>`;
            },
            // Override link renderer to ensure proper rendering
            link(href, title, text) {
                const titleAttr = title ? ` title="${title}"` : '';
                return `<a href="${href}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
            }
        },
        extensions: [{
            name: 'latex',
            level: 'inline',
            start(src) { 
                const dollarIndex = src.indexOf('$');
                
                // More aggressive link detection - check for common source patterns
                // This will detect both standard links and citation-style patterns
                const isLikelyLink = /^\[.*?\](\(.*?\)|:)/.test(src) || 
                                    /^Source:/.test(src) || 
                                    /(https?:\/\/|www\.)/.test(src.split('\n')[0]);
                                    
                // Only consider square brackets if they're not likely part of a citation or link
                const bracketIndex = isLikelyLink ? -1 : src.indexOf('[');
                
                if (dollarIndex === -1 && bracketIndex === -1) return Infinity;
                
                return Math.min(
                    dollarIndex !== -1 ? dollarIndex : Infinity,
                    bracketIndex !== -1 ? bracketIndex : Infinity
                );
            },
            tokenizer(src) {
                // Enhanced link detection pattern - check for multiple formats
                // This detects standard markdown links, citations, and source references
                if (/^\[.*?\](\(.*?\)|:)/.test(src) || 
                    /^Source:/.test(src) || 
                    /(https?:\/\/|www\.)/.test(src.split('\n')[0])) {
                    return false; // Let standard Markdown handle these
                }
                
                // Detect and skip source-style formatting with letters on separate lines
                // Look for patterns like single letters on separate lines followed by a URL
                if (/^[A-Za-z]\n[A-Za-z]\n[A-Za-z]/.test(src)) {
                    // Check if there's a URL pattern within the next few lines
                    const nextFewLines = src.split('\n').slice(0, 10).join('\n');
                    if (/(https?:\/\/|www\.)/.test(nextFewLines)) {
                        return false; // This looks like a source citation, not LaTeX
                    }
                }
                
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
                
                // Block LaTeX with square brackets - with enhanced checks
                // Only treat as LaTeX if:
                // 1. Not followed by parentheses or colon (markdown link or citation)
                // 2. Not part of a URL reference
                // 3. Not surrounded by typical citation/source text
                const blockBracketMatch = /^\[([\s\S]+?)\](?![\(:])/.exec(src);
                if (blockBracketMatch) {
                    // Additional check - look for URL-like patterns around this match
                    const context = src.substring(0, blockBracketMatch.index + blockBracketMatch[0].length + 30);
                    if (!/(Source|http|www|\.com|\.org|\.net)/.test(context)) {
                        return {
                            type: 'latex',
                            raw: blockBracketMatch[0],
                            text: blockBracketMatch[1].trim(),
                            displayMode: true
                        };
                    }
                    return false;
                }
                
                // Inline LaTeX with $ delimiters (must not have spaces after opening and before closing)
                const inlineMatch = /^\$([^\$\s][^\$]*?[^\$\s])\$/.exec(src) || /^\$([^\$])\$/.exec(src);
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
                    // Use KaTeX to render LaTeX expressions
                    return katex.renderToString(token.text, {
                        displayMode: token.displayMode,
                        throwOnError: false,
                        strict: false // Allow for more forgiving LaTeX parsing
                    });
                } catch (e) {
                    console.error('LaTeX rendering error:', e);
                    // Return escaped text on error so it's clear what went wrong
                    return `<span class="latex-error" title="${e.message}">${token.raw}</span>`;
                }
            }
        }]
    });
    
    // Ensure KaTeX auto-render is available and correctly configured
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
        try {
            renderMathInElement(document.body, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false},
                    {left: '\\[', right: '\\]', display: true},
                    {left: '\\(', right: '\\)', display: false},
                    {left: '[', right: ']', display: true}
                ],
                throwOnError: false,
                strict: false,
                trust: true,
                output: 'html',  // Use HTML output for better alignment environment support
                macros: {
                    "\\phi": "\\varphi",
                    "\\quad": "\\;\\;",
                    "\\cases": "\\begin{cases}#1\\end{cases}",
                    "\\n": "\\\\",
                    "\\align": "\\begin{align}#1\\end{align}",
                    "\\align*": "\\begin{align*}#1\\end{align*}",
                },
                errorCallback: function(msg, err) {
                    console.warn('KaTeX error:', msg);
                }
            });
        } catch (e) {
            console.error('Error initializing KaTeX auto-render:', e);
        }
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
