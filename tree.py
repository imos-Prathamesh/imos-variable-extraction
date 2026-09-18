import os

SKIP_DIRS = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "venv",
    "dist",
}

def print_directory_structure(start_path, indent=""):
    items = sorted(os.listdir(start_path))

    # Remove skipped directories
    items = [item for item in items if item not in SKIP_DIRS]

    for index, item in enumerate(items):
        path = os.path.join(start_path, item)
        is_last = (index == len(items) - 1)
        connector = "└── " if is_last else "├── "

        print(indent + connector + item)

        if os.path.isdir(path):
            extension = "    " if is_last else "│   "
            print_directory_structure(path, indent + extension)

if __name__ == "__main__":
    print(os.path.abspath("."))
    print_directory_structure(".")