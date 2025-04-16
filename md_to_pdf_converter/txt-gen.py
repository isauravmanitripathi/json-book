import os

# Define the base directory as the directory where the script is located
base_dir = os.path.dirname(os.path.abspath(__file__))

# Files and directories to ignore
ignore_files = {"openai-rerwite.py"}
ignore_dirs = {
    "json_writer",
    "pdf_worker_2",
    ".venv",
    "gemini-book-generator"  # Ignoring the virtual environment folder
}

# Output file path
output_file = os.path.join(base_dir, "combined_python_code.txt")

# Function to scan and collect Python file contents
def collect_python_files(directory):
    collected_data = []
    for root, dirs, files in os.walk(directory):
        # Ignore specified directories
        if any(ignored in root for ignored in ignore_dirs):
            continue
        
        for file in files:
            if file.endswith(".py") and file not in ignore_files:
                file_path = os.path.join(root, file)
                
                # Read and collect the file content
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        code = f.read()
                        collected_data.append(f"### FILE: {file_path}\n{code}\n\n")
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    return collected_data

# Collect Python file contents
python_code = collect_python_files(base_dir)

# Save to a text file
with open(output_file, "w", encoding="utf-8") as f:
    f.writelines(python_code)

print(f"Python files content saved to {output_file}")