"""
LibreTexts content source — crawl bookshelves and extract page content.

The actual chunk/embed/store is handled by content_ingestion_core.ingest_sections().
"""
import logging
import re

import httpx

from src.lms_agents.tools.content_ingestion_core import ingest_sections, source_exists

log = logging.getLogger(__name__)

# Libraries available for ingestion
LIBRARIES = {
    "k12": {
        "base_url": "https://k12.libretexts.org",
        "subjects": {
            "Mathematics/Algebra": {"grade": "8", "subject": "Mathematics"},
            "Mathematics/Geometry": {"grade": "9", "subject": "Mathematics"},
            "Mathematics/Precalculus": {"grade": "11", "subject": "Mathematics"},
            "Mathematics/Trigonometry": {"grade": "10", "subject": "Mathematics"},
            "Mathematics/Calculus": {"grade": "11", "subject": "Mathematics"},
            "Mathematics/Statistics": {"grade": "11", "subject": "Mathematics"},
            "Mathematics/Analysis": {"grade": "12", "subject": "Mathematics"},
            "Science_and_Technology": {"grade": "7", "subject": "Science"},
            "Economics": {"grade": "11", "subject": "Social Studies"},
            "United_States_Government": {"grade": "11", "subject": "Social Studies"},
            "Geography": {"grade": "6", "subject": "Social Studies"},
        },
    },
    "bio": {
        "base_url": "https://bio.libretexts.org",
        "subjects": {
            "Introductory_and_General_Biology/General_Biology_(Boundless)": {"grade": "9", "subject": "Biology"},
            "Introductory_and_General_Biology/Biology_(Kimball)": {"grade": "10", "subject": "Biology"},
            "Human_Biology": {"grade": "10", "subject": "Biology"},
            "Cell_and_Molecular_Biology": {"grade": "11", "subject": "Biology"},
            "Ecology": {"grade": "10", "subject": "Biology"},
            "Genetics": {"grade": "11", "subject": "Biology"},
        },
    },
    "chem": {
        "base_url": "https://chem.libretexts.org",
        "subjects": {
            "Introductory_Chemistry": {"grade": "10", "subject": "Chemistry"},
            "General_Chemistry": {"grade": "11", "subject": "Chemistry"},
            "Organic_Chemistry": {"grade": "12", "subject": "Chemistry"},
        },
    },
    "phys": {
        "base_url": "https://phys.libretexts.org",
        "subjects": {
            "Classical_Mechanics": {"grade": "11", "subject": "Physics"},
            "Electricity_and_Magnetism": {"grade": "11", "subject": "Physics"},
            "Waves_and_Optics": {"grade": "12", "subject": "Physics"},
        },
    },
    "socialsci": {
        "base_url": "https://socialsci.libretexts.org",
        "subjects": {
            "History": {"grade": "10", "subject": "Social Studies"},
            "Psychology": {"grade": "11", "subject": "Social Studies"},
        },
    },
}


def get_subject_bookshelves(base_url="https://k12.libretexts.org"):
    """Get list of available subject bookshelves for a library."""
    resp = httpx.get(f"{base_url}/Bookshelves", timeout=15, follow_redirects=True)
    resp.raise_for_status()
    domain = base_url.replace("https://", "").replace("http://", "")
    matches = re.findall(rf'href="https://{re.escape(domain)}/Bookshelves/([A-Za-z_]+)"', resp.text)
    return sorted(set(matches))


def get_leaf_page_urls(subject_path, base_url="https://k12.libretexts.org"):
    """
    Recursively crawl to find leaf pages (actual content, not section indexes).
    """
    urls = []
    visited = set()

    def crawl(url, depth=0):
        if depth > 6 or url in visited:
            return
        visited.add(url)
        try:
            resp = httpx.get(url, timeout=15, follow_redirects=True)
            resp.raise_for_status()
        except Exception as e:
            log.warning(f"  Failed to fetch {url}: {e}")
            return

        domain = base_url.replace("https://", "").replace("http://", "")
        all_links = re.findall(
            rf'href="(https://{re.escape(domain)}/Bookshelves/[^"]+)"',
            resp.text,
        )
        current_path = url.replace(base_url + "/Bookshelves/", "")
        child_links = []
        for link in all_links:
            link_path = link.replace(base_url + "/Bookshelves/", "")
            if (link_path.startswith(current_path + "/")
                and link_path != current_path
                and "Front_Matter" not in link_path
                and "Back_Matter" not in link_path
                and link not in visited):
                child_links.append(link)

        child_links = sorted(set(child_links))

        if not child_links:
            urls.append(url)
        else:
            for child_url in child_links:
                crawl(child_url, depth + 1)

    start_url = f"{base_url}/Bookshelves/{subject_path}"
    crawl(start_url)
    return urls


def extract_page_content(url, browser=None):
    """Extract clean text content and images from a LibreTexts page using Playwright."""
    own_browser = False
    try:
        if browser is None:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=True)
            own_browser = True

        page = browser.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_timeout(5000)

        body_text = page.inner_text("body")
        lines = [l.strip() for l in body_text.split("\n") if len(l.strip()) > 30]

        skip_phrases = ["Living Library", "LibreTexts project", "multi-institutional",
                        "Creative Commons", "newcommand", "Table of Contents", "Back Matter"]

        sections = []
        current_heading = None
        current_text = ""

        for line in lines:
            if any(s in line for s in skip_phrases):
                continue
            if len(line) < 80 and not line.endswith(".") and not line.endswith(","):
                if current_text.strip() and len(current_text.strip()) > 50:
                    sections.append({
                        "page": None,
                        "heading": current_heading,
                        "text": current_text.strip(),
                    })
                    current_text = ""
                current_heading = line
            else:
                current_text += line + " "

        if current_text.strip() and len(current_text.strip()) > 50:
            sections.append({
                "page": None,
                "heading": current_heading,
                "text": current_text.strip(),
            })

        images = []
        img_elements = page.query_selector_all("img")
        for img in img_elements:
            src = img.get_attribute("src") or ""
            if src and "logo" not in src.lower() and "icon" not in src.lower() and len(src) > 20:
                alt = img.get_attribute("alt") or ""
                images.append({"url": src, "alt": alt})

        page.close()
        if own_browser:
            browser.close()

        return sections, images

    except Exception as e:
        log.warning(f"  Failed: {url}: {e}")
        return [], []


def ingest_page(url, subject, grade, source_label, browser=None):
    """Ingest a single LibreTexts page via the shared core pipeline."""
    if source_exists(source_label):
        log.info(f"  Skipping (exists): {source_label}")
        return 0

    sections, images = extract_page_content(url, browser=browser)
    if not sections:
        return 0

    # Quality check — skip pages that are mostly boilerplate
    total_content = " ".join(s["text"] for s in sections)
    if "Living Library" in total_content and len(total_content) < 500:
        log.info("    (skipped — boilerplate only)")
        return 0

    result = ingest_sections(
        sections=sections,
        name=source_label,
        subject=subject,
        grade_level=grade,
        upload_lane="oer_textbook",
        file_type="url",
        original_path=url,
    )
    return result.get("chunk_count", 0)
