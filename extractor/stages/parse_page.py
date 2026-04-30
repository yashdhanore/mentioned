from __future__ import annotations

import html
import re
from html.parser import HTMLParser


TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
INSTAGRAM_QUOTED_CAPTION_PATTERN = re.compile(r':\s*"(?P<caption>.*)"\s*$', re.DOTALL)
GENERIC_TEXT_VALUES = {"instagram", "instagram reel", "instagram post", "instagram photo"}


def _clean_value(value: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", value).strip())


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.metadata: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        attr_map = {key.lower(): value for key, value in attrs if value}
        if tag_name == "link" and attr_map.get("rel", "").lower() == "canonical":
            href = attr_map.get("href")
            if href:
                self.metadata.setdefault("canonical_page_url", _clean_value(href))
            return
        if tag_name != "meta":
            return
        content = attr_map.get("content")
        if not content:
            return
        property_name = attr_map.get("property", "").lower()
        field_name = attr_map.get("name", "").lower()
        cleaned_content = _clean_value(content)
        if property_name == "og:title":
            self.metadata.setdefault("og_title", cleaned_content)
        elif property_name == "og:description":
            self.metadata.setdefault("og_description", cleaned_content)
        elif property_name == "og:image":
            self.metadata.setdefault("og_image", cleaned_content)
        elif property_name == "og:url":
            self.metadata.setdefault("canonical_page_url", cleaned_content)
        elif field_name == "description":
            self.metadata.setdefault("description", cleaned_content)
        elif field_name in {"author", "creator"}:
            self.metadata.setdefault("creator", cleaned_content)


def _extract_caption_text(metadata: dict[str, str]) -> str | None:
    for key in ("og_description", "description"):
        value = metadata.get(key)
        if not value:
            continue
        match = INSTAGRAM_QUOTED_CAPTION_PATTERN.search(value)
        if match:
            return _clean_value(match.group("caption"))
        if value.lower() not in {"instagram", "instagram photo", "instagram reel"}:
            return value
    return None


def parse_page_metadata(html_text: str) -> dict:
    parser = MetadataParser()
    parser.feed(html_text)
    metadata = dict(parser.metadata)
    title_match = TITLE_PATTERN.search(html_text)
    if title_match:
        metadata.setdefault("title", _clean_value(title_match.group(1)))
    caption_text = _extract_caption_text(metadata)
    if caption_text:
        metadata.setdefault("caption_text", caption_text)
    return metadata


def combine_text_fields(metadata: dict) -> str:
    values = [
        metadata.get("title"),
        metadata.get("og_title"),
        metadata.get("description"),
        metadata.get("og_description"),
    ]
    return "\n".join(value for value in values if value and value.casefold() not in GENERIC_TEXT_VALUES)
