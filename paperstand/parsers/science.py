"""
parsers/science.py
Parser for Science family journals (science.org / AAAS).
Covers: Science, Science Advances, Science Translational Medicine,
        Science Immunology, Science Signaling, etc.

Structure:
  Title:    <meta name="citation_title">
            fallback: <h1 class="article__title">
  Abstract: <div class="article-abstract"> or <section class="abstract">
  Body:     <div class="article__body"> or <main>
              └── <section> or <div role="doc-section"> with <h2>/<h3>
  Authors:  <meta name="citation_author">
            fallback: <span class="al-author-name">
  Keywords: <meta name="keywords"> or subject tags
  Refs:     <div class="ref-list"> or <section class="references">
  Metadata: <meta name="citation_*">

Note: Science blocks server-side scraping. HTML must be saved
      from browser and loaded via --html-dir.
"""

import re
from bs4 import BeautifulSoup
from .base import BaseParser


class ScienceParser(BaseParser):

    def parse_title(self) -> str:
        title = self._meta("citation_title")
        if title:
            return title
        tag = self.soup.find("h1", class_=re.compile(r"article__title|article-title"))
        return self._text(tag) if tag else self._text(self.soup.find("h1"))

    def parse_abstract(self) -> str:
        for tag_name, cls in [
            ("div",     r"article-abstract|article__abstract"),
            ("section", r"\babstract\b"),
            ("div",     r"\babstract\b"),
        ]:
            tag = self.soup.find(tag_name, class_=re.compile(cls, re.I))
            if tag:
                text = tag.get_text(separator="\n", strip=True)
                return re.sub(r"^Abstract\s*", "", text, flags=re.IGNORECASE).strip()
        return self._meta(prop="og:description") or self._meta("description")

    def parse_sections(self) -> dict:
        sections = {}

        body = (
            self.soup.find("div", class_=re.compile(r"article__body|article-body"))
            or self.soup.find("main")
            or self.soup.find("article")
            or self.soup.body
        )
        if not body:
            return sections

        # Science uses <section> or <div role="doc-section">
        sec_tags = body.find_all("section", recursive=True)
        if not sec_tags:
            sec_tags = body.find_all("div", attrs={"role": "doc-section"})

        for sec in sec_tags:
            heading_tag = sec.find(["h2", "h3"])
            if not heading_tag:
                continue
            heading = self._text(heading_tag)
            if not heading or heading.lower() == "abstract":
                continue

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
        tags = self.soup.find_all(["span", "a"], class_=re.compile(r"author-name|al-author"))
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
        meta = self._meta("keywords")
        if meta:
            return [k.strip() for k in meta.split(",")]
        kw_div = self.soup.find(["div", "section"], class_=re.compile(r"keyword|subject"))
        if kw_div:
            return [self._text(k) for k in kw_div.find_all(["span", "a", "li"]) if self._text(k)]
        return []

    def parse_references(self) -> list:
        ref_section = (
            self.soup.find("section", class_=re.compile(r"reference"))
            or self.soup.find("div",     class_=re.compile(r"ref-list"))
            or self.soup.find("ol",      class_=re.compile(r"reference"))
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
