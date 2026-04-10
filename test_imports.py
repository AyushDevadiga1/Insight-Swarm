import os, sys, importlib.util
from pathlib import Path

tests_dir = Path("tests")
for root, _, files in os.walk(tests_dir):
    for f in files:
        if f.endswith(".py"):
            path = Path(root) / f
            print(f"Importing {path}...")
            spec = importlib.util.spec_from_file_location("test_module", path)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                print(f"OK: {path}")
            except Exception as e:
                print(f"ERROR on {path}: {e}")
