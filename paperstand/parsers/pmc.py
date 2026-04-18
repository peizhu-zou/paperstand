"""
parsers/pmc.py
Parser for PubMed Central (pmc.ncbi.nlm.nih.gov).

Verified structure (inspected live HTML):
  Title:    <meta name="citation_title"> or plain <h1>
  Abstract: <section class="abstract"> → strip "Abstract" heading
  Body:     <section class="body main-article-body">
              └── <section id="sec...">
                    └── <h2 class="pmc_sec_title"> or <h3 class="pmc_sec_title">
  Metadata: <meta name="citation_*"> tags (reliable)
"""

import re
from bs4 import BeautifulSoup
from .base import BaseParser


class PMCParser(BaseParser):

    def parse_title(self) -> str:
        title = self._meta("citation_title")
        if title:
            return title
        return self._text(self.soup.find("h1"))

    def parse_abstract(self) -> str:
        tag = self.soup.find("section", class_="abstract")
        if tag:
            text = tag.get_text(separator="\n", strip=True)
            return re.sub(r"^Abstract\s*", "", text, flags=re.IGNORECASE).strip()
        for sel in ["div.abstract", "#abstract"]:
            tag = self.soup.select_one(sel)
            if tag:
                return tag.get_text(separator="\n", strip=True)
        return self._meta(prop="og:description") or self._meta("description")

    def parse_sections(self) -> dict:
        sections = {}

        body = (
            self.soup.find("section", class_=re.compile(r"main-article-body"))
            or self.soup.find("main", id="main-content")
            or self.soup.find("div", class_="pmc-wm")
            or self.soup.find("article")
            or self.soup.body
        )
        if not body:
            return sections

        for sec in body.find_all("section", recursive=True):
            heading_tag = (
                sec.find(["h2", "h3"], class_="pmc_sec_title")
                or sec.find(["h2", "h3", "h4"])
            )
            if not heading_tag:
                continue
            heading = self._text(heading_tag)
            if not heading or heading.lower() == "abstract":
                continue

            # Re-parse section to safely remove nested subsections
            sec_soup = BeautifulSoup(str(sec), "lxml")
            for nested in sec_soup.find_all("section")[1:]:
                nested.decompose()
            for obj in sec_soup.find_all(class_="obj_head"):
                obj.decompose()

            text = sec_soup.get_text(separator="\n", strip=True)
            text = text.replace(heading, "", 1).strip()

            if text:
                sections[heading] = text

        return sections or self._fallback_heading_split(body)

    def parse_authors(self) -> list:
        return self._meta_all("citation_author")

    def parse_journal(self) -> str:
        return self._meta("citation_journal_title")

    def parse_date(self) -> str:
        return self._meta("citation_publication_date") or self._meta("citation_date")

    def parse_doi(self) -> str:
        doi = self._meta("citation_doi")
        if doi:
            return doi
        tag = self.soup.find("a", href=re.compile(r"doi\.org"))
        return tag["href"].replace("https://doi.org/", "") if tag else ""

    def parse_keywords(self) -> list:
        kw = self.soup.find(["div", "section"], class_=re.compile(r"keyword"))
        if kw:
            return [self._text(t) for t in kw.find_all(["span", "li", "a"]) if self._text(t)]
        meta = self._meta("keywords")
        return [k.strip() for k in meta.split(",")] if meta else []

    def parse_references(self) -> list:
        ref_section = (
            self.soup.find(["ol", "ul"], class_=re.compile(r"ref"))
            or self.soup.find("div", class_=re.compile(r"ref"))
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
