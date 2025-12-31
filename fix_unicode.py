#!/usr/bin/env python
"""Fix all Unicode characters in Python files for Windows cp1252 compatibility."""
import os
import re

# Files that need to be fixed
APP_DIR = "app"

# Unicode character replacements
REPLACEMENTS = {
    '✓': '[OK]',
    '✗': '[ERROR]',
    '⚠️': '[WARNING]',
    '⚠\ufe0f': '[WARNING]',  # variant form
    '🔴': '[!]',
    '🔵': '[*]',
    '⭐': '[STAR]',
    '❌': '[NO]',
    '✅': '[YES]',
    '→': '->',
    '═': '=',
    '🔴🔴🔴': '[!!!]',
    '⚠️⚠️⚠️': '[!!!]',
}

def fix_file(filepath):
    """Fix Unicode characters in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Apply all replacements
        for old, new in REPLACEMENTS.items():
            content = content.replace(old, new)

        # Only write if changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    fixed_count = 0

    for root, dirs, files in os.walk(APP_DIR):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if fix_file(filepath):
                    fixed_count += 1

    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == "__main__":
    main()
