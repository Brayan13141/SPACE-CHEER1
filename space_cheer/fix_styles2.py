"""
fix_styles2.py — Second bulk-fix for remaining inline style= attributes.
Maps exact style values to CSS class names and replaces across all templates.
Skips dynamic styles (those containing {{ or {%).
Run from space_cheer/ directory.
"""

import os, re, sys
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"

# ---------------------------------------------------------------------------
# Mapping: exact style value → replacement CSS class(es)
# Key  = the exact string inside style="..."
# Value = class string to add, or '' to just remove the style attr entirely
# ---------------------------------------------------------------------------
STYLE_MAP = {
    # ── Colors ──────────────────────────────────────────────────────────────
    "color:#ffc107;": "text-warning",
    "color:#dc3545;": "text-danger",
    "color: #ff6b6b;": "text-danger",
    "color:#4ade80;": "sc-color-green-light",
    "color:#25d366;": "sc-color-whatsapp",
    "color:#ff4f9a;": "sc-color-pink",
    "color:#2cb1ff;": "sc-color-cyan",
    "color:var(--sc-purple,#7f5af0);": "sc-color-purple",
    "color: #a0a7d0; font-size: 0.9rem;": "sc-color-muted",
    "color: #a0a7d0; margin-bottom: 0.5rem;": "sc-color-muted mb-2",
    "color:#a0a7d0; font-size:0.9rem;": "sc-color-muted",
    "color:#a0a7d0; font-size:0.85rem;": "sc-color-muted",
    "color:#2cb1ff; text-decoration:none;": "sc-color-cyan text-decoration-none",
    "color:#2cb1ff; text-decoration:none; font-size:0.9rem;": "sc-color-cyan text-decoration-none",
    "color:inherit;": "",           # remove — it's the default
    "display:inline;": "d-inline",
    "list-style:none;": "list-unstyled",
    "opacity: 0.85;": "opacity-75",
    "padding-top:1.5rem;": "pt-3",
    "width:auto;": "w-auto",
    "object-fit:cover;": "object-fit-cover",

    # ── Backgrounds — white tints ────────────────────────────────────────────
    "background:rgba(255,255,255,.04);": "sc-bg-white-04",
    "background:rgba(255,255,255,0.04);": "sc-bg-white-04",
    "background:rgba(255,255,255,.05);": "sc-bg-white-05",
    "background:rgba(255,255,255,0.05);": "sc-bg-white-05",
    "background:rgba(255,255,255,0.03);": "sc-bg-white-04",  # close enough

    # ── Backgrounds — color tints ────────────────────────────────────────────
    "background:rgba(13,202,240,.12);": "sc-bg-cyan-tint",
    "background:rgba(13,202,240,0.1);": "sc-bg-cyan-tint",
    "background:rgba(220,53,69,0.15);": "sc-bg-danger-faint",
    "background:rgba(220,53,69,0.08);border:1px solid rgba(220,53,69,0.2);": "sc-bg-danger-card",
    "background:rgba(25,135,84,0.15);": "sc-bg-success-faint",
    "background:rgba(255,193,7,.2);color:#ffc107;": "sc-bg-warning-badge",
    "background:rgba(255,193,7,.07);border:1px solid rgba(255,193,7,.2);": "sc-bg-warning-card",
    "background: rgba(13, 110, 253, 0.1); border-color: rgba(13, 110, 253, 0.3);": "sc-badge-primary-outline",
    "background: rgba(255, 193, 7, 0.1); border-color: rgba(255, 193, 7, 0.3);": "sc-badge-warning-outline",
    "background: rgba(220, 53, 69, 0.1); border: 1px solid rgba(220, 53, 69, 0.35); color: #f5a0a8; border-radius: 8px;": "sc-alert-danger-custom",
    "background: rgba(255, 193, 7, 0.1); border: 1px solid rgba(255, 193, 7, 0.3); color: #ffd060; border-radius: 8px;": "sc-alert-warning-custom",
    "background:rgba(44,177,255,0.07); border:1px solid rgba(44,177,255,0.2);": "sc-bg-cyan-card",
    "background:rgba(255,79,154,0.07); border:1px solid rgba(255,79,154,0.2);": "sc-bg-pink-card",
    "background:rgba(108,117,125,.4);font-size:.65rem;": "sc-badge-secondary-dark",
    "background:rgba(255,255,255,.1);color:var(--sc-cyan);": "sc-bg-cyan-ghost",
    "background: rgba(0,0,0,0.35);": "sc-bg-overlay",
    "background:rgba(255,255,255,0.05);border:1px solid rgba(220,53,69,0.3);color:white;letter-spacing:0.1em;": "sc-danger-code",
    "background:rgba(26,26,46,0.95);border:1px solid rgba(220,53,69,0.3) !important;": "sc-danger-modal-bg",
    "background-color: rgba(127,90,240,.2); color: var(--sc-purple); border: 1px solid var(--sc-purple);": "sc-badge-purple-outline",
    "background-color: rgba(44,177,255,.2); color: var(--sc-cyan); border: 1px solid var(--sc-cyan);": "sc-badge-cyan-outline",
    "background-color: var(--sc-cyan); color: #000;": "sc-bg-cyan",
    "background-color: var(--sc-purple); color: #fff;": "sc-bg-purple-solid",
    "background: var(--sc-dark, #0d0d1a)": "sc-bg-darkest",
    "background: var(--sc-panel, #1a1a2e)": "sc-bg-panel",
    "background:var(--sc-bg);": "sc-bg-surface",
    "background:var(--sc-bg);color:var(--sc-text-muted);": "sc-bg-surface text-secondary",
    "background:var(--sc-bg);max-height:180px;overflow-y:auto;": "sc-scrollable-180",
    "background:var(--sc-cyan);color:#000;": "sc-bg-cyan",
    "background:var(--sc-panel,#1a1a2e);": "sc-bg-panel",
    "background:var(--sc-purple);": "sc-bg-purple-solid",
    "background: #1a1a2e;": "sc-bg-panel",
    "background:transparent;border-color:var(--sc-border,rgba(255,255,255,.1));": "bg-transparent sc-border-color",
    "background: transparent; border-top: 1px solid rgba(255,255,255,.08);": "bg-transparent sc-border-top-faint",
    "background:var(--sc-surface);border:1px solid rgba(255,255,255,.1);cursor:pointer;": "sc-bg-surface sc-border-subtle cursor-pointer",
    "background:rgba(255,255,255,.05); {% if address.is_default %}border-left: 3px solid var(--sc-cyan) !important;{% endif %}": None,  # dynamic, skip

    # ── Borders ──────────────────────────────────────────────────────────────
    "border-color:rgba(255,255,255,.1)!important;": "sc-border-subtle",
    "border-color:rgba(255,255,255,.06);": "sc-border-faint",
    "border-color:var(--sc-border,rgba(255,255,255,.1));": "sc-border-color",
    "border-color:var(--sc-border,rgba(255,255,255,.1));margin:2rem 0;": "sc-border-color my-4",
    "border-bottom: 1px solid rgba(255,255,255,.1);": "sc-border-bottom-light",
    "border-color: rgba(255,255,255,0.05) !important;": "sc-border-white-05",

    # ── Font sizes ────────────────────────────────────────────────────────────
    "font-size:.6rem;": "sc-text-6xs",
    "font-size:0.6rem;": "sc-text-6xs",
    "font-size: 0.6rem;": "sc-text-6xs",
    "font-size: 0.85rem;": "sc-text-85",
    "font-size:.8rem;": "form-text-sm",
    "font-size:0.65rem;": "sc-text-xxs",
    "font-size:.65rem;": "sc-text-xxs",
    "font-size:1.6rem;": "sc-fs-16",
    "font-size: 2rem; color: #a0a7d0;": "sc-fs-2rem sc-color-muted",
    "font-size: 2rem; color: var(--secondary-color);": "sc-fs-2rem sc-color-secondary",
    "font-size: 3.5rem; color: var(--primary-color);": "sc-fs-icon-lg",
    "font-size: 4rem; color: var(--secondary-color);": "sc-fs-icon-xl sc-color-secondary",
    "font-size: 4rem; line-height: 1;": "sc-fs-icon-xl lh-1",
    "font-size:2rem;color:#dc3545;": "sc-fs-2rem text-danger",

    # ── Workflow step bubbles (event_detail.html) ─────────────────────────────
    "width:34px;height:34px;background:var(--sc-purple);color:#fff;font-size:.8rem;": "sc-step-bubble sc-step-current",
    "width:34px;height:34px;background:rgba(25,135,84,.25);color:#198754;": "sc-step-bubble sc-step-done",
    "width:34px;height:34px;background:rgba(108,117,125,.15);font-size:.8rem;": "sc-step-bubble sc-step-muted",
    "width:34px;height:34px;border:1px solid rgba(108,117,125,.35);font-size:.8rem;": "sc-step-bubble sc-step-future",
    "width:34px;height:34px;background:rgba(220,53,69,.2);color:#dc3545;": "sc-step-bubble sc-step-cancelled",
    "font-size:.65rem;color:var(--sc-purple);max-width:60px;": "sc-step-label sc-step-label-purple",
    "font-size:.65rem;max-width:60px;": "sc-step-label",
    "height:1px;background:rgba(108,117,125,.3);min-width:8px;margin-bottom:18px;": "sc-step-connector",
    "height:1px;width:12px;background:rgba(220,53,69,.4);margin-bottom:18px;": "sc-step-connector-danger",

    # ── Images ────────────────────────────────────────────────────────────────
    "height:160px;object-fit:cover;": "sc-img-160",
    "height: 160px; object-fit: cover;": "sc-img-160",
    "height: 160px; object-fit: cover; cursor: pointer;": "sc-img-160-click",
    "height:160px;background:var(--sc-bg);": "sc-img-160-bg",
    "height:160px;background:var(--sc-panel,#1a1a2e);": "sc-img-160-panel",
    "height:160px;": "sc-img-160-bare",
    "height: 200px; background: var(--sc-panel, #1a1a2e);": "sc-img-200-panel",
    "height: 200px; object-fit: cover;": "sc-img-200",
    "max-height:200px; object-fit:cover; width:100%;": "sc-img-200-full",
    "height:80px;border-radius:6px;": "sc-img-80",
    "max-height: 500px;": "sc-max-h-500",
    "max-height:100px;": "sc-max-h-100",
    "max-height:160px;": "sc-max-h-160",
    "max-height:200px;": "sc-max-h-200",

    # ── Avatars — size only ───────────────────────────────────────────────────
    "width: 30px; height: 30px;": "sc-avatar-30",
    "width: 32px; height: 32px; font-size: 0.9rem;": "sc-avatar-32",
    "width: 40px; height: 40px;": "sc-avatar-40",
    "width: 42px; height: 42px;": "sc-avatar-42",
    "width: 44px; height: 44px;": "sc-avatar-44",
    "width: 50px; height: 50px;": "sc-avatar-50",
    "width: 55px; height: 55px;": "sc-avatar-55",
    "width: 56px; height: 56px;": "sc-avatar-56",
    "width: 100px; height: 100px;": "sc-avatar-100",
    "width:40px;height:40px;": "sc-avatar-40",
    "width:40px;height:40px;background:rgba(108,117,125,.2);": "sc-avatar-40 sc-avatar-bg-gray-lt",
    "width:40px;height:40px;object-fit:cover;": "sc-avatar-40 object-fit-cover",
    "width:44px;height:44px;": "sc-avatar-44",
    "width:48px;height:48px;background:rgba(127,90,240,0.15);": "sc-avatar-48 sc-avatar-bg-purple-lt",
    "width:50px;height:50px;": "sc-avatar-50",
    "width:36px;height:36px;background:var(--sc-panel,#1a1a2e);": "sc-avatar-36-panel",
    "width: 5rem; height: 5rem; background-color: rgba(108, 117, 125, 0.1);": "sc-icon-5rem sc-icon-bg-gray",
    "width: 5rem; height: 5rem; background-color: rgba(13, 110, 253, 0.1);": "sc-icon-5rem sc-icon-bg-blue",
    "width:80px;height:80px;background:rgba(220,53,69,0.1);border:2px solid rgba(220,53,69,0.3);": "sc-avatar-80-danger",
    "width:120px;height:120px;object-fit:cover": "sc-avatar-120",

    # ── Width/min/max constraints ─────────────────────────────────────────────
    "width:48px;": "sc-w-48",
    "width:55px;": "sc-w-55",
    "width:80px;": "sc-w-80",
    "width:100px;": "sc-w-100",
    "min-width:95px;": "sc-min-w-95",
    "min-width:140px;": "sc-min-w-140",
    "min-width:44px;justify-content:center;": "sc-min-w-44 justify-content-center",
    "max-width: 180px;": "sc-max-w-180",
    "max-width: 480px;": "sc-max-w-480",
    "max-width: 640px;": "sc-max-w-640",
    "max-width:480px;": "sc-max-w-480",
    "max-width:520px;": "sc-max-w-520",
    "max-width:540px;": "sc-max-w-540",
    "max-width:640px;": "sc-max-w-640",
    "max-width:680px;": "sc-max-w-680",
    "max-width:760px;": "sc-max-w-760",
    "max-width: 480px;": "sc-max-w-480",
    "max-width: 520px;": "sc-max-w-520",

    # ── Misc ──────────────────────────────────────────────────────────────────
    "transition: background .15s;": "sc-hover-bg",
    "height: 10px;": "sc-h-10",
}

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------
STYLE_ATTR_RE = re.compile(r'\bstyle="([^"]*)"')
CLASS_ATTR_RE = re.compile(r'\bclass="([^"]*)"')


def is_dynamic(value: str) -> bool:
    """Return True if the style value contains Django template tags."""
    return "{{" in value or "{%" in value


def classes_from_style(value: str):
    """Return replacement class string, or None if unknown/dynamic."""
    if is_dynamic(value):
        return None
    stripped = value.strip()
    if stripped in STYLE_MAP:
        return STYLE_MAP[stripped]
    return None


def replace_file(path: Path) -> tuple[int, int]:
    """Process a single template file. Returns (replacements, skipped)."""
    text = path.read_text(encoding="utf-8")
    replacements = 0
    skipped = 0

    def replacer(m):
        nonlocal replacements, skipped
        style_value = m.group(1)
        new_classes = classes_from_style(style_value)

        if new_classes is None:
            skipped += 1
            return m.group(0)   # leave unchanged

        replacements += 1
        return f'data-replaced-style="{new_classes}"'  # placeholder, handled below

    # First pass: replace style= with placeholder
    new_text = STYLE_ATTR_RE.sub(replacer, text)

    if replacements == 0:
        return 0, skipped

    # Second pass: merge placeholder classes into existing class="" or add new one
    def merge_class(m):
        classes_to_add = m.group(1)
        if not classes_to_add:
            return ""    # remove style attr entirely
        return f'data-add-class="{classes_to_add}"'

    new_text = re.sub(r'data-replaced-style="([^"]*)"', merge_class, new_text)

    # Third pass: if there's a class attr on the same tag, merge; else add
    lines = new_text.splitlines(keepends=True)
    final_lines = []
    for line in lines:
        while 'data-add-class="' in line:
            m = re.search(r'data-add-class="([^"]*)"', line)
            if not m:
                break
            to_add = m.group(1)
            placeholder = m.group(0)

            # Try to find class attr on the same line
            cm = CLASS_ATTR_RE.search(line, 0, m.start())
            if cm:
                # Append to existing class attr
                new_class_str = cm.group(1).strip() + " " + to_add
                line = (
                    line[: cm.start()]
                    + f'class="{new_class_str}"'
                    + line[cm.end(): m.start()]
                    + line[m.end():]
                )
            else:
                # Replace placeholder with class attr
                line = line.replace(placeholder, f'class="{to_add}"', 1)

        final_lines.append(line)

    path.write_text("".join(final_lines), encoding="utf-8")
    return replacements, skipped


def main():
    total_replaced = 0
    total_skipped = 0
    files_touched = 0

    exclude_dirs = {"email"}

    for html_file in sorted(TEMPLATES_DIR.rglob("*.html")):
        if any(part in exclude_dirs for part in html_file.parts):
            continue
        replaced, skipped = replace_file(html_file)
        if replaced > 0:
            rel = html_file.relative_to(TEMPLATES_DIR)
            print(f"  {replaced:3d} replaced, {skipped:2d} skipped  → {rel}")
            total_replaced += replaced
            files_touched += 1
        total_skipped += skipped

    print(f"\nDone: {total_replaced} replaced, {total_skipped} skipped across {files_touched} files.")


if __name__ == "__main__":
    main()
