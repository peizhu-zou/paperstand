"""
parsers/nature.py
Parser for Nature portfolio journals (nature.com).
Covers: Nature, Nature Communications, Nature Methods,
        Nature Genetics, Nature Medicine, etc.

Verified structure (inspected live HTML):
  Title:    <meta name="citation_title"> (most reliable)
            fallback: <h1 class="c-article-title">
  Abstract: <section data-title="Abstract">
              └── <div id="Abs1-content">
  Body:     <div class="c-article-body"> or <article>
              └── <section data-title="Introduction"> etc.
                    └── <div class="c-article-section__content">
  Authors:  <meta name="citation_author"> (multiple)
            fallback: <li class="c-author-list__item">
  Keywords: <ul class="c-article-subject-list">
  Refs:     <ol class="c-article-references">
  Metadata: <meta name="citation_*"> (reliable)

Note: Nature blocks server-side scraping. HTML must be saved
      from browser (Cmd+S / Ctrl+S) and loaded via --html-dir.
"""

import re
from .base import BaseParser


class NatureParser(BaseParser):

    def parse_title(self) -> str:
        title = self._meta("citation_title")
        if title:
            return title
        tag = self.soup.find("h1", class_=re.compile(r"c-article-title|article-title"))
        return self._text(tag) if tag else self._text(self.soup.find("h1"))

    def parse_abstract(self) -> str:
        # Primary: <section data-title="Abstract">
        sec = self.soup.find("section", attrs={"data-title": re.compile(r"^abstract$", re.I)})
        if sec:
            content = sec.find("div", id=re.compile(r"Abs\d+-content"))
            return self._text(content) if content else self._text(sec)

        # Fallback: any div with "abstract" in class
        for tag in self.soup.find_all("div", class_=re.compile(r"\babstract\b", re.I)):
            text = self._text(tag)
            if text:
                return text

        return self._meta(prop="og:description") or self._meta("description")

    def parse_sections(self) -> dict:
        sections = {}

        body = (
            self.soup.find("div", class_=re.compile(r"c-article-body"))
            or self.soup.find("article")
            or self.soup.body
        )
        if not body:
            return sections

        # Nature uses <section data-title="Introduction"> etc.
        for sec in body.find_all("section", attrs={"data-title": True}):
            heading = sec.get("data-title", "").strip()
            if not heading or heading.lower() == "abstract":
                continue

            content_div = sec.find("div", class_=re.compile(r"c-article-section__content"))
            text = self._text(content_div) if content_div else self._text(sec)

            # Remove the heading text from the start if present
            if text.startswith(heading):
                text = text[len(heading):].strip()

            if text:
                sections[heading] = text

        return sections or self._fallback_heading_split(body)

    def parse_authors(self) -> list:
        authors = self._meta_all("citation_author")
        if authors:
            return authors
        items = self.soup.find_all("li", class_=re.compile(r"c-author-list__item"))
        result = []
        for item in items:
            name_tag = item.find(["a", "span"], class_=re.compile(r"author-name|c-author"))
            name = self._text(name_tag)
            if name:
                result.append(name)
        return result

    def parse_journal(self) -> str:
        journal = self._meta("citation_journal_title")
        if journal:
            return journal
        return self._meta(prop="og:site_name")

    def parse_date(self) -> str:
        date = self._meta("citation_publication_date") or self._meta("citation_online_date")
        if date:
            return date
        tag = self.soup.find("time", attrs={"datetime": True})
        return tag.get("datetime", "") if tag else ""

    def parse_doi(self) -> str:
        doi = self._meta("citation_doi")
        if doi:
            return doi
        tag = self.soup.find("a", attrs={"data-track-action": "view doi"})
        if tag:
            return self._text(tag).replace("https://doi.org/", "")
        tag = self.soup.find("a", href=re.compile(r"doi\.org"))
        return tag["href"].replace("https://doi.org/", "") if tag else ""

    def parse_keywords(self) -> list:
        # Nature calls them "Subjects"
        kw_list = self.soup.find("ul", class_=re.compile(r"c-article-subject"))
        if kw_list:
            return [self._text(a) for a in kw_list.find_all("a") if self._text(a)]
        sec = self.soup.find("section", attrs={"data-title": re.compile(r"subject", re.I)})
        if sec:
            return [self._text(a) for a in sec.find_all("a") if self._text(a)]
        meta = self._meta("keywords")
        return [k.strip() for k in meta.split(",")] if meta else []

    def parse_references(self) -> list:
        ref_list = self.soup.find("ol", class_=re.compile(r"c-article-references|references"))
        if ref_list:
            return [
                li.get_text(separator=" ", strip=True)
                for li in ref_list.find_all("li")
                if li.get_text(strip=True)
            ]
        # Fallback: references section
        sec = self.soup.find("section", attrs={"data-title": re.compile(r"reference", re.I)})
        if sec:
            return [
                li.get_text(separator=" ", strip=True)
                for li in sec.find_all("li")
                if li.get_text(strip=True)
            ]
        return []

    def parse_figures(self) -> list:
        return self._figures()

    def parse_tables(self) -> list:
        return self._tables()
