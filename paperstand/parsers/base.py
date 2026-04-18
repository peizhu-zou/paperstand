"""
parsers/base.py
Abstract base class all journal parsers must inherit from.
Defines the standard interface and shared utility methods.
"""

from abc import ABC, abstractmethod
from bs4 import BeautifulSoup
import re


class BaseParser(ABC):
    """
    Every journal parser inherits from this class and implements
    the abstract methods below. The parse() method is the only
    method callers need — it returns a standardized nested dict.
    """

    def __init__(self, html: str, url: str = "", identifier: str = "unknown"):
        self.soup       = BeautifulSoup(html, "lxml")
        self.url        = url
        self.identifier = identifier  # PMCID, DOI slug, or URL slug

    # ── Public entry point ────────────────────────────────────────────────────

    def parse(self) -> dict:
        """Run full parse and return standardized nested dict."""
        return {
            "identifier": self.identifier,
            "url":        self.url,
            "title":      self.parse_title(),
            "abstract":   self.parse_abstract(),
            "sections":   self.parse_sections(),
            "metadata": {
                "authors":  self.parse_authors(),
                "journal":  self.parse_journal(),
                "date":     self.parse_date(),
                "doi":      self.parse_doi(),
                "keywords": self.parse_keywords(),
            },
            "references": self.parse_references(),
            "figures":    self.parse_figures(),
            "tables":     self.parse_tables(),
        }

    # ── Abstract methods every parser must implement ──────────────────────────

    @abstractmethod
    def parse_title(self) -> str:
        pass

    @abstractmethod
    def parse_abstract(self) -> str:
        pass

    @abstractmethod
    def parse_sections(self) -> dict:
        """
        Return {section_heading: section_text} for all body sections.
        Use original heading strings as keys (e.g. "Materials and Methods").
        The extractor handles alias resolution.
        """
        pass

    @abstractmethod
    def parse_authors(self) -> list:
        pass

    @abstractmethod
    def parse_journal(self) -> str:
        pass

    @abstractmethod
    def parse_date(self) -> str:
        pass

    @abstractmethod
    def parse_doi(self) -> str:
        pass

    @abstractmethod
    def parse_keywords(self) -> list:
        pass

    @abstractmethod
    def parse_references(self) -> list:
        pass

    @abstractmethod
    def parse_figures(self) -> list:
        """Return list of {"id": ..., "caption": ...} dicts."""
        pass

    @abstractmethod
    def parse_tables(self) -> list:
        """Return list of {"caption": ..., "headers": [...], "rows": [[...]]} dicts."""
        pass

    # ── Shared utilities ──────────────────────────────────────────────────────

    def _meta(self, name: str = None, prop: str = None) -> str:
        """Get <meta name="..."> or <meta property="..."> content."""
        if name:
            tag = self.soup.find("meta", attrs={"name": name})
        elif prop:
            tag = self.soup.find("meta", attrs={"property": prop})
        else:
            return ""
        return tag.get("content", "").strip() if tag else ""

    def _meta_all(self, name: str) -> list:
        """Get content of all <meta> tags with the same name (e.g. multiple authors)."""
        tags = self.soup.find_all("meta", attrs={"name": name})
        return [t.get("content", "").strip() for t in tags if t.get("content", "").strip()]

    def _text(self, tag) -> str:
        """Clean text from a BS4 tag. Returns empty string if tag is None."""
        if tag is None:
            return ""
        return re.sub(r"\s+", " ", tag.get_text(separator=" ")).strip()

    def _figures(self) -> list:
        """Default figure extraction — works for most journals."""
        figures = []
        for fig in self.soup.find_all("figure"):
            caption = fig.find("figcaption")
            figures.append({
                "id":      fig.get("id", ""),
                "caption": self._text(caption),
            })
        return figures

    def _tables(self) -> list:
        """Default table extraction — works for most journals."""
        tables = []
        for table in self.soup.find_all("table"):
            caption_tag = table.find_previous("caption") or table.find("caption")
            headers = [self._text(th) for th in table.find_all("th")]
            rows = [
                [self._text(td) for td in tr.find_all("td")]
                for tr in table.find_all("tr") if tr.find("td")
            ]
            tables.append({
                "caption": self._text(caption_tag),
                "headers": headers,
                "rows":    rows,
            })
        return tables

    def _fallback_heading_split(self, body) -> dict:
        """
        Last-resort section extraction: split body text by h2/h3 headings.
        Used when journal-specific selectors find nothing.
        """
        sections = {}
        current_heading = None
        current_text = []

        for tag in body.find_all(["h2", "h3", "p"], recursive=True):
            if tag.name in ["h2", "h3"]:
                if current_heading and current_text:
                    sections[current_heading] = "\n".join(current_text).strip()
                current_heading = self._text(tag)
                current_text = []
            elif tag.name == "p" and current_heading:
                text = self._text(tag)
                if text:
                    current_text.append(text)

        if current_heading and current_text:
            sections[current_heading] = "\n".join(current_text).strip()

        return sections
