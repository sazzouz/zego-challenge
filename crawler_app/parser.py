import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from typeguard import typechecked

from .constants import SUPPORTED_PROTOCOLS
from .utils import normalize_url

logger = logging.getLogger(__name__)


@typechecked
def extract_links(html_content: str, base_url: str) -> set[str]:
    """
    Extract all valid links from HTML content and normalize them.

    This function parses HTML content, extracts all anchor tags with href attributes,
    filters out invalid URLs (like JavaScript links, fragments, or excluded schemes),
    and normalizes the remaining URLs to ensure they are absolute and properly formatted.

    Args:
        html_content: The HTML content to parse
        base_url: The base URL of the page (used to resolve relative URLs)

    Returns:
        A set of normalized absolute URLs found in the HTML

    Example:
        ```python
        html = "<html><body><a href='/page1'>Page 1</a><a href='https://example.com'>External</a></body></html>"
        links = extract_links(html, "https://mysite.com")
        # Returns: {'https://mysite.com/page1', 'https://example.com'}
        ```
    """
    if not html_content:
        logger.debug("Empty HTML content provided, returning empty set")
        return set()

    try:
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        links = set()

        # Find all anchor tags with href attributes and process them
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()

            # Skip empty links, fragments, and javascript: links
            if not href or href.startswith(("#", "javascript:")):
                continue

            # Skip URLs with unsupported schemes
            parsed_href = urlparse(href)
            if parsed_href.scheme and parsed_href.scheme.lower() not in SUPPORTED_PROTOCOLS:
                logger.debug(f"Skipping URL with unsupported scheme: {href}")
                continue

            # Normalize the URL using our utility function
            normalized_url = normalize_url(href, base_url)
            if normalized_url:
                # Ensure we only have supported protocol URLs after normalization
                parsed_normalized = urlparse(normalized_url)
                if parsed_normalized.scheme in SUPPORTED_PROTOCOLS:
                    links.add(normalized_url)
                else:
                    logger.debug(f"Skipping URL with unsupported scheme after normalization: {normalized_url}")

        return links

    except Exception as e:
        logger.error(f"Error extracting links from HTML for {base_url}: {str(e)}")
        return set()
