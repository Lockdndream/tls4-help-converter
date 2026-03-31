# TLS-4 Help Converter

Converts a **RoboHelp 2022** (Frameless/HTML5) output package into a **RoboHelp 2019** (WebHelp, frame-based) package so it renders correctly on the **Gilbarco TLS-450** embedded browser.

## Background

RoboHelp 2022 outputs use CSS custom properties (`var()`), Flexbox, and responsive breakpoints to lay out the navigation pane. The TLS-450's embedded browser has limited support for these features, causing the nav pane to consume ~80% of the display. The 2019 WebHelp format uses a hard HTML `frameset` (`cols="260,*"`) which works reliably on the device.

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/your-org/tls4-help-converter.git
cd tls4-help-converter

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Usage

1. Upload the **2022 output zip** (new content — from RoboHelp 2022 Frameless output)
2. Upload the **2019 output zip** (old package — provides the WebHelp navigation engine)
3. Click **Run Conversion**
4. Download `help_converted.zip`
5. Deploy the contents of `help/english/` to the TLS-450 as you would the original 2019 package

## How it works

The tool:
- Extracts the 2019 WebHelp framework (JS nav engine, `whdata/`, `whgdata/`, `index.htm` frameset)
- Converts every 2022 topic `.htm` file:
  - Removes the `<?xml?>` declaration
  - Fixes DOCTYPE to `<!DOCTYPE HTML>`
  - Removes `_rhdefault.css` (CSS-var-heavy, unsupported on device)
  - Rewrites CSS path to `tls4_gui.css`
  - Flattens `assets/images/` paths
  - Lowercases all internal `.htm` href values (case-sensitive filesystem compatibility)
- Copies all 2022 images into the correct locations
- Repackages everything as a single zip

## Project structure

```
tls4-help-converter/
├── app.py          # Streamlit UI
├── converter.py    # Conversion logic (no Streamlit dependency)
├── requirements.txt
└── README.md
```

`converter.py` has no Streamlit dependency — it can be used standalone:

```python
from converter import convert

convert(
    new_zip_path="help_2022.zip",
    old_zip_path="help_2019.zip",
    output_zip_path="help_converted.zip",
)
```

## Known limitations

- Topics added in 2022 that don't exist in the 2019 TOC won't appear in the nav tree. They are accessible via direct URL or breadcrumb links within topic content.
- The 2019 search index only covers 2019 topics. To fully update both the TOC and search, regenerate the `whxdata/` files using RoboHelp 2019 with the updated project.

## Reporting bugs

When the conversion produces unexpected output:
1. Note which **Step** in the log failed or produced wrong output
2. Copy the **error detail** from the app's error expander
3. Bring both to Claude along with the relevant source files from `converter.py`
4. Fix `converter.py`, save — Streamlit will show a **Rerun** banner automatically
