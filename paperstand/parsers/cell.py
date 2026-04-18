"""
parsers/cell.py
Parser for Cell Press journals (cell.com).
Covers: Cell, Cell Reports, Cell Metabolism, Cell Host & Microbe,
        Current Biology, Immunity, Neuron, etc.

Structure:
  Title:    <meta name="citation_title">
            fallback: <h1 class="article-header__title">
  Abstract: <div class="abstract"> or <section class="abstract">
  Body:     <div class="body"> or <div id="article-body">
              └── <section> with <h2>/<h3> headings
  Authors:  <meta name="citation_author">
            fallback: <span class="author-name">
  Keywords: <div class="keywords">
  Refs:     <section class="references"> or <ul class="references">
  Metadata: <meta name="citation_*">

Note: Cell Press blocks server-side scraping. HTML must be saved
      from browser and loaded via --html-dir.
"""

import re
from bs4 import BeautifulSoup
from .base import BaseParser


class CellParser(BaseParser):

    def parse_title(self) -> str:
        title = self._meta("citation_title")
        if title:
            return title
        tag = self.soup.find("h1", class_=re.compile(r"article-header__title|article-title|^title$"))
        return self._text(tag) if tag else self._text(self.soup.find("h1"))

    def parse_abstract(self) -> str:
        for tag_name, cls in [("div", r"\babstract\b"), ("section", r"\babstract\b")]:
            tag = self.soup.find(tag_name, class_=re.compile(cls, re.I))
            if tag:
                text = tag.get_text(separator="\n", strip=True)
                return re.sub(r"^Abstract\s*", "", text, flags=re.IGNORECASE).strip()
        return self._meta(prop="og:description") or self._meta("description")

    def parse_sections(self) -> dict:
        sections = {}

        body = (
            self.soup.find("div", class_=re.compile(r"\bbody\b"))
            or self.soup.find("div", id=re.compile(r"article-body|body"))
            or self.soup.find("article")
            or self.soup.body
        )
        if not body:
            return sections

        for sec in body.find_all("section", recursive=True):
            heading_tag = sec.find(["h2", "h3"])
            if not heading_tag:
                continue
            heading = self._text(heading_tag)
            if not heading or heading.lower() in ["abstract", "highlights"]:
                continue

            # Remove nested subsections before extracting text
            sec_soup = BeautifulSoup(str(sec), "lxml")
            for nested in sec_soup.find_all("section")[1:]:
                nested.decompose()

            text = sec_soup.get_text(separator="\n", strip=True)
            text = text.replace(heading, "", 1).strip()

            if text:
                sections[heading] = text

        return sections or self._fallback_heading_split(body)

    def parse_authors(self) -> list:
        authors = self._meta_all("citation_author")
        if authors:
            return authors
        tags = self.soup.find_all(["span", "a"], class_=re.compile(r"author-name|contrib-author"))
        return [self._text(t) for t in tags if self._text(t)]

    def parse_journal(self) -> str:
        return self._meta("citation_journal_title") or self._meta(prop="og:site_name")

    def parse_date(self) -> str:
        return self._meta("citation_publication_date") or self._meta("citation_online_date")

    def parse_doi(self) -> str:
        doi = self._meta("citation_doi")
        if doi:
            return doi
        tag = self.soup.find("a", href=re.compile(r"doi\.org"))
        return tag["href"].replace("https://doi.org/", "") if tag else ""

    def parse_keywords(self) -> list:
        kw_div = self.soup.find("div", class_=re.compile(r"keyword"))
        if kw_div:
            return [self._text(k) for k in kw_div.find_all(["span", "a", "li"]) if self._text(k)]
        meta = self._meta("keywords")
        return [k.strip() for k in meta.split(",")] if meta else []

    def parse_references(self) -> list:
        ref_section = (
            self.soup.find("section", class_=re.compile(r"reference"))
            or self.soup.find("ul", class_=re.compile(r"reference"))
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
