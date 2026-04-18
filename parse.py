"""
parse.py
Parse a PubMed Central HTML article into a nested dictionary structure.

Output structure:
{
    "pmcid": "PMC1234567",
    "title": "...",
    "abstract": "...",
    "sections": {
        "Introduction": "...",
        "Methods": "...",
        "Results": "...",
        "Discussion": "...",
        "Data Availability": "...",
        ...
    },
    "metadata": {
        "authors": [...],
        "journal": "...",
        "date": "...",
        "doi": "...",
        "keywords": [...],
    },
    "references": [...],
    "figures": [...],
    "tables": [...]
}
"""

from bs4 import BeautifulSoup
import re


def parse_paper(html: str, pmcid: str = "unknown") -> dict:
    """
    Parse a PMC article HTML into a nested dictionary.

    Args:
        html: raw HTML string of the PMC article page
        pmcid: the PMCID string (used as paper identifier)

    Returns:
        Nested dict with title, abstract, sections, metadata, etc.
    """
    soup = BeautifulSoup(html, "lxml")

    paper = {
        "pmcid": pmcid,
        "title": _parse_title(soup),
        "abstract": _parse_abstract(soup),
        "sections": _parse_sections(soup),
        "metadata": _parse_metadata(soup),
        "references": _parse_references(soup),
        "figures": _parse_figures(soup),
        "tables": _parse_tables(soup),
    }

    return paper


# ── Private helpers ──────────────────────────────────────────────────────────

def _parse_title(soup: BeautifulSoup) -> str:
    """Extract article title."""
    # PMC uses <h1 class="content-title"> or <h1 id="article-title">
    for selector in [
        "h1.content-title",
        "h1#article-title",
        "h1.title",
        "[id='article-title']",
    ]:
        tag = soup.select_one(selector)
        if tag:
            return tag.get_text(separator=" ", strip=True)

    # Fallback: first <h1>
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def _parse_abstract(soup: BeautifulSoup) -> str:
    """Extract the abstract text."""
    # PMC wraps abstract in <div class="abstract"> or <section class="abstract">
    for selector in [
        "div.abstract",
        "section.abstract",
        "#abstract",
        "[class*='abstract']",
    ]:
        tag = soup.select_one(selector)
        if tag:
            return tag.get_text(separator="\n", strip=True)
    return ""


def _parse_sections(soup: BeautifulSoup) -> dict:
    """
    Extract body sections as {section_heading: section_text}.
    Handles both flat and nested section structures.
    """
    sections = {}

    # PMC article body lives in <div class="pmc-wm"> or <article> or <div id="pmc-article-body">
    body = (
        soup.find("div", class_="pmc-wm")
        or soup.find("article")
        or soup.find("div", id="pmc-article-body")
        or soup.find("div", class_="article-body")
        or soup.body
    )

    if not body:
        return sections

    # Find all <section> tags or <div class="sec"> (PMC uses both)
    section_tags = body.find_all(["section"], recursive=True)
    if not section_tags:
        section_tags = body.find_all("div", class_=re.compile(r"\bsec\b"))

    for sec in section_tags:
        # Section heading is usually h2 or h3
        heading_tag = sec.find(["h2", "h3", "h4"])
        if not heading_tag:
            continue
        heading = heading_tag.get_text(strip=True)
        if not heading:
            continue

        # Get text of the whole section (minus sub-section headings to avoid duplication)
        # Remove nested section text
        for nested in sec.find_all(["section", "div"], class_=re.compile(r"\bsec\b")):
            nested.decompose()

        text = sec.get_text(separator="\n", strip=True)
        # Remove the heading from the top of the text
        text = text.replace(heading, "", 1).strip()

        if heading in sections:
            # Append if heading repeats (e.g., multiple "Methods" subsections)
            sections[heading] += "\n" + text
        else:
            sections[heading] = text

    # Fallback: if no sections found, try heading-based splitting
    if not sections:
        sections = _fallback_heading_split(body)

    return sections


def _fallback_heading_split(body) -> dict:
    """
    Fallback: split body by h2/h3 headings when section tags aren't present.
    """
    sections = {}
    current_heading = "Body"
    current_text = []

    for tag in body.find_all(["h2", "h3", "p"], recursive=True):
        if tag.name in ["h2", "h3"]:
            if current_text:
                sections[current_heading] = "\n".join(current_text).strip()
            current_heading = tag.get_text(strip=True)
            current_text = []
        elif tag.name == "p":
            current_text.append(tag.get_text(strip=True))

    if current_text:
        sections[current_heading] = "\n".join(current_text).strip()

    return sections


def _parse_metadata(soup: BeautifulSoup) -> dict:
    """Extract metadata: authors, journal, date, DOI, keywords."""
    metadata = {
        "authors": _parse_authors(soup),
        "journal": _parse_journal(soup),
        "date": _parse_date(soup),
        "doi": _parse_doi(soup),
        "keywords": _parse_keywords(soup),
    }
    return metadata


def _parse_authors(soup: BeautifulSoup) -> list:
    """Extract list of author names."""
    authors = []

    # PMC: authors in <div class="contrib-group"> or <span class="authors-list">
    contrib = soup.find("div", class_=re.compile(r"contrib"))
    if contrib:
        for name_tag in contrib.find_all(["span", "a"], class_=re.compile(r"name|author")):
            name = name_tag.get_text(strip=True)
            if name:
                authors.append(name)
        if authors:
            return authors

    # Fallback: look for meta tags
    for meta in soup.find_all("meta", attrs={"name": "citation_author"}):
        authors.append(meta.get("content", ""))

    return authors


def _parse_journal(soup: BeautifulSoup) -> str:
    """Extract journal name."""
    # Meta tag
    meta = soup.find("meta", attrs={"name": "citation_journal_title"})
    if meta:
        return meta.get("content", "")

    # PMC journal title tag
    tag = soup.find("span", class_=re.compile(r"journal|source"))
    if tag:
        return tag.get_text(strip=True)

    return ""


def _parse_date(soup: BeautifulSoup) -> str:
    """Extract publication date."""
    # Meta tag
    for name in ["citation_publication_date", "citation_date", "DC.Date"]:
        meta = soup.find("meta", attrs={"name": name})
        if meta:
            return meta.get("content", "")

    # PMC pub-date tag
    pub_date = soup.find("span", class_=re.compile(r"pub.?date|date"))
    if pub_date:
        return pub_date.get_text(strip=True)

    return ""


def _parse_doi(soup: BeautifulSoup) -> str:
    """Extract DOI."""
    meta = soup.find("meta", attrs={"name": "citation_doi"})
    if meta:
        return meta.get("content", "")

    # Look for DOI link pattern
    doi_link = soup.find("a", href=re.compile(r"doi\.org"))
    if doi_link:
        return doi_link.get("href", "").replace("https://doi.org/", "")

    return ""


def _parse_keywords(soup: BeautifulSoup) -> list:
    """Extract keywords."""
    keywords = []

    kw_section = soup.find(["div", "section"], class_=re.compile(r"keyword"))
    if kw_section:
        for kw in kw_section.find_all(["span", "li", "a"]):
            text = kw.get_text(strip=True)
            if text:
                keywords.append(text)

    if not keywords:
        meta = soup.find("meta", attrs={"name": "keywords"})
        if meta:
            keywords = [k.strip() for k in meta.get("content", "").split(",")]

    return keywords


def _parse_references(soup: BeautifulSoup) -> list:
    """Extract list of references."""
    refs = []

    ref_section = soup.find(["ol", "ul"], class_=re.compile(r"ref"))
    if not ref_section:
        ref_section = soup.find("div", class_=re.compile(r"ref"))

    if ref_section:
        for li in ref_section.find_all("li"):
            text = li.get_text(separator=" ", strip=True)
            if text:
                refs.append(text)

    return refs


def _parse_figures(soup: BeautifulSoup) -> list:
    """Extract figure captions."""
    figures = []
    for fig in soup.find_all("figure"):
        caption = fig.find("figcaption")
        figures.append({
            "id": fig.get("id", ""),
            "caption": caption.get_text(strip=True) if caption else ""
        })
    return figures


def _parse_tables(soup: BeautifulSoup) -> list:
    """Extract tables as list of {caption, headers, rows}."""
    tables = []
    for table in soup.find_all("table"):
        caption_tag = table.find_previous("caption") or table.find("caption")
        caption = caption_tag.get_text(strip=True) if caption_tag else ""

        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = []
        for tr in table.find_all("tr"):
            row = [td.get_text(strip=True) for td in tr.find_all("td")]
            if row:
                rows.append(row)

        tables.append({"caption": caption, "headers": headers, "rows": rows})
    return tables


def parse_multiple(html_dict: dict) -> dict:
    """
    Parse multiple papers.

    Args:
        html_dict: dict mapping pmcid -> html string

    Returns:
        dict mapping pmcid -> parsed paper dict
    """
    results = {}
    for pmcid, html in html_dict.items():
        if html:
            print(f"[parse] Parsing {pmcid}...")
            results[pmcid] = parse_paper(html, pmcid=pmcid)
        else:
            print(f"[parse] Skipping {pmcid} (no HTML)")
    return results
