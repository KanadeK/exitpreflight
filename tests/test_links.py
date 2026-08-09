from __future__ import annotations

import unittest

from exitpreflight.links import (
    classify_reference,
    extract_references,
    resolve_local_reference,
)


class LinkTests(unittest.TestCase):
    def test_extracts_markdown_html_and_plain_urls(self) -> None:
        markdown = extract_references(
            "docs/page.md",
            "![Image](../asset.png)\n[Cloud](https://drive.google.com/file/d/1)\n",
        )
        self.assertEqual(len(markdown), 2)
        self.assertTrue(markdown[0].is_image)
        html = extract_references("page.html", '<img src="pic.png"><a href="next.html">Next</a>')
        self.assertEqual({item.target for item in html}, {"pic.png", "next.html"})

    def test_classifies_cloud_signed_external_and_ignored(self) -> None:
        self.assertEqual(classify_reference("https://drive.google.com/file/d/1"), "cloud")
        self.assertEqual(
            classify_reference("https://cdn.example.test/file?X-Amz-Signature=abc"), "signed"
        )
        self.assertEqual(classify_reference("https://example.com"), "external")
        self.assertEqual(classify_reference("mailto:test@example.com"), "ignored")
        self.assertEqual(classify_reference("asset.png"), "local")

    def test_resolves_relative_and_root_paths(self) -> None:
        self.assertEqual(resolve_local_reference("docs/page.md", "../asset.png"), "asset.png")
        self.assertEqual(
            resolve_local_reference("docs/page.md", "/assets/a%20b.png"), "assets/a b.png"
        )


if __name__ == "__main__":
    unittest.main()
