import os
import json
import argparse

def compile_project(config_filename: str):
    """
    Reads a JSON configuration file from projects/,
    optionally writes 'start_prompt' at the top,
    then for each listed file:
      1) Write 'start_text' (if provided),
      2) Write the file’s contents,
      3) Write 'stop_text' (if provided).
    Finally, save everything to one .txt file in output/.
    """

    # ------------------------
    # 1) Locate and load the JSON
    # ------------------------
    base_dir = os.path.dirname(__file__)  # Directory where main.py lives
    config_path = os.path.join(base_dir, "projects", config_filename)
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Could not find configuration file: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ------------------------
    # 2) Extract fields (all optional except absolute_path and files)
    # ------------------------
    title = data.get("title", "").strip()
    abs_path = data.get("absolute_path", "").strip()
    start_prompt = data.get("start_prompt", "").strip()   # Optional
    start_text_template = data.get("start_text", "").strip()  # Optional
    stop_text_template = data.get("stop_text", "").strip()    # Optional
    files_list = data.get("files", [])

    # Validate required fields
    if not abs_path:
        raise ValueError("The 'absolute_path' field must not be empty.")
    if not os.path.isdir(abs_path):
        raise FileNotFoundError(f"Absolute path does not exist: {abs_path}")
    if not isinstance(files_list, list) or len(files_list) == 0:
        raise ValueError("The 'files' array must contain at least one relative path.")

    # ------------------------
    # 3) Prepare output directory and filename
    # ------------------------
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(config_filename))[0]
    output_filename = f"{base_name}.txt"
    output_path = os.path.join(output_dir, output_filename)

    # ------------------------
    # 4) Open output file and begin writing
    # ------------------------
    with open(output_path, "w", encoding="utf-8") as out_file:
        # 4.a) Write start_prompt if provided
        if start_prompt:
            out_file.write(start_prompt + "\n\n")

        # 4.b) Write project title if provided
        if title:
            out_file.write(f"Project: {title}\n\n")

        # 4.c) Iterate through each file in 'files'
        for rel_path in files_list:
            full_path = os.path.join(abs_path, rel_path)

            # 4.c.i) Write start_text before the file (if provided)
            if start_text_template:
                if "{file}" in start_text_template:
                    intro = start_text_template.replace("{file}", rel_path)
                else:
                    # If no {file} placeholder, append the filename
                    intro = f"{start_text_template} \"{rel_path}\""
                out_file.write(intro + "\n")

            # 4.c.ii) Read and write the file’s contents (or an error if missing)
            try:
                with open(full_path, "r", encoding="utf-8") as code_file:
                    content = code_file.read()
            except FileNotFoundError:
                content = f"*** ERROR: Could not find file: {full_path} ***\n"
            out_file.write(content)

            # 4.c.iii) Write stop_text after the file (if provided)
            if stop_text_template:
                if "{file}" in stop_text_template:
                    footer = stop_text_template.replace("{file}", rel_path)
                else:
                    footer = stop_text_template
                out_file.write(footer)

            # 4.c.iv) Add two blank lines between files, for readability
            out_file.write("\n\n")

    print(f"Compilation complete! Output written to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect file contents based on a JSON configuration, " +
                    "with optional start_prompt, start_text, and stop_text."
    )
    parser.add_argument(
        "project_json",
        type=str,
        help="Name of the JSON file in projects/ (e.g., my-project.json)"
    )
    args = parser.parse_args()

    try:
        compile_project(args.project_json)
    except Exception as e:
        print(f"An error occurred: {e}")
