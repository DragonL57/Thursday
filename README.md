# Thursday - A Personal Assistant In Your Terminal

Thursday is a Python-based personal assistant that leverages the power of Pollinations AI models to help you with various tasks. It's designed to be versatile and extensible, offering a range of tools to interact with your system and the internet. (These were written by AI)

A short disclaimer this was originally made to be my personal assistant so it might not be as versatile as you might expect. It uses Pollinations AI as the backend for its language capabilities.

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
- **Simple Chat Interface:** Interact with the assistant through a straightforward command-line chat interface.
- **Memory:** Can save notes between conversation and remember them.
- **Saving Conversation:** Save and load previous conversations.
- **Commands:** Supports creating/executing (code), use `/commands` for more information.
- **Extension:** For now you are required to write some code to extend its capabilities like adding commands to `CommandExecutor` or making new tools, there should be enough examples in `gem/builtin_commands.py` for commands and the `tools` directory for tool implementations.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- uv (for dependency management) - [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)
- An internet connection (for Pollinations AI access)

### Installation

1.  Clone the repository:

```bash
git clone https://github.com/DragonL57/Thursday.git 
cd Thursday
```

2.  Install dependencies using uv:

This will create venv if it doesn't exist

```bash
uv sync
```


### Usage

Run the `assistant.py` script to start the chat interface:

```bash
uv run assistant.py
```

You can then interact with Thursday by typing commands in the chat. Type `exit`, `quit`, or `bye` to close the chat.

## Configuration

The main configuration file is `config.py`. Here you can customize:

- **`MODEL`**: Currently set to "openai-large" for use with Pollinations AI.
- **`NAME`**: Set the name of your assistant (defaults to "Thursday").
- **`SYSTEM_PROMPT`**: Modify the system prompt to adjust the assistant's personality and instructions.
- **API retry parameters**: Control how the application handles temporary failures and rate limits.

**Note:** Restart the `assistant.py` script after making changes to `config.py`.

## Model Selection

Thursday supports multiple AI model providers through a flexible naming scheme:

- **Default OpenAI-compatible:** `openai-large` (Uses Pollinations.AI's OpenAI-compatible endpoint)

To change the model, modify the `MODEL` variable in `config.py`. Note that tool calling capabilities may vary by model provider and specific model.

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
*   **Structured Memory:** Replace the simple `ai-log.txt` with a more structured format (e.g., JSON file, database) to store learned preferences, successful strategies, and environmental facts, enabling more effective context injection and retrieval.
*   **Feedback Mechanism:** Introduce a user command (e.g., `/feedback`) to allow explicit feedback on task outcomes, storing this information in the structured memory for potential future learning.

### 4. Refined Environmental Perception
*   **Context Integration:** Ensure consistent and explicit use of both static (OS, time, configured location) and dynamic (tool results, conversation history) context in reasoning and planning steps.


## Known Issues

- **Web Interaction:** Web interaction tools may not work as expected due to rate limits and other issues.
- **File download tool:** Might not show progress or filename(if not explicitly provided) correctly if file download endpoint is dynamic

# FAQ

### Why does it has so many seperate tools?

Because I think it does way better when there is one tool for one thing and it can just choose instead of one tool doing multiple things.
