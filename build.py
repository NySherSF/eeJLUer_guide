from pathlib import Path
import base64
import mimetypes
import shutil
import zipfile
import re
import unicodedata

import markdown
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


# config

ROOT = Path(__file__).resolve().parent

PDF_FILES = [
    "README.md",
    "Timeline.md",
    "Learn.md",
    "Daily.md",
    "Concept.md",
    "Easy.md",
    "Resources.md",
]

HTML_FILES = [
    "Pitfalls.md",
]

OUTPUT_DIR = ROOT / "build"

CSS_FILE = ROOT / "style.css"

ZIP_FILE = ROOT / "latest_release.zip"

# toc config
def github_slug(text: str) -> str:

    text = BeautifulSoup(
        text,
        "html.parser",
    ).get_text()

    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    text = text.lower()

    text = re.sub(
        r"[^\w\u4e00-\u9fff -]",
        "",
        text,
    )

    text = re.sub(
        r"\s+",
        "-",
        text,
    )

    return text

# md to html

def markdown_to_html(md_text: str) -> str:

    html = markdown.markdown(
        md_text,
        extensions=[
            "extra",
            "tables",
            "fenced_code",
            "footnotes",
            "attr_list",
        ],
        output_format="html",
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    used_ids = {}

    for heading in soup.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6"]
    ):

        slug = github_slug(
            heading.get_text()
        )

        if slug in used_ids:
            used_ids[slug] += 1
            slug = f"{slug}-{used_ids[slug]}"
        else:
            used_ids[slug] = 0

        heading["id"] = slug

    return str(soup)

# base64 encode

def image_to_base64(image_path: Path) -> str:

    mime_type, _ = mimetypes.guess_type(
        image_path.name
    )

    if mime_type is None:
        mime_type = "application/octet-stream"

    data = image_path.read_bytes()

    encoded = base64.b64encode(data).decode(
        "ascii"
    )

    return f"data:{mime_type};base64,{encoded}"

# embed images

def embed_images(
    html: str,
) -> str:

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for img in soup.find_all("img"):

        src = img.get("src")

        if not src:
            continue

        src = src.replace("\\", "/")

        image_path = (
            ROOT / src
        ).resolve()

        if not image_path.exists():
            print(
                f"WARNING: image not found: {src}"
            )
            continue

        if not image_path.is_file():
            continue

        img["src"] = image_to_base64(
            image_path
        )

        print(
            f"Embedded: {image_path}"
        )

    return str(soup)

# css

def load_css() -> str:

    return CSS_FILE.read_text(
        encoding="utf-8"
    )

# build full html

def build_full_html(
    body: str,
    title: str,
    css: str,
) -> str:

    return f"""<!DOCTYPE html>
<html lang="zh-CN">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>{title}</title>

<style>
{css}
</style>

</head>

<body>

{body}

</body>

</html>
"""

# build pdf

def build_pdf(
    browser,
    html_path: Path,
    pdf_path: Path,
):

    pdf_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    page = browser.new_page()

    page.goto(
        html_path.as_uri(),
        wait_until="networkidle",
    )

    page.pdf(
        path=str(pdf_path),
        format="A4",
        print_background=True,
        prefer_css_page_size=True,
        margin={
            "top": "0",
            "right": "0",
            "bottom": "0",
            "left": "0",
        },
    )

    page.close()

# build html file

def build_html_file(
    md_file: Path,
    output_file: Path,
    css: str,
):

    md_text = md_file.read_text(
        encoding="utf-8"
    )

    body = markdown_to_html(
        md_text
    )

    body = embed_images(
        body
    )

    html = build_full_html(
        body=body,
        title=md_file.stem,
        css=css,
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file.write_text(
        html,
        encoding="utf-8",
    )

    print(
        f"Generated: {output_file}"
    )

# main

def main():

    if OUTPUT_DIR.exists():
        shutil.rmtree(
            OUTPUT_DIR
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    pdf_dir = OUTPUT_DIR / "pdf"

    html_dir = OUTPUT_DIR / "html"

    pdf_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    html_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    css = load_css()

    # pdf

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        for filename in PDF_FILES:

            md_file = ROOT / filename

            if not md_file.exists():
                raise FileNotFoundError(
                    f"PDF source not found: {md_file}"
                )

            print(
                f"Building PDF: {filename}"
            )

            md_text = md_file.read_text(
                encoding="utf-8"
            )

            body = markdown_to_html(
                md_text
            )

            html = build_full_html(
                body=body,
                title=md_file.stem,
                css=css,
            )

            temp_html = (
                OUTPUT_DIR
                / f".{md_file.stem}.html"
            )

            temp_html.write_text(
                html,
                encoding="utf-8",
            )

            pdf_file = (
                pdf_dir
                / f"{md_file.stem}.pdf"
            )

            build_pdf(
                browser=browser,
                html_path=temp_html,
                pdf_path=pdf_file,
            )

            temp_html.unlink()

            print(
                f"Generated: {pdf_file}"
            )

        browser.close()

    # html

    for filename in HTML_FILES:

        md_file = ROOT / filename

        if not md_file.exists():
            raise FileNotFoundError(
                f"HTML source not found: {md_file}"
            )

        html_file = (
            html_dir
            / f"{md_file.stem}.html"
        )

        build_html_file(
            md_file=md_file,
            output_file=html_file,
            css=css,
        )

    # zip

    if ZIP_FILE.exists():
        ZIP_FILE.unlink()

    print("Creating ZIP...")

    with zipfile.ZipFile(
        ZIP_FILE,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as zipf:

        for file in OUTPUT_DIR.rglob("*"):

            if not file.is_file():
                continue

            if file.name.startswith("."):
                continue

            zipf.write(
                file,
                file.relative_to(
                    OUTPUT_DIR
                ),
            )

    print(
        f"Generated: {ZIP_FILE}"
    )

    print(
        "Build completed successfully."
    )


if __name__ == "__main__":
    main()