"""
Tests for the HTML parser module in the crawler application.

This module tests the extract_links function, which is responsible for:
- Extracting URLs from HTML content
- Resolving relative URLs to absolute URLs
- Filtering URLs based on protocol
- Handling special cases like fragments, invalid links, and malformed HTML

The parser is a critical component in the crawler's ability to discover new
URLs to visit while avoiding problematic links and respecting protocol constraints.
"""

from typing import Any

import pytest

from crawler_app.constants import SUPPORTED_PROTOCOLS
from crawler_app.parser import extract_links


@pytest.mark.parametrize(
    "html_content, base_url, expected_links",
    [
        ("", "http://example.com", set()),  # Empty HTML
        ("<html><body><p>No links here</p></body></html>", "http://example.com", set()),  # No links
    ],
)
def test_extract_links_empty_or_no_links(html_content: str, base_url: str, expected_links: set[str]) -> None:
    """
    Test that extract_links properly handles empty HTML content or HTML with no links.

    Args:
        html_content: HTML content to parse (empty or containing no links)
        base_url: Base URL for resolving relative links
        expected_links: Expected set of links (should be empty)
    """
    links = extract_links(html_content, base_url)
    assert links == expected_links


@pytest.mark.parametrize(
    "html_key, base_url, expected_links",
    [
        (
            "basic",
            "http://example.com",
            {"http://example.com/page1.html", "http://example.com/page2.html", "http://example.com/page3.html"},
        ),
        ("with_fragments", "http://example.com", {"http://example.com/page1.html"}),
        ("with_invalid_links", "http://example.com", set()),
        (
            "with_external_links",
            "http://example.com",
            {"http://example.com/internal.html", "http://external.com/page.html", "http://sub.example.com/page.html"},
        ),
        ("with_special_urls", "http://example.com", {"http://example.com/page1.html"}),
    ],
)
def test_extract_links(
    sample_html_content: dict[str, str], html_key: str, base_url: str, expected_links: set[str]
) -> None:
    """
    Test link extraction functionality with various HTML documents.

    This parameterized test verifies that the extract_links function correctly:
    - Extracts links from anchor tags
    - Resolves relative URLs to absolute URLs
    - Returns a set of normalized links
    - Handles different scenarios such as fragments, invalid links, external links, and special URLs
    """
    html = sample_html_content[html_key]

    links = extract_links(html, base_url)

    assert links == expected_links


@pytest.mark.parametrize(
    "html_key, base_url, expected_result",
    [
        ("with_fragments", "http://example.com", {"http://example.com/page1.html"}),  # URL fragments should be removed
        ("with_invalid_links", "http://example.com", set()),  # Invalid links should be skipped
        (
            "with_external_links",
            "http://example.com",
            {
                "http://example.com/internal.html",
                "http://external.com/page.html",
                "http://sub.example.com/page.html",
            },
        ),  # External domains should be included by the parser
        (
            "with_special_urls",
            "http://example.com",
            {"http://example.com/page1.html"},
        ),  # Special URLs should be filtered out
    ],
)
def test_extract_links_filtering(
    sample_html_content: dict[str, str], html_key: str, base_url: str, expected_result: set[str]
) -> None:
    """
    Test URL filtering behavior in the extract_links function.

    This parameterized test verifies various filtering scenarios:
    - Fragment removal (#section)
    - Invalid URL filtering (javascript:, empty)
    - External domain inclusion (parser shouldn't filter by domain)
    - Special URL scheme filtering (mailto:, tel:, ftp:)

    Args:
        sample_html_content: Fixture providing sample HTML content
        html_key: Key to access specific HTML content from the fixture
        base_url: Base URL for resolving relative links
        expected_result: Expected set of extracted links
    """
    html = sample_html_content[html_key]
    links = extract_links(html, base_url)
    assert links == expected_result


@pytest.mark.parametrize(
    "html_key, base_url, expected_links",
    [
        ("malformed", "http://example.com", {"http://example.com/page1.html", "http://example.com/page2.html"}),
    ],
)
def test_extract_links_malformed_html(
    sample_html_content: dict[str, str], html_key: str, base_url: str, expected_links: set[str]
) -> None:
    """
    Test link extraction from malformed HTML with unclosed tags.

    This test verifies that the extract_links function correctly handles
    malformed HTML using BeautifulSoup's error recovery capabilities.
    """
    html = sample_html_content[html_key]
    links = extract_links(html, base_url)
    assert links == expected_links


@pytest.mark.parametrize(
    "html_content",
    [
        "<html><head>Invalid & HTML",
        "",  # Empty string instead of None
        "<a href='javascript:void(0)'>Invalid</a>",  # JavaScript links
    ],
)
def test_extract_links_handles_errors(html_content: str) -> None:
    """
    Test that extract_links gracefully handles parsing errors.

    This test verifies that the function returns an empty set or properly handles:
    - Severely malformed HTML that might cause BeautifulSoup to raise exceptions
    - Empty string content
    - JavaScript links that should be filtered out

    Args:
        html_content: Invalid or problematic HTML content
    """
    base_url = "http://example.com"
    links = extract_links(html_content, base_url)
    assert links == set()  # Should return an empty set on error or for filtered content


@pytest.mark.parametrize(
    "base_url, html_key, expected_url",
    [
        ("http://example.com", "basic", "http://example.com/page1.html"),
        ("http://example.com/path/", "basic", "http://example.com/path/page1.html"),
        ("https://example.com", "basic", "https://example.com/page1.html"),
    ],
)
def test_extract_links_url_resolution(
    sample_html_content: dict[str, str], base_url: str, html_key: str, expected_url: str
) -> None:
    """
    Test URL resolution with different base URLs.

    This test verifies that relative URLs are correctly resolved against different base URLs:
    - Standard domain without path
    - Domain with path (where relative links should be resolved against the path)
    - Different protocols (http vs https)

    Args:
        sample_html_content: Fixture providing sample HTML content
        base_url: Base URL for resolving relative links
        html_key: Key to access specific HTML content from the fixture
        expected_url: Expected resolved URL for the first link
    """
    html = sample_html_content[html_key]
    links = extract_links(html, base_url)
    assert expected_url in links


@pytest.mark.parametrize(
    "scheme",
    ["mailto:", "tel:", "ftp:"],
)
def test_extract_links_unsupported_protocols(scheme: str, sample_html_content: dict[str, str]) -> None:
    """
    Test handling of unsupported protocols.

    This test verifies that links with protocols not in SUPPORTED_PROTOCOLS are filtered out.
    """
    links = extract_links(sample_html_content["with_special_urls"], "http://example.com")

    # Should only include the HTTP link (in SUPPORTED_PROTOCOLS)
    assert len(links) == 1
    assert "http://example.com/page1.html" in links

    # This should be filtered out as it's not in SUPPORTED_PROTOCOLS
    assert not any(link.startswith(scheme) for link in links)


@pytest.mark.parametrize(
    "page_url, html_content, expected_page_links",
    [
        ("http://example.com", "basic", "http://example.com/page1.html"),
        ("http://example.com/page1.html", "with_external_links", "http://example.com/page2.html"),
        ("http://example.com/page2.html", "with_fragments", "http://example.com/page3.html"),
        ("http://example.com/page3.html", "no_links", None),
    ],
)
def test_extract_links_across_different_pages(
    sample_html_content: dict[str, str],
    crawler_test_data: dict[str, Any],
    page_url: str,
    html_content: str,
    expected_page_links: str | None,
) -> None:
    """
    Test link extraction across different types of pages using fixtures.

    This test uses the crawler_test_data fixture to verify that link extraction
    works correctly across a variety of pages with different characteristics.
    """
    base_domain = crawler_test_data["base_domain"]
    expected_links = crawler_test_data["expected_links"]

    # Map of page URLs to their corresponding HTML content
    page_to_html = {
        base_domain: sample_html_content["basic"],
        f"{base_domain}/page1.html": sample_html_content["with_external_links"],
        f"{base_domain}/page2.html": sample_html_content["with_fragments"],
        f"{base_domain}/page3.html": sample_html_content["no_links"],
    }

    # Test each page defined in our test data
    for page_url, html_content in page_to_html.items():
        links = extract_links(html_content, page_url)
        expected_page_links = expected_links.get(page_url, set())

        # Verify that the extracted links match the expected links
        assert links == expected_page_links, f"Links don't match for page {page_url}"


@pytest.mark.parametrize("scheme", [proto for proto in SUPPORTED_PROTOCOLS])
def test_extract_links_supported_protocols(scheme: str, sample_html_content: dict[str, str]) -> None:
    """
    Test that extract_links correctly handles URLs with supported protocols.

    This test verifies that links with protocols in SUPPORTED_PROTOCOLS are included
    in the results, based on the actual configured protocols in the application.

    Args:
        scheme: Protocol to test (from SUPPORTED_PROTOCOLS)
        sample_html_content: Fixture providing sample HTML content
    """
    # Create a simple HTML with a link using the protocol being tested
    html = f'<html><body><a href="{scheme}://example.com/page.html">Link</a></body></html>'

    links = extract_links(html, f"{scheme}://example.com")

    # The link should be included in the results
    assert f"{scheme}://example.com/page.html" in links
