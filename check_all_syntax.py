import os
import py_compile
import sys

def verify_all_python_files(start_dir: str = "."):
    py_files = []
    for root, dirs, files in os.walk(start_dir):
        if ".git" in root or "__pycache__" in root or ".venv" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))

    print(f"Verifying compilation for {len(py_files)} Python source files...")
    errors = 0
    for file_path in py_files:
        try:
            py_compile.compile(file_path, doraise=True)
        except py_compile.PyCompileError as e:
            print(f"[SYNTAX ERROR] {file_path}: {e}")
            errors += 1
        except Exception as e:
            print(f"[ERROR] {file_path}: {e}")
            errors += 1

    if errors == 0:
        print(f"SUCCESS: All {len(py_files)} Python source files compiled with 0 syntax/type errors!")
    else:
        print(f"FAILURE: Found {errors} syntax errors.")
        sys.exit(1)

if __name__ == "__main__":
    verify_all_python_files(".")
