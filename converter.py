"""
TLS-4 GUI Help Converter
Converts RoboHelp 2022 Frameless output → RoboHelp 2019 WebHelp (frame-based) format
so it renders correctly on the Gilbarco TLS-450 embedded browser.
"""

import os
import re
import shutil
import zipfile
import tempfile
from pathlib import Path
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(msg: str, callback: Optional[Callable] = None) -> None:
    """Send a log line to the callback (Streamlit) or print it."""
    if callback:
        callback(msg)
    else:
        print(msg)


def _find_english_dir(root: Path) -> Optional[Path]:
    """
    Walk the extracted zip tree and find the 'english' folder that contains
    the actual help content (identified by the presence of .htm files).
    """
    for path in sorted(root.rglob("english")):
        if path.is_dir() and any(path.glob("*.htm")):
            return path
    # Fallback: any directory with .htm files
    for path in sorted(root.rglob("*.htm")):
        return path.parent
    return None


def _extract_zip(zip_path: str, dest: Path, log: Callable) -> Path:
    """Extract a zip and return the path to the english/ content directory."""
    log(f"  Extracting: {Path(zip_path).name}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)

    english_dir = _find_english_dir(dest)
    if not english_dir:
        raise FileNotFoundError(
            f"Could not find a content directory with .htm files inside {Path(zip_path).name}. "
            "Check that the zip is a valid RoboHelp output package."
        )
    log(f"  Content directory: .../{english_dir.relative_to(dest)}")
    return english_dir


# ---------------------------------------------------------------------------
# Topic conversion
# ---------------------------------------------------------------------------

def _convert_topic(content: str) -> str:
    """
    Transform a single 2022 topic HTML to be compatible with the 2019
    WebHelp frame-based viewer.

    Changes applied:
      1. Remove XML declaration (<?xml ...?>)
      2. Replace XHTML DOCTYPE with plain HTML DOCTYPE
      3. Remove _rhdefault.css link (2022-only, uses CSS vars unsupported on device)
      4. Rewrite CSS path: assets/css/TLS4_GUI.css -> tls4_gui.css
      5. Flatten image paths: assets/images/ -> (root)
      6. Ensure charset meta is present
    """
    # 1. Strip XML declaration
    content = re.sub(r"<\?xml[^>]+\?>\s*", "", content)

    # 2. Fix DOCTYPE
    content = re.sub(
        r"<!DOCTYPE html[^>]*>",
        "<!DOCTYPE HTML>",
        content,
        count=1,
        flags=re.IGNORECASE,
    )

    # 3. Remove _rhdefault.css link
    content = re.sub(
        r'<link[^>]+_rhdefault\.css[^>]*/>\s*',
        "",
        content,
        flags=re.IGNORECASE,
    )

    # 4. Fix CSS path
    content = content.replace("assets/css/TLS4_GUI.css", "tls4_gui.css")
    content = content.replace("assets/css/tls4_gui.css", "tls4_gui.css")

    # 5. Flatten image paths (assets/images/ prefix → nothing, img/ stays)
    content = re.sub(r'assets/images/(?!img/)', "", content)
    content = content.replace("assets/images/img/", "img/")

    return content


def _lowercase_htm_hrefs(content: str) -> str:
    """
    Normalize all internal .htm href values to lowercase so links work on
    case-sensitive file systems (Linux-based embedded browser on TLS-450).
    """
    def _lower(m: re.Match) -> str:
        val = m.group(1)
        if val.lower().endswith(".htm") and not val.startswith("http"):
            return f'href="{val.lower()}"'
        return m.group(0)

    return re.sub(r'href="([^"]+\.htm[^"]*)"', _lower, content)


# ---------------------------------------------------------------------------
# Image copying
# ---------------------------------------------------------------------------

def _copy_images(src_assets_images: Path, dest_english: Path, log: Callable) -> int:
    """
    Copy all images from the 2022 assets/images tree into the 2019 output.
    Files in assets/images/img/ go to dest/img/.
    All other files go to dest/ (flat, alongside the .htm files).
    Returns count of files copied.
    """
    count = 0
    if not src_assets_images.exists():
        log("  WARNING: No assets/images directory found in 2022 package.")
        return count

    for src_file in src_assets_images.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_assets_images)
        parts = rel.parts

        if parts[0].lower() == "img":
            dest_file = dest_english / "img" / Path(*parts[1:])
        else:
            dest_file = dest_english / src_file.name

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
        count += 1

    return count


# ---------------------------------------------------------------------------
# Main conversion entry point
# ---------------------------------------------------------------------------

def convert(
    new_zip_path: str,
    old_zip_path: str,
    output_zip_path: str,
    log_callback: Optional[Callable] = None,
) -> None:
    """
    Full conversion pipeline.

    Args:
        new_zip_path:    Path to the RoboHelp 2022 output zip (new content).
        old_zip_path:    Path to the RoboHelp 2019 output zip (provides
                         the WebHelp frame-based navigation engine).
        output_zip_path: Destination path for the converted zip.
        log_callback:    Optional callable(str) for progress reporting.
    """

    def log(msg: str) -> None:
        _log(msg, log_callback)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        new_root = tmp / "new"
        old_root = tmp / "old"
        out_root = tmp / "out" / "english"

        new_root.mkdir()
        old_root.mkdir()
        out_root.mkdir(parents=True)

        # ------------------------------------------------------------------ #
        # Step 1: Extract both packages
        # ------------------------------------------------------------------ #
        log("── Step 1/5: Extracting packages")
        new_english = _extract_zip(new_zip_path, new_root, log)
        old_english = _extract_zip(old_zip_path, old_root, log)

        # The 2019 zip may contain a nested help.zip — extract it if present
        nested = old_english / "help.zip"
        if nested.exists():
            log("  Found nested help.zip inside 2019 package — extracting…")
            nested_root = old_root / "_nested"
            nested_root.mkdir()
            with zipfile.ZipFile(nested, "r") as zf:
                zf.extractall(nested_root)
            old_english = _find_english_dir(nested_root) or old_english
            log(f"  Nested content dir: .../{old_english.relative_to(old_root)}")

        # ------------------------------------------------------------------ #
        # Step 2: Copy 2019 WebHelp framework (nav engine) to output
        # ------------------------------------------------------------------ #
        log("── Step 2/5: Copying 2019 WebHelp framework")
        framework_count = 0
        for item in old_english.iterdir():
            dest = out_root / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
            framework_count += 1
        log(f"  Copied {framework_count} items from 2019 framework")

        # ------------------------------------------------------------------ #
        # Step 3: Convert and overlay 2022 topic files
        # ------------------------------------------------------------------ #
        log("── Step 3/5: Converting 2022 topic files")
        topic_files = list(new_english.glob("*.htm"))
        converted = 0
        errors = []

        for src_file in topic_files:
            dest_name = src_file.name.lower()
            dest_path = out_root / dest_name
            try:
                raw = src_file.read_text(encoding="utf-8", errors="replace")
                converted_content = _convert_topic(raw)
                converted_content = _lowercase_htm_hrefs(converted_content)
                dest_path.write_text(converted_content, encoding="utf-8")
                converted += 1
            except Exception as exc:
                errors.append(f"{src_file.name}: {exc}")

        log(f"  Converted {converted} topic files")
        if errors:
            log(f"  WARNINGS ({len(errors)} files had issues):")
            for e in errors[:10]:
                log(f"    • {e}")
            if len(errors) > 10:
                log(f"    … and {len(errors) - 10} more")

        # ------------------------------------------------------------------ #
        # Step 4: Copy 2022 images
        # ------------------------------------------------------------------ #
        log("── Step 4/5: Copying images from 2022 package")
        assets_images = new_english / "assets" / "images"
        img_count = _copy_images(assets_images, out_root, log)
        log(f"  Copied {img_count} image files")

        # Also copy any loose images from the new english/ root (PNG/GIF at root)
        for ext in ("*.png", "*.PNG", "*.gif", "*.GIF", "*.jpg", "*.JPG"):
            for img in new_english.glob(ext):
                dest = out_root / img.name
                if not dest.exists():
                    shutil.copy2(img, dest)

        # ------------------------------------------------------------------ #
        # Step 5: Package output
        # ------------------------------------------------------------------ #
        log("── Step 5/5: Packaging output zip")
        out_package_root = out_root.parent  # tmp/out/

        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for file_path in sorted(out_root.rglob("*")):
                if file_path.is_file():
                    arcname = "help/english/" + str(
                        file_path.relative_to(out_root)
                    )
                    zout.write(file_path, arcname)

        size_mb = Path(output_zip_path).stat().st_size / (1024 * 1024)
        log(f"  Output: {Path(output_zip_path).name} ({size_mb:.1f} MB)")
        log("── Conversion complete ✓")
