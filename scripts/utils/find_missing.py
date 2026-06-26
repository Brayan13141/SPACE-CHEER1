#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(encoding='utf-8')

PO_FILE = r"C:\Users\Lenovo\Documents\SPACE-CHEER\space_cheer\locale\en\LC_MESSAGES\django.po"

with open(PO_FILE, encoding='utf-8') as f:
    lines = f.readlines()

missing = []
i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith('msgid ') and not line.startswith('msgid ""'):
        val = line.rstrip()[7:-1]
        j = i + 1
        while j < len(lines) and lines[j].startswith('"'):
            val += lines[j].rstrip()[1:-1]
            j += 1
        k = j
        while k < len(lines) and (lines[k].startswith('#') or lines[k].strip() == ''):
            k += 1
        if k < len(lines) and lines[k].startswith('msgstr "'):
            mv = lines[k].rstrip()[8:-1]
            if mv == '':
                missing.append(val)
    i += 1

print(f"Remaining untranslated: {len(missing)}")
for m in missing:
    print(repr(m))
