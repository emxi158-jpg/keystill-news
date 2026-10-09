from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import update_news as news

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


def rss(title, link, date="Thu, 08 Oct 2026 18:00:00 GMT"):
    return f"""<rss><channel><item><title>{title}</title><link>{link}</link>
    <pubDate>{date}</pubDate><description><![CDATA[<p>A recent report describes how
    communities are responding to changes in their local institutions, and explains
    why the issue matters to readers around the world.</p><script>ignored</script>]]></description>
    </item></channel></rss>""".encode()


class UpdaterTests(unittest.TestCase):
    def request(self, url):
        for index, (_, _, source_url) in enumerate(news.SOURCES):
            if url == source_url:
                return rss(f"Recent news topic {index}", f"https://example.com/story/{index}")
        raise AssertionError("Unexpected external request")

    def test_three_categories_with_real_dates_links_and_translation_labels(self):
        package = news.make_package(NOW, self.request, lambda text: "这是一段测试译文。")
        self.assertEqual([item["category"] for item in package["items"]], ["世界热点", "文化", "艺术"])
        self.assertEqual(len({item["url"] for item in package["items"]}), 3)
        self.assertTrue(all(item["date"] == "2026-10-09" for item in package["items"]))
        self.assertTrue(all("机器翻译" in item["translation"] for item in package["items"]))
        for category, source, _ in news.SOURCES:
            candidate = news.parse_feed(self.request(news.SOURCES[0][2]), category, source, NOW)[0]
            self.assertLessEqual(len(candidate["title_en"].split()) + len(candidate["en"].split()), 25)
            self.assertNotIn("ignored", candidate["en"])

    def test_stale_future_or_unsafe_entries_are_not_used(self):
        for date in ["Thu, 01 Jan 2026 00:00:00 GMT", "Thu, 31 Dec 2026 00:00:00 GMT", "invalid"]:
            self.assertEqual(news.parse_feed(rss("News", "https://example.com/x", date), "文化", "Test", NOW), [])
        self.assertEqual(news.parse_feed(rss("News", "javascript:alert(1)"), "文化", "Test", NOW), [])

    def test_duplicate_links_or_missing_category_fail_complete_batch(self):
        with self.assertRaises(ValueError):
            news.make_package(NOW, lambda url: rss("News", "https://example.com/same"), lambda t: "译文")
        with self.assertRaises(ValueError):
            news.make_package(NOW, lambda url: b"<rss><channel/></rss>", lambda t: "译文")

    def test_translation_limit_and_failure_are_not_published_as_news(self):
        translator = news.Translator(lambda url: json.dumps({"responseStatus": 429, "responseData": {"translatedText": "QUOTA"}}).encode())
        with self.assertRaises(ValueError):
            translator("A short story")
        with self.assertRaises(ValueError):
            translator("a" * 501)
        with self.assertRaises(ValueError):
            news.make_package(NOW, self.request, translator)

    def test_repeated_batch_preserves_timestamp_and_atomic_failure_preserves_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "news.json"
            package = news.make_package(NOW, self.request, lambda text: "测试译文")
            self.assertTrue(news.write_package(path, package))
            original = path.read_bytes()
            package["generatedAt"] = (NOW + timedelta(days=1)).isoformat()
            self.assertFalse(news.write_package(path, package))
            self.assertEqual(path.read_bytes(), original)
            with patch("sys.argv", ["update_news.py", "--output", str(path)]), patch("update_news.make_package", side_effect=ValueError("source offline")):
                self.assertEqual(news.main(), 1)
            self.assertEqual(path.read_bytes(), original)

    def test_xml_entities_are_refused(self):
        with self.assertRaises(ValueError):
            news.parse_feed(b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss/>', "文化", "Test", NOW)


if __name__ == "__main__":
    unittest.main()
