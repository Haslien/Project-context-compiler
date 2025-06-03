# Project Context Compiler

## Overview
**Project Context Compiler** is a simple Python utility that consolidates multiple source files from a project into a single text file. Its primary purpose is to help you provide the full context of a project when interacting with large language models (LLMs) or sharing an overview of your codebase.

Instead of copying and pasting many individual files, you can run this script to automatically gather all specified files (using a JSON configuration) into one combined output. This saves time and ensures that each file is properly labeled before and after its contents.

## Key Features
- **JSON Configuration**: Specify project details (title, absolute path, optional prompts, and list of files).
- **Optional Prompts and Markers**:
  - **start_prompt**: A message written at the very beginning of the output to instruct the reader or LLM.
  - **start_text**: A header template that appears before each file’s content.
  - **stop_text**: A footer template that appears after each file’s content.
- **Single Output File**: All file contents are concatenated into one `.txt` file under the `output/` directory.
- **Error Handling**: If a specified file is not found, an error message for that missing file will be inserted instead of the actual content.

## Getting Started

### Prerequisites
- Python 3.6 or later
- No external dependencies (uses only Python’s standard library)

### Directory Structure
Your repository should follow this layout (with `main.py` at the root level):

```
<project-root>/
├── main.py
├── projects/
│   └── my-project.json
├── output/
└── README.md  <-- (this file)
```

- **`projects/`**: Place one or more JSON configuration files here. Each JSON describes a project to compile.
- **`output/`**: After running the script, a `.txt` file for each JSON configuration will be created here.
- **`main.py`**: The Python script that reads JSON configurations and generates the combined output.
- **`README.md`**: This documentation file.

### Example Configuration File
Create a JSON file (for example `projects/my-project.json`) with the following structure:

```json
{
  "title": "My Amazing Project",
  "absolute_path": "/path/to/your/project",
  "start_prompt": "Please get acquainted with this project’s structure and source files. I will send you multiple files in sequence—review and understand their contents. Once you have absorbed the overall context, wait for my instructions before performing any specific tasks.

",
  "start_text": "-- Begin file "{file}" --
",
  "stop_text": "-- End file "{file}" --
",
  "files": [
    "src/app.tsx",
    "src/main.tsx",
    "src/components/Header.tsx",
    "src/pages/LoginPage.tsx",
    "README.md"
  ]
}
```

- **`title`**: A descriptive name for your project (used as a header in the output).
- **`absolute_path`**: The root directory where the listed files reside.
- **`start_prompt`** (optional): A message to appear at the very top of the output file.
- **`start_text`** (optional): A template header before each file’s content. Use `{file}` to include the relative file path.
- **`stop_text`** (optional): A template footer after each file’s content. Use `{file}` if desired.
- **`files`**: An array of relative paths (relative to `absolute_path`) for each file you want to include.

### How to Use

1. **Place Your JSON Configuration**  
   Add your JSON file to the `projects/` directory (e.g., `projects/my-project.json`).

2. **Verify File Paths**  
   Ensure that `absolute_path` is correct and that every file listed in `files` actually exists.

3. **Run the Script**  
   In your terminal, navigate to the project root (where `main.py` is located) and execute:
   ```
   python main.py my-project.json
   ```
   Replace `my-project.json` with the name of your configuration file. The script will:
   - Read the JSON configuration.
   - Write the optional `start_prompt` at the top of the combined output.
   - For each file in `files`, write `start_text`, then the file’s content (or an error if missing), then `stop_text`.
   - Save the result as `output/my-project.txt` (derived from the JSON filename).

4. **Check the Output**  
   After the script runs, open `output/my-project.txt` to see the concatenated contents:
   ```
   (start_prompt)

   Project: My Amazing Project

   -- Begin file "src/app.tsx" --
   <contents of src/app.tsx>
   -- End file "src/app.tsx" --

   -- Begin file "src/main.tsx" --
   <contents of src/main.tsx>
   -- End file "src/main.tsx" --

   …etc…
   ```

5. **Share with LLMs**  
   Copy and paste the contents of the generated `output/my-project.txt` into a new conversation with an LLM. The model will see:
   - Your **start_prompt** instructions
   - A clearly labeled sequence of every file’s contents

   This way, the LLM can “get familiar” with the entire project context before you ask specific questions or request modifications.

## Customization and Tips
- **Omitting Optional Fields**  
  - If you do not want a `start_prompt`, simply omit that property from your JSON.  
  - If you do not want per-file headers (`start_text`) or footers (`stop_text`), omit those properties.  
  - The script will gracefully skip any missing fields.

- **Line Breaks**  
  - Use `
` inside JSON strings to insert newlines in `start_prompt`, `start_text`, or `stop_text`.

- **Handling Missing Files**  
  - If a file listed in the `files` array does not exist, the script writes a placeholder error message in the output. This makes it obvious which files need attention.

- **Multiple Projects**  
  - You can create multiple JSON files in `projects/` (for example, `projA.json`, `projB.json`).  
  - Run the script separately for each one:  
    ```
    python main.py projA.json
    python main.py projB.json
    ```

## License
This utility is provided “as is” under the MIT License. You are free to copy, modify, and distribute it for any purpose.

---

Happy coding!  
Copy the contents of `output/<your-config-name>.txt` directly into an LLM prompt to get instant, project-wide context.
