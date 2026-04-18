"""
parsers/generic.py
Fallback heuristic parser for unknown journals.

Strategy:
  - Relies entirely on <meta name="citation_*"> tags for metadata
    (nearly universal across journals — part of the Google Scholar spec)
  - Uses heading-based section splitting for body text
  - Works reasonably well on any journal that follows basic HTML conventions

This parser will never be as accurate as a journal-specific one,
but it's far better than returning empty results.
When it's used, a warning is printed so you know to add a proper parser.
"""

import re
from .base import BaseParser


class GenericParser(BaseParser):
    """
    Heuristic fallback parser. Used when no journal-specific parser matches.
    Logs a warning so developers know a new parser may be needed.
    """

    def __init__(self, html: str, url: str = "", identifier: str = "unknown"):
        super().__init__(html, url=url, identifier=identifier)
        print(
            f"[parser] ⚠️  No specific parser found for '{url or identifier}'. "
            f"Using GenericParser — results may be incomplete. "
            f"Consider adding a dedicated parser in parsers/."
        )

    def parse_title(self) -> str:
        # citation_title meta is nearly universal
        title = self._meta("citation_title")
        if title:
            return title
        # og:title is a reliable fallback
        title = self._meta(prop="og:title")
        if title:
            return title
        return self._text(self.soup.find("h1"))

    def parse_abstract(self) -> str:
        # Try common abstract containers in order of reliability
        candidates = [
            self.soup.find("meta",    attrs={"name": "description"}),
            self.soup.find("section", attrs={"data-title": re.compile(r"abstract", re.I)}),
            self.soup.find("div",     class_=re.compile(r"\babstract\b", re.I)),
            self.soup.find("section", class_=re.compile(r"\babstract\b", re.I)),
            self.soup.find("div",     id=re.compile(r"\babstract\b", re.I)),
        ]
        for tag in candidates:
            if tag is None:
                continue
            # Meta tag — return content directly
            if tag.name == "meta":
                return tag.get("content", "")
            text = tag.get_text(separator="\n", strip=True)
            text = re.sub(r"^Abstract\s*", "", text, flags=re.IGNORECASE).strip()
            if text:
                return text

        return self._meta(prop="og:description") or ""

    def parse_sections(self) -> dict:
        # Find the most likely article body container
        body = (
            self.soup.find("article")
            or self.soup.find("main")
            or self.soup.find("div", id=re.compile(r"article|content|body", re.I))
            or self.soup.find("div", class_=re.compile(r"article|content|body", re.I))
            or self.soup.body
        )
        if not body:
            return {}

        # Try <section data-title="..."> first (Nature-style, increasingly common)
        sections = {}
        for sec in body.find_all("section", attrs={"data-title": True}):
            heading = sec.get("data-title", "").strip()
            if heading and heading.lower() != "abstract":
                text = sec.get_text(separator="\n", strip=True)
                text = text.replace(heading, "", 1).strip()
                if text:
                    sections[heading] = text

        if sections:
            return sections

        # Fallback: heading-based split
        return self._fallback_heading_split(body)

    def parse_authors(self) -> list:
        # citation_author meta is nearly universal
        authors = self._meta_all("citation_author")
        if authors:
            return authors
        # Try common author container patterns
        for cls in [r"author-name", r"authors", r"contrib"]:
            tags = self.soup.find_all(["span", "a", "li"], class_=re.compile(cls, re.I))
            if tags:
                return [self._text(t) for t in tags if self._text(t)]
        return []

    def parse_journal(self) -> str:
        return (
            self._meta("citation_journal_title")
            or self._meta("citation_publisher")
            or self._meta(prop="og:site_name")
        )

    def parse_date(self) -> str:
        return (
            self._meta("citation_publication_date")
            or self._meta("citation_online_date")
            or self._meta("citation_date")
            or self._meta("DC.Date")
        )

    def parse_doi(self) -> str:
        doi = self._meta("citation_doi")
        if doi:
            return doi
        tag = self.soup.find("a", href=re.compile(r"doi\.org"))
        return tag["href"].replace("https://doi.org/", "") if tag else ""

    def parse_keywords(self) -> list:
        meta = self._meta("keywords")
        if meta:
            return [k.strip() for k in meta.split(",") if k.strip()]
        kw_div = self.soup.find(["div", "section", "ul"], class_=re.compile(r"keyword|subject|tag", re.I))
        if kw_div:
            return [self._text(k) for k in kw_div.find_all(["a", "span", "li"]) if self._text(k)]
        return []

    def parse_references(self) -> list:
        ref_section = (
            self.soup.find("ol",      class_=re.compile(r"reference", re.I))
            or self.soup.find("ul",   class_=re.compile(r"reference", re.I))
            or self.soup.find("div",  class_=re.compile(r"reference", re.I))
            or self.soup.find("section", class_=re.compile(r"reference", re.I))
        )
        if ref_section:
            return [
                li.get_text(separator=" ", strip=True)
                for li in ref_section.find_all("li")
                if li.get_text(strip=True)
            ]
        return []

    def parse_figures(self) -> list:
        return self._figures()

    def parse_tables(self) -> list:
        return self._tables()
