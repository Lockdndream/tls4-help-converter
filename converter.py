"""
TLS-4 GUI Help Converter
Converts RoboHelp 2022 Frameless output → RoboHelp 2019 WebHelp (frame-based) format
so it renders correctly on the Gilbarco TLS-450 embedded browser.
"""

import re
import shutil
import zipfile
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(msg: str, callback=None) -> None:
    if callback:
        callback(msg)
    else:
        print(msg)


def _find_english_dir(root: Path):
    for path in sorted(root.rglob("english")):
        if path.is_dir() and any(path.glob("*.htm")):
            return path
    for path in sorted(root.rglob("*.htm")):
        return path.parent
    return None


def _extract_zip(zip_path: str, dest: Path, log) -> Path:
    log(f"  Extracting: {Path(zip_path).name}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)
    english_dir = _find_english_dir(dest)
    if not english_dir:
        raise FileNotFoundError(
            f"Could not find a content directory with .htm files inside {Path(zip_path).name}."
        )
    log(f"  Content directory: .../{english_dir.relative_to(dest)}")
    return english_dir


# ---------------------------------------------------------------------------
# 2019 legacy format constants
# ---------------------------------------------------------------------------

# FIX 1: two spaces before font-style (matches 2019 reference exactly)
_BC_STYLE = (
    "font-family: Arial; font-size: 10pt; font-weight: 400;  "
    "font-style:normal; color: rgb(0, 0, 255); text-decoration:none; text-align: left"
)

# Deprecated Netscape 4 resize workaround — formatting matches 2019 reference exactly
_NETSCAPE_RESIZE_SCRIPT = (
    '<script type="text/javascript" language="JavaScript">\n'
    '//<![CDATA[\n'
    'function reDo() {\n'
    '  if (innerWidth != origWidth || innerHeight != origHeight)\n'
    '     location.reload();\n'
    '}\n'
    'if ((parseInt(navigator.appVersion) == 4) && (navigator.appName == "Netscape")) {\n'
    '\torigWidth = innerWidth;\n'
    '\torigHeight = innerHeight;\n'
    '\tonresize = reDo;\n'
    '}\n'
    'onerror = null; \n'
    '//]]>\n'
    '</script>'
)

# WebHelp popup style — properties on separate lines as in 2019 reference
_WEBHELP_POPUP_STYLE = (
    '<style type="text/css">\n'
    '<!--\n'
    'div.WebHelpPopupMenu { position:absolute;\n'
    'left:0px;\n'
    'top:0px;\n'
    'z-index:4;\n'
    'visibility:hidden; }\n'
    'p.WebHelpNavBar { text-align:left; }\n'
    '-->\n'
    '</style>'
)

# Six WebHelp JS src-script includes
_WEBHELP_SRC_SCRIPTS = (
    '<script type="text/javascript" language="javascript1.2" src="whmsg.js" charset="utf-8"></script>\n'
    '<script type="text/javascript" language="javascript" src="whver.js" charset="utf-8"></script>\n'
    '<script type="text/javascript" language="javascript1.2" src="whutils.js" charset="utf-8"></script>\n'
    '<script type="text/javascript" language="javascript1.2" src="whproxy.js" charset="utf-8"></script>\n'
    '<script type="text/javascript" language="javascript1.2" src="whlang.js" charset="utf-8"></script>\n'
    '<script type="text/javascript" language="javascript1.2" src="whtopic.js" charset="utf-8"></script>'
)

# FIX 2: Inline script template matching 2019 reference formatting exactly:
#   - //<![CDATA[ on same line as closing > (no newline)
#   - Opening brace on its own line
#   - Tab indentation; addButton has no indentation
#   - Two blank lines between addButton and document.write
#   - else\n\tif style (not else if on one line)
#   - //]]></script> with no newline before </script>
# Uses %-formatting to avoid conflicts with JS curly braces.
_INLINE_SCRIPT_TMPL = (
    '<script type="text/javascript" language="javascript1.2">//<![CDATA[\n'
    '<!--\n'
    'if (window.gbWhTopic)\n'
    '{\n'
    '\tvar strUrl = decodeURI(document.location.href);\n'
    '\tvar bc = 0;\n'
    '\tvar n = strUrl.toLowerCase().indexOf("bc-");\n'
    '\tif(n != -1)\n'
    '\t{\n'
    '\t\tdocument.location.replace(strUrl.substring(0, n));\n'
    '\t\tbc = strUrl.substring(n+3);\n'
    '\t}\n'
    '\n'
    '\taddTocInfo("%(toc_path)s");\n'
    'addButton("show",BTN_TEXT,"Show TOC","","","","",0,0,"whd_show0.gif","whd_show2.gif","whd_show1.gif");\n'
    'addButton("hide",BTN_TEXT,"Hide TOC","","","","",0,0,"whd_hide0.gif","whd_hide2.gif","whd_hide1.gif");\n'
    '\n'
    '\n'
    '\tdocument.write("<p style=\\"%(bc_style)s\\"> ");\n'
    'AddMasterBreadcrumbs("index.htm", "%(bc_style)s", "&gt;", "Home", "%(home_href)s");\n'
    'document.write("%(bc_js_write)s");\n'
    '\n'
    '}\n'
    'else\n'
    '\tif (window.gbIE4)\n'
    '\t\tdocument.location.reload();\n'
    '    \n'
    'onLoadHandler = function()\n'
    '{\n'
    '\tif (window.setRelStartPage)\n'
    '\t{\n'
    '    setTimeout("setRelStartPage(\'index.htm\');", 1)\n'
    '\n'
    '    setTimeout("UpdateBreadCrumbsMarker();", 1);\n'
    '    }\n'
    '} \n'
    '\n'
    'if (window.addEventListener){  \n'
    '\twindow.addEventListener(\'load\', onLoadHandler, false);   \n'
    '} else if (window.attachEvent){  \n'
    '\twindow.attachEvent(\'onload\', onLoadHandler);  \n'
    '}\n'
    '\n'
    'function onSetStartPage()\n'
    '{\n'
    '\tautoSync(0);\n'
    '\tsendSyncInfo();\n'
    '\tsendAveInfoOut();\n'
    '}\n'
    '//-->\n'
    '//]]></script>'
)

# FIX 3: Body-start scripts injected immediately after <body> (no space before <script>)
_BODY_START_SCRIPTS = (
    '<script type="text/javascript" language="javascript1.2">//<![CDATA[\n'
    '<!--\n'
    'if (window.writeIntopicBar)\n'
    '\twriteIntopicBar(1);\n'
    '//-->\n'
    '//]]></script>\n'
    '<script type="text/javascript" src="./ehlpdhtm.js" language="JavaScript1.2"></script>'
)

# FIX 4: Body-end script injected before </body>
_BODY_END_SCRIPT = (
    '<script type="text/javascript" language="javascript1.2">//<![CDATA[\n'
    '<!--\n'
    'if (window.writeIntopicBar)\n'
    '\twriteIntopicBar(0);\n'
    '\n'
    'highlightSearch();\n'
    '//-->\n'
    '//]]></script>'
)


# ---------------------------------------------------------------------------
# Breadcrumb extraction
# ---------------------------------------------------------------------------

def _extract_breadcrumb_data(content: str):
    bc_div = re.search(
        r'<div[^>]+class="[^"]*breadcrumbs[^"]*"[^>]*>.*?</div>',
        content, re.IGNORECASE | re.DOTALL,
    )
    if not bc_div:
        return "", "", "welcome_to_tls-4_help.htm"

    bc_html = bc_div.group(0)

    # FIX 5: lowercase home_href to match 2019 case-insensitive file references
    home_m = re.search(
        r'<a[^>]+class="[^"]*breadcrumbs-home[^"]*"[^>]+href="([^"]+)"',
        bc_html, re.IGNORECASE,
    )
    home_href = home_m.group(1).lower() if home_m else "welcome_to_tls-4_help.htm"

    links = re.findall(
        r'<a[^>]+class="[^"]*breadcrumbs-link[^"]*"[^>]+href="([^"]+)"[^>]*>'
        r'\s*<span>([^<]+)</span>',
        bc_html, re.IGNORECASE,
    )

    topic_m = re.search(
        r'<a[^>]+class="[^"]*breadcrumbs-topic[^"]*"[^>]*>\s*<span>([^<]+)</span>',
        bc_html, re.IGNORECASE,
    )
    topic = topic_m.group(1).strip() if topic_m else ""

    toc_parts = [t.strip() for _, t in links] + ([topic] if topic else [])
    toc_path = "\\n".join(toc_parts)

    # FIX 6: lowercase all hrefs inside JS strings
    bc = _BC_STYLE
    parts = []
    for href, text in links:
        parts.append(
            '<a style=\\"' + bc + '\\" href=\\"' + href.lower() + '\\">' +
            text.strip() + '<\\/a> &gt; '
        )
    if topic:
        parts.append(topic + "<\\/p>")
    bc_js_write = "".join(parts)

    return toc_path, bc_js_write, home_href


def _remove_breadcrumb_wrapper(content: str) -> str:
    return re.sub(
        r'\s*<div>\s*<div[^>]+class="[^"]*breadcrumbs[^"]*".*?</div>'
        r'\s*(?:<p[^>]*>\s*(?:<br\s*/?>)?\s*</p>\s*)?</div>',
        "",
        content, flags=re.IGNORECASE | re.DOTALL,
    )


# ---------------------------------------------------------------------------
# Body structure cleanup
# ---------------------------------------------------------------------------

def _unwrap_body_content(content: str) -> str:
    """
    FIX 7: Remove outer <div> wrapper around body content and trailing spacer divs.
    2022 structure: <body>\n  <div>[content]</div>\n  <div><p><br/></p></div>
    """
    # Remove opening content-wrapper <div> immediately after <body>
    content = re.sub(
        r'(<body(?:[^>]*)>)\s*<div>',
        r'\1',
        content, count=1, flags=re.IGNORECASE,
    )
    # Remove the content wrapper's closing </div> + any trailing spacer divs before </body>
    content = re.sub(
        r'\s*</div>\s*(?:<div>\s*<p[^>]*>\s*(?:<br\s*/?>\s*)*</p>\s*</div>\s*)*\s*(?=</body>)',
        '\n',
        content, flags=re.IGNORECASE | re.DOTALL,
    )
    return content


def _clean_table_markup(content: str) -> str:
    """
    FIX 8: Remove XHTML-isms absent from 2019 format:
      - <colgroup>/<tbody> wrapper tags removed (children kept)
      - cellspacing="0" → cellspacing="0px"
    """
    content = re.sub(r'<colgroup[^>]*>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'</colgroup>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<tbody[^>]*>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'</tbody>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'cellspacing="0"', 'cellspacing="0px"', content, flags=re.IGNORECASE)
    return content


# ---------------------------------------------------------------------------
# Main topic conversion
# ---------------------------------------------------------------------------

def _convert_topic(content: str) -> str:
    """
    Transform a single 2022 topic HTML to be compatible with the 2019 WebHelp viewer.
    See inline step comments for what each step does.
    """

    # 1. Strip XML declaration
    content = re.sub(r"<\?xml[^>]+\?>\s*", "", content)

    # 2. Normalise DOCTYPE
    content = re.sub(
        r"<!DOCTYPE html[^>]*>", "<!DOCTYPE HTML>",
        content, count=1, flags=re.IGNORECASE,
    )

    # 3. Remove xmlns; split <html><head> onto separate lines
    content = re.sub(r'(<html)\s+xmlns="[^"]*"', r'\1', content, flags=re.IGNORECASE)
    content = re.sub(r'<html>\s*<head>', '<html>\n<head>', content, count=1, flags=re.IGNORECASE)
    content = re.sub(r'<head>([^\n])', r'<head>\n\1', content, count=1, flags=re.IGNORECASE)

    # 4. Update generator meta to 2019
    content = re.sub(
        r'<meta\s+name="generator"\s+content="[^"]*"\s*/?>',
        '<meta name="generator" content="Adobe RoboHelp Classic 2019" />',
        content, flags=re.IGNORECASE,
    )

    # 5. Remove 2022-only metas
    for name in ("topic-status", "template", "rh-index-keywords", "topic-check-list"):
        content = re.sub(
            rf'<meta\s+name="{name}"\s+content="[^"]*"\s*/?>\s*',
            "", content, flags=re.IGNORECASE,
        )

    # 6. Deduplicate charset meta — keep first, remove subsequent occurrences
    charset_pat = re.compile(r'<meta\s+http-equiv="Content-Type"[^>]*/>', re.IGNORECASE)
    matches = list(charset_pat.finditer(content))
    if len(matches) > 1:
        for m in reversed(matches[1:]):
            content = content[:m.start()] + content[m.end():]

    # 7. Fix title separator: } → >
    content = re.sub(
        r"(<title>[^<]*)}([^<]*</title>)", r"\1>\2",
        content, flags=re.IGNORECASE,
    )

    # 8. Normalise CSS path; produce 2019-style duplicate pair (second has leading space)
    content = content.replace("assets/css/TLS4_GUI.css", "tls4_gui.css")
    content = content.replace("assets/css/tls4_gui.css", "tls4_gui.css")
    content = re.sub(
        r'<link[^>]+href="tls4_gui\.css"[^>]*/?>',
        '<link rel="StyleSheet" href="tls4_gui.css" type="text/css" />\n'
        ' <link rel="StyleSheet" href="tls4_gui.css" type="text/css" />',
        content, count=1, flags=re.IGNORECASE,
    )

    # 9. Remove _rhdefault.css link
    content = re.sub(r'<link[^>]+_rhdefault\.css[^>]*/>\s*', "", content, flags=re.IGNORECASE)

    # 10. Flatten image paths
    content = re.sub(r'assets/images/(?!img/)', "", content)
    content = content.replace("assets/images/img/", "img/")

    # 11. Extract breadcrumb data; strip breadcrumb wrapper from body
    toc_path, bc_js_write, home_href = _extract_breadcrumb_data(content)
    content = _remove_breadcrumb_wrapper(content)

    # 12. Unwrap outer body content div + remove trailing spacer div
    content = _unwrap_body_content(content)

    # 13. Clean table markup (colgroup, tbody, cellspacing)
    content = _clean_table_markup(content)

    # 14. Inject body-start scripts immediately after <body> (no space before <script>)
    content = re.sub(
        r'(<body(?:[^>]*)>)\s*',
        r'\1' + _BODY_START_SCRIPTS + '\n\n',
        content, count=1, flags=re.IGNORECASE,
    )

    # 15. Inject body-end script immediately before </body>
    content = re.sub(
        r'\s*(</body>)',
        '\n' + _BODY_END_SCRIPT + '\n' + r'\1',
        content, count=1, flags=re.IGNORECASE,
    )

    # 16. Build complete 2019 head block and inject before </head>
    inline_script = _INLINE_SCRIPT_TMPL % {
        "toc_path":    toc_path,
        "bc_style":    _BC_STYLE,
        "home_href":   home_href,
        "bc_js_write": bc_js_write,
    }
    head_block = "\n".join([
        _NETSCAPE_RESIZE_SCRIPT,
        _WEBHELP_POPUP_STYLE,
        _WEBHELP_SRC_SCRIPTS,
        inline_script,
    ])
    content = re.sub(
        r"</head>",
        head_block + "\n</head>",
        content, count=1, flags=re.IGNORECASE,
    )

    # 17. Convert line endings to CRLF (matches 2019 reference)
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    content = content.replace('\n', '\r\n')

    return content


def _lowercase_htm_hrefs(content: str) -> str:
    """Normalize all internal .htm href HTML attributes to lowercase."""
    def _lower(m):
        val = m.group(1)
        if val.lower().endswith(".htm") and not val.startswith("http"):
            return f'href="{val.lower()}"'
        return m.group(0)
    return re.sub(r'href="([^"]+\.htm[^"]*)"', _lower, content)


# ---------------------------------------------------------------------------
# Image copying
# ---------------------------------------------------------------------------

def _copy_images(src_assets_images: Path, dest_english: Path, log) -> int:
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
# Show/Hide TOC patch (index.htm frameset listener)
# ---------------------------------------------------------------------------

_SHOW_HIDE_JS = """
<script language="javascript" src="whmsg.js"></script>
<script language="javascript">
// --- Show/Hide TOC support injected by TLS-4 Help Converter ---
function onReceiveNotification(oMsg) {
    if (!oMsg) return true;
    var fs = document.getElementById("whPfset");
    if (!fs) return true;
    if (oMsg.msgId == WH_MSG_SHOWPANE) {
        fs.cols = "260,*";
        return false;
    }
    if (oMsg.msgId == WH_MSG_HIDEPANE) {
        fs.cols = "0,*";
        return false;
    }
    if (oMsg.msgId == WH_MSG_ISPANEVISIBLE) {
        var bVis = (parseInt(fs.cols) > 0);
        if (oMsg.oParam) oMsg.oParam.bVisible = bVis;
        oMsg.bVisible = bVis;
        try { reply(oMsg); } catch(e) {}
        return false;
    }
    return true;
}
function _registerShowHide() {
    if (window.registerListener2) {
        registerListener2(window, WH_MSG_SHOWPANE);
        registerListener2(window, WH_MSG_HIDEPANE);
        registerListener2(window, WH_MSG_ISPANEVISIBLE);
    }
}
function _unregisterShowHide() {
    if (window.unregisterListener2) {
        unregisterListener2(window, WH_MSG_SHOWPANE);
        unregisterListener2(window, WH_MSG_HIDEPANE);
        unregisterListener2(window, WH_MSG_ISPANEVISIBLE);
    }
}
(function () {
    var _prevLoad   = window.onload   || null;
    var _prevUnload = window.onunload || null;
    window.onload = function () { _registerShowHide(); if (_prevLoad) _prevLoad(); };
    window.onunload = function () { _unregisterShowHide(); if (_prevUnload) _prevUnload(); };
})();
// --- end Show/Hide TOC support ---
</script>
"""


def _patch_show_hide_toc(out_root: Path, log) -> None:
    index_path = out_root / "index.htm"
    if not index_path.exists():
        log("  WARNING: index.htm not found — skipping show/hide TOC patch")
        return
    content = index_path.read_text(encoding="utf-8", errors="replace")
    if "_registerShowHide" in content:
        log("  show/hide TOC patch already present — skipping")
        return
    if "</head>" in content.lower():
        content = re.sub(
            r"</head>",
            _SHOW_HIDE_JS + "\n</head>",
            content, count=1, flags=re.IGNORECASE,
        )
        index_path.write_text(content, encoding="utf-8")
        log("  Patched index.htm with show/hide TOC listener support")
    else:
        log("  WARNING: </head> not found in index.htm — show/hide TOC patch skipped")


# ---------------------------------------------------------------------------
# Fix addTocInfo newlines in legacy 2019 topic files
# ---------------------------------------------------------------------------

def _fix_addtocinfo_newlines(content: str) -> str:
    """
    Replace actual newline characters inside addTocInfo("...") string arguments
    with \\n JavaScript escape sequences.

    Adobe RoboHelp 2019 exported addTocInfo() calls with literal line breaks for
    multi-level TOC paths, e.g.:
        addTocInfo("Diagnostics
    Temp Control
    Relay Performance");

    This is a JavaScript SyntaxError — string literals cannot span multiple lines.
    The browser refuses to parse the entire <script> block, so addButton() is never
    called and the Show/Hide TOC buttons never appear.

    This function fixes those calls so the path is a valid single-line JS string:
        addTocInfo("Diagnostics\nTemp Control\nRelay Performance");
    """
    def _replacer(m):
        arg = m.group(1)
        if '\n' not in arg and '\r' not in arg:
            return m.group(0)
        # Replace each newline (CRLF, CR, or LF) with the two-char JS escape \n
        fixed = re.sub(r'\r\n|\r|\n', r'\\n', arg)
        return f'addTocInfo("{fixed}")'

    # [^"] matches any char including \n (character classes always match newlines)
    return re.sub(r'addTocInfo\("([^"]*)"\)', _replacer, content)


def _fix_addtocinfo_newlines_in_dir(out_root: Path, log) -> int:
    """Apply _fix_addtocinfo_newlines to every .htm file in out_root."""
    fixed = 0
    for htm_file in out_root.glob("*.htm"):
        try:
            content = htm_file.read_text(encoding="utf-8", errors="replace")
            new_content = _fix_addtocinfo_newlines(content)
            if new_content != content:
                htm_file.write_text(new_content, encoding="utf-8")
                fixed += 1
        except Exception:
            pass
    return fixed


# ---------------------------------------------------------------------------
# Main conversion entry point
# ---------------------------------------------------------------------------

def convert(
    new_zip_path: str,
    old_zip_path: str,
    output_zip_path: str,
    log_callback=None,
) -> None:
    def log(msg):
        _log(msg, log_callback)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        new_root = tmp / "new"
        old_root = tmp / "old"
        out_root = tmp / "out" / "english"
        new_root.mkdir(); old_root.mkdir(); out_root.mkdir(parents=True)

        log("── Step 1/6: Extracting packages")
        new_english = _extract_zip(new_zip_path, new_root, log)
        old_english = _extract_zip(old_zip_path, old_root, log)

        nested = old_english / "help.zip"
        if nested.exists():
            log("  Found nested help.zip inside 2019 package — extracting…")
            nested_root = old_root / "_nested"
            nested_root.mkdir()
            with zipfile.ZipFile(nested, "r") as zf:
                zf.extractall(nested_root)
            old_english = _find_english_dir(nested_root) or old_english
            log(f"  Nested content dir: .../{old_english.relative_to(old_root)}")

        log("── Step 2/6: Copying 2019 WebHelp framework")
        framework_count = 0
        for item in old_english.iterdir():
            dest = out_root / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
            framework_count += 1
        log(f"  Copied {framework_count} items from 2019 framework")

        log("── Step 3/6: Patching show/hide TOC support")
        _patch_show_hide_toc(out_root, log)

        log("── Step 4/6: Converting 2022 topic files")
        topic_files = list(new_english.glob("*.htm"))
        converted = 0
        errors = []
        for src_file in topic_files:
            dest_name = src_file.name.lower()
            dest_path = out_root / dest_name
            try:
                raw = src_file.read_text(encoding="utf-8", errors="replace")
                out = _convert_topic(raw)
                out = _lowercase_htm_hrefs(out)
                dest_path.write_text(out, encoding="utf-8")
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

        fixed = _fix_addtocinfo_newlines_in_dir(out_root, log)
        if fixed:
            log(f"  Fixed addTocInfo newlines in {fixed} legacy file(s) — Show/Hide TOC will now work on those pages")

        log("── Step 5/6: Copying images from 2022 package")
        assets_images = new_english / "assets" / "images"
        img_count = _copy_images(assets_images, out_root, log)
        log(f"  Copied {img_count} image files")
        for ext in ("*.png", "*.PNG", "*.gif", "*.GIF", "*.jpg", "*.JPG"):
            for img in new_english.glob(ext):
                dest = out_root / img.name
                if not dest.exists():
                    shutil.copy2(img, dest)

        log("── Step 6/6: Packaging output zip")
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for file_path in sorted(out_root.rglob("*")):
                if file_path.is_file():
                    arcname = "help/english/" + str(file_path.relative_to(out_root))
                    zout.write(file_path, arcname)

        size_mb = Path(output_zip_path).stat().st_size / (1024 * 1024)
        log(f"  Output: {Path(output_zip_path).name} ({size_mb:.1f} MB)")
        log("── Conversion complete ✓")
