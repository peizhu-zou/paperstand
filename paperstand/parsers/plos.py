"""
parsers/plos.py
Parser for PLOS journals (plos.org).
Covers: PLOS ONE, PLOS Biology, PLOS Medicine, PLOS Genetics,
        PLOS Computational Biology, PLOS Pathogens, etc.

PLOS is fully open access and does NOT block scraping — HTML
can be fetched directly without browser-saving.

Verified structure:
  Title:    <meta name="citation_title">
            fallback: <h1 id="artTitle">
  Abstract: <div class="abstract-content">
            or <div id="abstract0">
  Body:     <div id="artText"> or <div class="article-text">
              └── <div class="section"> with <h2>/<h3>
                    or <section> tags
  Authors:  <meta name="citation_author"> (multiple)
            fallback: <span class="author-name">
  Keywords: <div class="kwd-group"> or <meta name="keywords">
  Refs:     <ol class="references"> or <div id="references">
  Data:     <div class="data-availability"> — PLOS requires this
  Metadata: <meta name="citation_*">
"""

import re
from bs4 import BeautifulSoup
from .base import BaseParser


class PLOSParser(BaseParser):

    def parse_title(self) -> str:
        title = self._meta("citation_title")
        if title:
            return title
        tag = self.soup.find("h1", id="artTitle") or self.soup.find("h1")
        return self._text(tag)

    def parse_abstract(self) -> str:
        # PLOS: <div class="abstract-content"> inside <div id="abstract0">
        tag = (
            self.soup.find("div", class_=re.compile(r"abstract-content"))
            or self.soup.find("div", id=re.compile(r"^abstract"))
            or self.soup.find("div", class_=re.compile(r"\babstract\b", re.I))
        )
        if tag:
            text = tag.get_text(separator="\n", strip=True)
            return re.sub(r"^Abstract\s*", "", text, flags=re.IGNORECASE).strip()
        return self._meta(prop="og:description") or self._meta("description")

    def parse_sections(self) -> dict:
        sections = {}

        body = (
            self.soup.find("div", id="artText")
            or self.soup.find("div", class_=re.compile(r"article-text|article-body"))
            or self.soup.find("article")
            or self.soup.body
        )
        if not body:
            return sections

        # PLOS uses <div class="section"> with <h2> or <h3>
        sec_tags = body.find_all("div", class_=re.compile(r"\bsection\b"))
        if not sec_tags:
            sec_tags = body.find_all("section", recursive=True)

        for sec in sec_tags:
            heading_tag = sec.find(["h2", "h3"])
            if not heading_tag:
                continue
            heading = self._text(heading_tag)
            if not heading or heading.lower() in ["abstract"]:
                continue

            sec_soup = BeautifulSoup(str(sec), "lxml")
            # Remove nested sections to avoid duplication
            for nested in sec_soup.find_all("div", class_=re.compile(r"\bsection\b"))[1:]:
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
        tags = self.soup.find_all(["span", "a"], class_=re.compile(r"author-name|contrib"))
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
        # PLOS: <div class="kwd-group"> with <a> or <span> tags
        kw_div = self.soup.find("div", class_=re.compile(r"kwd-group|keyword"))
        if kw_div:
            return [self._text(k) for k in kw_div.find_all(["a", "span", "li"]) if self._text(k)]
        meta = self._meta("keywords")
        return [k.strip() for k in meta.split(",")] if meta else []

    def parse_references(self) -> list:
        ref_section = (
            self.soup.find("ol",  class_=re.compile(r"reference"))
            or self.soup.find("div", id="references")
            or self.soup.find("div", class_=re.compile(r"reference"))
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
