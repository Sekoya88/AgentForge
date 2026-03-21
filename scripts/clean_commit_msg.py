#!/usr/bin/env python3
import sys
import re

if len(sys.argv) < 2:
    sys.exit(0)

commit_msg_file = sys.argv[1]

try:
    with open(commit_msg_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    clean_lines = []
    for line in lines:
        if re.search(r'Made(\s|-)+with:\s*Cursor|Co-authored-by:\s*Claude', line, re.IGNORECASE):
            continue
        clean_lines.append(line)

    with open(commit_msg_file, 'w', encoding='utf-8') as f:
        f.writelines(clean_lines)

except Exception as e:
    print(f"Warning: Failed to clean commit message: {e}")
