"""
Tests for the web scraper service.

Covers:
- _strip_html_tags: HTML cleaning, tag removal, whitespace normalization
- fetch_source_content: HTTP fetch with HTML stripping and SHA-256 hashing
- fetch_multiple_sources: batch fetching with mixed success/failure handling
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.web_scraper import (
    _strip_html_tags,
    fetch_multiple_sources,
    fetch_source_content,
)

# ─── _strip_html_tags ───────────────────────────────────────────────


class TestStripHtmlTags:
    """Unit tests for _strip_html_tags helper."""

    def test_strips_script_tags(self):
        html = "<html><body><script>alert('xss')</script><p>Hello</p></body></html>"
        result = _strip_html_tags(html)
        assert "alert" not in result
        assert "Hello" in result

    def test_strips_style_tags(self):
        html = "<html><body><style>body { color: red; }</style><p>Visible</p></body></html>"
        result = _strip_html_tags(html)
        assert "color" not in result
        assert "Visible" in result

    def test_strips_nav_tags(self):
        html = "<html><body><nav><a href='/'>Home</a></nav><p>Content</p></body></html>"
        result = _strip_html_tags(html)
        assert "Home" not in result
        assert "Content" in result

    def test_strips_footer_tags(self):
        html = "<html><body><p>Main</p><footer>Copyright 2025</footer></body></html>"
        result = _strip_html_tags(html)
        assert "Copyright" not in result
        assert "Main" in result

    def test_strips_header_tags(self):
        html = "<html><body><header><h1>Site Title</h1></header><p>Body text</p></body></html>"
        result = _strip_html_tags(html)
        assert "Site Title" not in result
        assert "Body text" in result

    def test_preserves_body_text(self):
        html = """
        <html>
        <body>
            <div>
                <h2>Tax Update</h2>
                <p>The new rate is 5.5%.</p>
                <p>Effective July 1, 2025.</p>
            </div>
        </body>
        </html>
        """
        result = _strip_html_tags(html)
        assert "Tax Update" in result
        assert "The new rate is 5.5%." in result
        assert "Effective July 1, 2025." in result

    def test_handles_nested_tags(self):
        html = (
            "<div><p>Outer <span>inner <strong>bold</strong> text</span> end</p></div>"
        )
        result = _strip_html_tags(html)
        assert "Outer" in result
        assert "inner" in result
        assert "bold" in result
        assert "text" in result
        assert "end" in result
        # No HTML tag remnants
        assert "<" not in result
        assert ">" not in result

    def test_strips_multiple_excluded_tags_at_once(self):
        html = """
        <html>
        <head><style>.x{}</style></head>
        <body>
            <header>Header</header>
            <nav>Nav</nav>
            <script>var x=1;</script>
            <main><p>Real content here</p></main>
            <footer>Footer</footer>
        </body>
        </html>
        """
        result = _strip_html_tags(html)
        assert "Real content here" in result
        assert "Header" not in result
        assert "Nav" not in result
        assert "var x" not in result
        assert "Footer" not in result
        assert ".x{}" not in result

    def test_handles_empty_string(self):
        result = _strip_html_tags("")
        assert result == ""

    def test_handles_minimal_html(self):
        result = _strip_html_tags("<p>Hello</p>")
        assert result.strip() == "Hello"

    def test_handles_plain_text(self):
        result = _strip_html_tags("Just plain text with no tags")
        assert "Just plain text with no tags" in result

    def test_collapses_blank_lines(self):
        html = "<p>Line one</p>\n\n\n\n<p>Line two</p>"
        result = _strip_html_tags(html)
        lines = result.splitlines()
        # No empty lines should remain after stripping
        assert all(line.strip() for line in lines)


# ─── fetch_source_content ────────────────────────────────────────────


class TestFetchSourceContent:
    """Tests for fetch_source_content with mocked httpx."""

    async def test_returns_text_and_hash(self):
        html = "<html><body><p>Tax rate is 10%</p></body></html>"
        expected_text = _strip_html_tags(html)
        expected_hash = hashlib.sha256(expected_text.encode()).hexdigest()

        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.web_scraper.httpx.AsyncClient", return_value=mock_client):
            text, content_hash = await fetch_source_content("https://example.com/tax")

        assert text == expected_text
        assert content_hash == expected_hash
        assert len(content_hash) == 64  # SHA-256 hex digest length
        mock_client.get.assert_called_once_with("https://example.com/tax")
        mock_response.raise_for_status.assert_called_once()

    async def test_strips_html_from_response(self):
        html = """
        <html>
        <body>
            <script>tracking();</script>
            <nav><a>Menu</a></nav>
            <p>Important tax info</p>
            <footer>Copyright</footer>
        </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.web_scraper.httpx.AsyncClient", return_value=mock_client):
            text, _ = await fetch_source_content("https://example.com")

        assert "Important tax info" in text
        assert "tracking" not in text
        assert "Menu" not in text
        assert "Copyright" not in text

    async def test_passes_timeout_to_client(self):
        mock_response = MagicMock()
        mock_response.text = "<p>OK</p>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.web_scraper.httpx.AsyncClient", return_value=mock_client) as mock_cls:
            await fetch_source_content("https://example.com", timeout=15.0)

        mock_cls.assert_called_once_with(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "TaxLens/0.1 (+https://taxlens.io)"},
        )

    async def test_raises_on_timeout(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.web_scraper.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.TimeoutException):
                await fetch_source_content("https://slow.example.com")

    async def test_raises_on_http_4xx_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "404 Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404),
            )
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.web_scraper.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await fetch_source_content("https://example.com/missing")

    async def test_raises_on_http_5xx_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500 Internal Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.web_scraper.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await fetch_source_content("https://example.com/error")


# ─── fetch_multiple_sources ──────────────────────────────────────────


class TestFetchMultipleSources:
    """Tests for fetch_multiple_sources with mocked fetch_source_content."""

    async def test_mixed_success_and_failure(self):
        """Some URLs succeed, some fail -- results are returned for all."""
        url_ok = "https://example.com/ok"
        url_fail = "https://example.com/fail"
        expected_text = "Tax info"
        expected_hash = hashlib.sha256(expected_text.encode()).hexdigest()

        async def _mock_fetch(url, timeout=30.0):
            if url == url_ok:
                return expected_text, expected_hash
            raise httpx.TimeoutException("timed out")

        with patch("app.services.web_scraper.fetch_source_content", side_effect=_mock_fetch):
            results = await fetch_multiple_sources([url_ok, url_fail])

        assert len(results) == 2

        ok_result = results[0]
        assert ok_result["url"] == url_ok
        assert ok_result["text"] == expected_text
        assert ok_result["content_hash"] == expected_hash
        assert ok_result["error"] is None

        fail_result = results[1]
        assert fail_result["url"] == url_fail
        assert fail_result["text"] is None
        assert fail_result["content_hash"] is None
        assert fail_result["error"] is not None
        assert "timed out" in fail_result["error"]

    async def test_all_succeed(self):
        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]

        async def _mock_fetch(url, timeout=30.0):
            text = f"Content for {url}"
            h = hashlib.sha256(text.encode()).hexdigest()
            return text, h

        with patch("app.services.web_scraper.fetch_source_content", side_effect=_mock_fetch):
            results = await fetch_multiple_sources(urls)

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["url"] == urls[i]
            assert result["text"] == f"Content for {urls[i]}"
            assert result["content_hash"] is not None
            assert result["error"] is None

    async def test_all_fail(self):
        urls = [
            "https://bad1.example.com",
            "https://bad2.example.com",
        ]

        async def _mock_fetch(url, timeout=30.0):
            raise httpx.ConnectError(f"Connection refused: {url}")

        with patch("app.services.web_scraper.fetch_source_content", side_effect=_mock_fetch):
            results = await fetch_multiple_sources(urls)

        assert len(results) == 2
        for i, result in enumerate(results):
            assert result["url"] == urls[i]
            assert result["text"] is None
            assert result["content_hash"] is None
            assert result["error"] is not None
            assert "Connection refused" in result["error"]

    async def test_empty_url_list(self):
        results = await fetch_multiple_sources([])
        assert results == []

    async def test_passes_timeout_to_fetch(self):
        async def _mock_fetch(url, timeout=30.0):
            assert timeout == 10.0
            return "text", hashlib.sha256(b"text").hexdigest()

        with patch("app.services.web_scraper.fetch_source_content", side_effect=_mock_fetch):
            results = await fetch_multiple_sources(["https://example.com"], timeout=10.0)

        assert len(results) == 1
        assert results[0]["error"] is None
