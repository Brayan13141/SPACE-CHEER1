"""
Bulk-fix: replace inline style= attributes with CSS utility classes across all templates.
Creates static/css/sc-utils.css and patches all .html files.
"""
import os
import re
from pathlib import Path

BASE = Path(r"C:\Users\Lenovo\Documents\SPACE-CHEER\space_cheer")
TEMPLATES_DIR = BASE / "templates"
CSS_DIR = BASE / "static" / "CSS"
CSS_FILE = CSS_DIR / "sc-utils.css"

# Mapping: exact style value (stripped) → CSS class name
STYLE_MAP = {
    # Colors — SC design tokens
    "color:var(--sc-cyan);":                        "sc-color-cyan",
    "color: var(--sc-cyan);":                       "sc-color-cyan",
    "color:var(--sc-purple);":                      "sc-color-purple",
    "color: var(--sc-purple);":                     "sc-color-purple",
    "color:var(--secondary-color);":                "sc-color-secondary",
    "color: var(--secondary-color);":               "sc-color-secondary",
    "color:#7f5af0;":                               "sc-color-purple",
    "color: #7f5af0;":                              "sc-color-purple",
    "color:#a0a7d0;":                               "sc-color-muted",
    "color: #a0a7d0;":                              "sc-color-muted",
    "color:#b0b7e0;":                               "sc-color-muted-light",
    "color: #b0b7e0;":                              "sc-color-muted-light",
    "color:#e4eaff;":                               "sc-color-light",
    "color: #e4eaff;":                              "sc-color-light",
    "color: var(--light-color);":                   "sc-color-light",
    "color:var(--light-color);":                    "sc-color-light",
    "color: #e2e8f0;":                              "sc-color-text",
    "color:#e2e8f0;":                               "sc-color-text",
    "color:var(--sc-pink);":                        "sc-color-pink",
    # Backgrounds — SC design tokens
    "background:var(--sc-surface);":                "sc-bg-surface",
    "background: var(--sc-surface);":               "sc-bg-surface",
    "background:transparent;":                      "sc-bg-transparent",
    "background: transparent;":                     "sc-bg-transparent",
    "background:var(--sc-cyan);":                   "sc-bg-cyan",
    "background:var(--sc-success,#198754);":        "sc-bg-success",
    "background:var(--sc-warning,#ffc107);color:#000;": "sc-bg-warning-dark",
    "background:rgba(127,90,240,0.08);border:1px solid rgba(127,90,240,0.2);": "sc-card-purple",
    "border: 1px solid rgba(127,90,240,0.2) !important;": "sc-border-purple",
    "border-bottom:1px solid rgba(255,255,255,0.05);": "sc-border-bottom-subtle",
    "border-bottom:1px solid rgba(127,90,240,0.15);": "sc-border-bottom-purple",
    # Font sizes
    "font-size:0.75rem;":                           "sc-text-xs",
    "font-size: 0.75rem;":                          "sc-text-xs",
    "font-size:.75rem;":                            "sc-text-xs",
    "font-size: .75rem;":                           "sc-text-xs",
    "font-size:0.7rem;":                            "sc-text-xxs",
    "font-size:.7rem;":                             "sc-text-xxs",
    # Sizes
    "width:48px;height:48px;":                      "sc-icon-48",
    "width:38px;height:38px;":                      "sc-icon-38",
    "width:36px;height:36px;":                      "sc-icon-36",
    "width:60px;":                                  "sc-w-60",
    "min-width:60px;":                              "sc-min-w-60",
    "max-width:560px;":                             "sc-max-w-560",
    "max-width:600px;":                             "sc-max-w-600",
    # Layout
    "text-align: center;":                          "text-center",
    "display:none":                                 "d-none",
    "display:none;":                                "d-none",
    "display:block;":                               "d-block",
}

CSS_RULES = """\
/* sc-utils.css — Auto-generated utility classes replacing inline style= attributes.
   Included via <link rel="stylesheet"> so no nonce needed (style-src 'self' allows it). */

/* Colors */
.sc-color-cyan       { color: var(--sc-cyan); }
.sc-color-purple     { color: var(--sc-purple); }
.sc-color-secondary  { color: var(--secondary-color); }
.sc-color-muted      { color: #a0a7d0; }
.sc-color-muted-light{ color: #b0b7e0; }
.sc-color-light      { color: #e4eaff; }
.sc-color-text       { color: #e2e8f0; }
.sc-color-pink       { color: var(--sc-pink); }

/* Backgrounds */
.sc-bg-surface       { background: var(--sc-surface); }
.sc-bg-transparent   { background: transparent; }
.sc-bg-cyan          { background: var(--sc-cyan); }
.sc-bg-success       { background: var(--sc-success, #198754); }
.sc-bg-warning-dark  { background: var(--sc-warning, #ffc107); color: #000; }

/* Cards / Borders */
.sc-card-purple      { background: rgba(127,90,240,0.08); border: 1px solid rgba(127,90,240,0.2); }
.sc-border-purple    { border: 1px solid rgba(127,90,240,0.2) !important; }
.sc-border-bottom-subtle { border-bottom: 1px solid rgba(255,255,255,0.05); }
.sc-border-bottom-purple { border-bottom: 1px solid rgba(127,90,240,0.15); }

/* Font sizes */
.sc-text-xs          { font-size: 0.75rem; }
.sc-text-xxs         { font-size: 0.7rem; }

/* Sizes */
.sc-icon-48          { width: 48px; height: 48px; }
.sc-icon-38          { width: 38px; height: 38px; }
.sc-icon-36          { width: 36px; height: 36px; }
.sc-w-60             { width: 60px; }
.sc-min-w-60         { min-width: 60px; }
.sc-max-w-560        { max-width: 560px; }
.sc-max-w-600        { max-width: 600px; }

/* Shared account template utilities (used in login, profile_setup, curp_verification) */
.text-muted-light    { color: #a0a7d0; }
.link-secondary-color{ color: var(--secondary-color); }
.form-text-sm        { font-size: 0.8rem; }
"""


def normalize(s):
    """Collapse whitespace for comparison."""
    return re.sub(r'\s+', '', s).lower()


def build_normalized_map():
    """Build a map from normalized style value → class name."""
    return {normalize(k): v for k, v in STYLE_MAP.items()}


NORM_MAP = build_normalized_map()


def style_to_class(style_value):
    """Return a CSS class name if the style value is in our map, else None."""
    return NORM_MAP.get(normalize(style_value))


def patch_html(content):
    """
    Find all style="..." attributes and replace with class additions where possible.
    Returns (new_content, replaced_count).
    """
    count = 0

    def replace_style(m):
        nonlocal count
        full_match = m.group(0)
        style_value = m.group(1)
        cls = style_to_class(style_value)
        if cls is None:
            return full_match  # unknown pattern, leave as-is

        count += 1
        # Find the element tag context: look for existing class="..." BEFORE this style attr
        # We'll return just the replacement for the style= attr; class merging handled below
        return f'data-sc-class="{cls}"'  # temp marker

    # Step 1: replace known style="..." with temp markers
    result = re.sub(r'style="([^"]*)"', replace_style, content)

    # Step 2: merge temp markers into class attributes
    def merge_class(m):
        tag_inner = m.group(1)
        # Collect all data-sc-class markers in this tag
        markers = re.findall(r'data-sc-class="([^"]+)"', tag_inner)
        if not markers:
            return m.group(0)

        # Remove all data-sc-class markers
        tag_inner = re.sub(r'\s*data-sc-class="[^"]+"', '', tag_inner)

        # Merge into existing class or add new class
        extra_classes = ' '.join(markers)
        if 'class="' in tag_inner:
            tag_inner = re.sub(r'class="([^"]*)"', lambda cm: f'class="{cm.group(1)} {extra_classes}"', tag_inner, count=1)
        else:
            # Add class attribute after the tag name
            tag_inner = re.sub(r'^(\w[\w-]*)', r'\1 class="' + extra_classes + '"', tag_inner, count=1)

        return f'<{tag_inner}>'

    result = re.sub(r'<([^>]+)>', merge_class, result)
    return result, count


def main():
    # Write CSS utility file
    CSS_DIR.mkdir(parents=True, exist_ok=True)
    CSS_FILE.write_text(CSS_RULES, encoding='utf-8')
    print(f"Wrote {CSS_FILE}")

    total_replaced = 0
    total_files = 0
    files_changed = []

    for html_file in TEMPLATES_DIR.rglob('*.html'):
        original = html_file.read_text(encoding='utf-8')
        patched, n = patch_html(original)
        if n > 0:
            html_file.write_text(patched, encoding='utf-8')
            total_replaced += n
            total_files += 1
            files_changed.append((str(html_file.relative_to(TEMPLATES_DIR)), n))

    print(f"\nReplaced {total_replaced} inline styles across {total_files} files:")
    for f, n in sorted(files_changed, key=lambda x: -x[1]):
        print(f"  {n:3d}  {f}")

    remaining = 0
    for html_file in TEMPLATES_DIR.rglob('*.html'):
        content = html_file.read_text(encoding='utf-8')
        remaining += len(re.findall(r'style="[^"]*"', content))
    print(f"\nRemaining style= attributes (not in map): {remaining}")


if __name__ == '__main__':
    main()
