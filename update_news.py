"""Prepare three short bilingual RSS briefs without AI keys or paid services."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SOURCES = (
    ("世界热点", "BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("文化", "The Guardian · Culture", "https://www.theguardian.com/culture/rss"),
    ("艺术", "The Guardian · Art and design", "https://www.theguardian.com/artanddesign/rss"),
)
MAX_BYTES = 2_000_000
MAX_TRANSLATION_CHARS = 1400
TZ = timezone(timedelta(hours=8))


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignore += 1
        elif tag in ("p", "br", "div"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.ignore = max(0, self.ignore - 1)
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.ignore:
            self.parts.append(data)


def plain(value):
    parser = PlainText()
    parser.feed(value or "")
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


def get(url):
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError("HTTPS required")
    request = urllib.request.Request(url, headers={"User-Agent": "Keystill-News/1.0 (weekly RSS brief reader)"})
    with urllib.request.urlopen(request, timeout=15) as response:
        if urllib.parse.urlparse(response.url).scheme != "https":
            raise ValueError("Insecure redirect refused")
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Response too large")
    return data


def parse_feed(data, category, source, now):
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("RSS with external entities refused")
    root = ET.fromstring(data)
    candidates = []
    for entry in root.findall("./channel/item"):
        title = plain(entry.findtext("title"))
        summary = plain(entry.findtext("description"))
        url = (entry.findtext("link") or "").strip()
        try:
            date = parsedate_to_datetime(entry.findtext("pubDate") or "")
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            date = date.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
        if not title or not summary or not url.startswith("https://"):
            continue
        if date > now + timedelta(hours=1) or now - date > timedelta(days=31):
            continue
        # Publish short RSS excerpts only, never article bodies. The title and
        # excerpt together contain no more than 25 source words.
        title = " ".join(title.split()[:15])[:100]
        budget = max(5, 25 - len(title.split()))
        words = summary.split()
        excerpt = " ".join(words[:budget])
        if len(words) > budget:
            excerpt = excerpt.rstrip(".,;:") + "…"
        if not excerpt:
            continue
        candidates.append({"title_en": title, "en": excerpt, "category": category,
                           "source": source, "url": url, "published": date,
                           "date": date.astimezone(TZ).date().isoformat()})
    return sorted(candidates, key=lambda item: item["published"], reverse=True)


class Translator:
    def __init__(self, request=get):
        self.request = request
        self.used = 0
        self.cache = {}

    def __call__(self, text):
        if text in self.cache:
            return self.cache[text]
        if len(text.encode("utf-8")) > 500:
            raise ValueError("Translation segment exceeds 500 bytes")
        self.used += len(text)
        if self.used > MAX_TRANSLATION_CHARS:
            raise ValueError("Weekly translation request cap reached")
        query = urllib.parse.urlencode({"q": text, "langpair": "en|zh-CN"})
        response = json.loads(self.request("https://api.mymemory.translated.net/get?" + query))
        translated = plain(unescape(response.get("responseData", {}).get("translatedText", "")))
        if str(response.get("responseStatus")) != "200" or response.get("quotaFinished") or not translated:
            raise ValueError("Free translation unavailable; previous news retained")
        if not re.search(r"[\u3400-\u9fff]", translated):
            raise ValueError("Chinese translation missing; previous news retained")
        self.cache[text] = translated
        return translated


def make_package(now=None, request=get, translate=None, previous=None):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    translate = translate or Translator(request)
    selected, seen = [], set()
    for category, source, url in SOURCES:
        candidates = parse_feed(request(url), category, source, now)
        candidate = next((item for item in candidates if item["url"] not in seen), None)
        if candidate is None:
            raise ValueError(f"No recent item for {category}; previous news retained")
        seen.add(candidate["url"])
        selected.append(candidate)
    items = []
    old_items = {item.get('url'): item for item in (previous or {}).get('items', [])
                 if isinstance(item, dict) and all(item.get(key) for key in ('id', 'title', 'zh', 'en', 'date', 'source'))}
    for item in selected:
        old = old_items.get(item['url'])
        if old and old.get('category') == item['category'] and old.get('date') == item['date'] and old.get('en') == item['en']:
            items.append(old)
            continue
        title_zh, summary_zh = translate(item["title_en"]), translate(item["en"])
        items.append({"id": "weekly-" + hashlib.sha256(item["url"].encode()).hexdigest()[:18],
                      "title": title_zh[:100], "category": item["category"],
                      "date": item["date"], "source": item["source"], "url": item["url"],
                      "original": "en", "en": item["en"], "zh": summary_zh,
                      "translation": "机器翻译 · MyMemory", "format": "RSS 短摘要"})
    return {"version": 1, "generatedAt": now.isoformat().replace("+00:00", "Z"),
            "frequency": "weekly", "translation": "机器翻译 · MyMemory", "items": items}


def write_package(path, package):
    # Replace only after all three categories and their translations succeed.
    # Repeated runs without new source URLs leave the previous file untouched.
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            if previous.get("items") == package["items"]:
                return False
        except (ValueError, OSError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="news.json")
    args = parser.parse_args()
    try:
        path = Path(args.output)
        previous = None
        if path.exists():
            try:
                previous = json.loads(path.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                pass
        package = make_package(previous=previous)
        changed = write_package(Path(args.output), package)
        print("Prepared three bilingual briefs." if changed else "No new source items; previous package retained.")
    except Exception as error:
        print(f"Update stopped; previous package retained: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
