import hashlib
import logging
import re

import httpx

logger = logging.getLogger(__name__)


def _strip_html_tags(html: str) -> str:
    """Extract readable text from HTML, stripping tags and excess whitespace."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
    except ImportError:
        text = re.sub(r"<[^>]+>", " ", html)

    lines = (line.strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


async def fetch_source_content(
    url: str,
    timeout: float = 30.0,
) -> tuple[str, str]:
    """Fetch URL content and return (text_content, content_hash).

    Raises httpx.HTTPError on network / HTTP failures.
    """
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "TaxLens/0.1 (+https://taxlens.io)"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        text = _strip_html_tags(response.text)
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        return text, content_hash


async def fetch_multiple_sources(
    urls: list[str],
    timeout: float = 30.0,
) -> list[dict]:
    """Fetch multiple URLs, returning results for each (including errors).

    Returns a list of dicts: {url, text, content_hash, error}
    """
    results = []
    for url in urls:
        try:
            text, content_hash = await fetch_source_content(url, timeout=timeout)
            results.append({
                "url": url,
                "text": text,
                "content_hash": content_hash,
                "error": None,
            })
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            results.append({
                "url": url,
                "text": None,
                "content_hash": None,
                "error": str(e),
            })
    return results
