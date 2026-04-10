import sys
with open('pytest_err.log', 'r', encoding='utf-16le', errors='ignore') as f:
    text = f.read()

parts = text.split("=================================== FAILURES ===================================")
if len(parts) > 1:
    print(parts[1])
else:
    print("NO FAILURES string found.")
