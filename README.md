# Thursday - A Personal Assistant In Your Terminal (and Web)

Thursday is a Python-based personal assistant that leverages the power of Pollinations AI models to help you with various tasks. It's designed to be versatile and extensible, offering a range of tools to interact with your system and the internet.

A short disclaimer: this was originally made to be my personal assistant so it might not be as versatile as you needed. It uses Pollinations AI as the backend for its language capabilities.

## Features

- **Powered by LLM:** Utilizes Pollinations AI models for natural language understanding and generation.
- **Tool-based architecture:** Equipped with a variety of tools for tasks like:
  - Web searching (DuckDuckGo)
  - File system operations (listing directories, reading/writing files, etc.)
  - System information retrieval
  - Reddit interaction
  - Running shell commands
  - And more!
- **Customizable:** Easily configure the assistant's behavior and extend its capabilities with new tools.
- **Dual Interface:** 
  - Terminal Chat Interface: Interact with the assistant through a straightforward command-line chat interface.
  - Web UI: A browser-based interface with real-time tool execution display.
- **Memory:** Can save notes between conversations and remember them.
- **Saving Conversation:** Save and load previous conversations.
- **Commands:** Supports creating/executing (code), use `/commands` for more information.
- **Extension:** For now you are required to write some code to extend its capabilities like adding commands to `CommandExecutor` or making new tools, there should be enough examples in `gem/builtin_commands.py` for commands and the `tools` directory for tool implementations.
- **Real-time Tool Execution:** See tool calls and their results in real-time as they're executed.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- uv (for dependency management) - [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)
- An internet connection (for Pollinations AI access)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/DragonL57/Thursday.git 
cd Thursday
```

2. Install dependencies using uv:

This will create venv if it doesn't exist

```bash
uv sync
```

### Usage

#### Terminal Interface

Run the `assistant.py` script to start the chat interface:

```bash
uv run assistant.py
```

You can then interact with Thursday by typing commands in the chat. Type `exit`, `quit`, or `bye` to close the chat.

#### Web Interface

Run the `app.py` script to start the web server:

```bash
uv run app.py
```

Then open your browser and navigate to `http://localhost:5000` to interact with Thursday via the web interface.

## Tools

Thursday comes with a set of built-in tools that you can use in your conversations. These tools are organized in the `tools` directory by functionality:

- **Web Search:**
  - `duckduckgo_search_tool` (Enhanced with region, time filters, and safe search parameters)

- **Web Interaction:**
  - `get_website_text_content` (Enhanced with timeout and extraction modes: 'text', 'markdown', or 'article')

- **File System:**
  - `list_dir`, `read_file`, `write_files`, `create_directory`, `copy_file`, `move_file`, `rename_file`, `rename_directory`, `get_file_metadata`, `get_directory_size`, `get_multiple_directory_size`

- **System:**
  - `get_system_info`, `run_shell_command`, `get_current_time`, `get_current_directory`, `get_drives`, `get_environment_variable`

- **Python Tools:**
  - `inspect_python_script`, `get_python_function_source_code`

**And much more!**

## Configuration

You can configure Thursday's behavior by modifying the following settings in `.env`:

```
MODEL=openai-large
TEMPERATURE=0.8
TOP_P=0.95
MAX_TOKENS=8192
CLEAR_BEFORE_START=True
NAME=Thursday
```

## Model Selection

Thursday can use different models from Pollinations AI. 

Set your desired model in the `.env` file.

## LaTeX Support

Thursday supports rendering LaTeX mathematical expressions in conversations. You can use the following formats:

- Inline math: Use `$...$` for inline equations (e.g., $E=mc^2$)
- Block math: Use `$$...$$` for displayed equations (e.g., $$E=mc^2$$)
- Alternative block math: Use `[...]` for displayed equations when appropriate (e.g., [E=mc^2])

Note: 
1. For inline math with single `$` delimiters, avoid spaces immediately after the opening delimiter and immediately before the closing delimiter to ensure proper rendering.
2. Markdown links in the format `[text](url)` will be properly rendered as links and not as LaTeX equations.
3. Source citations with text inside square brackets followed by URLs will be rendered as text rather than equations.
4. If you need to include square brackets for non-LaTeX purposes, consider using markdown link syntax or adding some contextual text like "Source:" nearby.

## Web Interface Features

The Thursday web interface offers several advantages:

1. **Real-time Tool Execution:** Watch tools execute in real-time before the final assistant response.
2. **Syntax Highlighting:** Code blocks are automatically highlighted for better readability.
3. **LaTeX Support:** Mathematical expressions are rendered properly in the browser.
4. **Clean Message Display:** User and assistant messages are clearly distinguished.
5. **Responsive Design:** Works on desktop and mobile devices.
6. **Theme Toggle:** Switch between light and dark mode.

## Testing

To run tests, use:
```bash
uv run pytest tests/
```

## Dependencies

The project dependencies are managed by UV and listed in `pyproject.toml`. Key dependencies include:

- `requests`
- `duckduckgo-search`
- `rich`
- `python-dotenv`
- `beautifulsoup4`
- `lxml`
- `docstring-parser`
- `prompt-toolkit`
- `colorama`
- `pydantic`
- `flask` (for web interface)

## Contributing

All contributions are welcome! Please fork the repository and create a pull request.

## Future Enhancements (Agentic Capabilities Roadmap)

This roadmap outlines potential enhancements to evolve Thursday towards a more autonomous, agentic system capable of complex goal achievement, reasoning, and adaptation.

### 1. Goal Management and Planning
*   **Goal Decomposition:** Enable the assistant to break down high-level user goals (e.g., "Plan my trip") into actionable sub-tasks using LLM-driven planning.
*   **Explicit Planning:** Generate and maintain a visible plan (sequence of steps/tool calls) to achieve the goal, moving beyond simple reactive responses.
*   **Dynamic Replanning:** Allow the agent to reassess and modify its plan if steps fail or yield unexpected results, rather than just reporting the error.

### 2. Enhanced Reasoning and Decision-Making
*   **Proactive Information Gathering:** When faced with ambiguity, attempt to use tools (e.g., search, list files) to gather necessary information before asking the user for clarification.
*   **Self-Correction:** Implement logic to analyze tool failures and attempt automated corrective actions (e.g., retrying commands with different parameters, switching to alternative tools).

### 3. Improved Learning and Adaptation
*   **User Preference Tracking:** Learn and remember user preferences, constraints, and common patterns to improve future interactions.
*   **Local Knowledge Base:** Build and maintain a personal knowledge base for the user, accumulating information from previous interactions and tool calls.

### 4. Refined Environmental Perception
*   **Context-Awareness:** Enhance the assistant's ability to understand and adapt to the user's computing environment, current working context, and available resources.
*   **File Content Understanding:** Improve understanding of file contents and structures to enable more intelligent file operations and code manipulation.

## Known Issues

- **Web Interaction:** Web interaction tools may not work as expected due to rate limits and other issues.

## FAQ

### Why does it have so many separate tools?

Because I think it does way better when there is one tool for one thing and it can just choose instead of one tool doing multiple things.
