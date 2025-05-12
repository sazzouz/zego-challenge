from collections.abc import Awaitable, Callable, Generator
from typing import TypedDict
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from rich.console import Console
from typer.testing import CliRunner

from crawler_app.cli import CrawlerProgress
from crawler_app.crawler import Crawler


class CrawlerTestData(TypedDict):
    """Type definition for crawler test data dictionary."""

    base_domain: str
    base_domain_netloc: str
    pages_to_crawl: list[str]
    expected_links: dict[str, set[str]]
    urls_not_to_crawl: list[str]


@pytest.fixture
def sample_html_content() -> dict[str, str]:
    """
    Returns a dictionary of sample HTML contents for different test scenarios.

    The dictionary contains the following keys:
    - basic: Simple HTML with a few links
    - with_external_links: HTML with links to external domains and subdomains
    - with_fragments: HTML with fragment links
    - with_invalid_links: HTML with invalid or empty links
    - malformed: Malformed HTML with unclosed tags
    - no_links: HTML without any links
    - with_special_urls: HTML with mailto: and tel: URLs
    - with_recursive_links: HTML with links forming a loop (recursive structure)

    These samples are used by various tests to verify the behavior of the parser
    and crawler components without making real HTTP requests.
    """
    return {
        "basic": """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <a href="page1.html">Page 1</a>
                <a href="/page2.html">Page 2</a>
                <a href="http://example.com/page3.html">Page 3</a>
            </body>
        </html>
        """,
        "with_external_links": """
        <html>
            <head><title>Page with External Links</title></head>
            <body>
                <a href="http://example.com/internal.html">Internal</a>
                <a href="http://external.com/page.html">External</a>
                <a href="http://sub.example.com/page.html">Subdomain</a>
            </body>
        </html>
        """,
        "with_fragments": """
        <html>
            <head><title>Page with Fragments</title></head>
            <body>
                <a href="page1.html#section1">Page 1 Section 1</a>
                <a href="page1.html#section2">Page 1 Section 2</a>
            </body>
        </html>
        """,
        "with_invalid_links": """
        <html>
            <head><title>Page with Invalid Links</title></head>
            <body>
                <a href="">Empty Link</a>
                <a href="javascript:void(0)">JavaScript Link</a>
                <a href="#section">Fragment Link</a>
            </body>
        </html>
        """,
        "malformed": """
        <html>
            <head><title>Malformed HTML</title>
            <body>
                <a href="page1.html">Unclosed tag
                <p>Another tag</p>
                <a href="page2.html">Another link</a>
            </body>
        </html>
        """,
        "no_links": """
        <html>
            <head><title>No Links</title></head>
            <body>
                <p>This page has no links.</p>
            </body>
        </html>
        """,
        "with_special_urls": """
        <html>
            <head><title>Page with Special URLs</title></head>
            <body>
                <a href="mailto:contact@example.com">Contact Us</a>
                <a href="tel:+12345678900">Call Us</a>
                <a href="ftp://ftp.example.com/files/">FTP Files</a>
                <a href="http://example.com/page1.html">Normal Link</a>
            </body>
        </html>
        """,
        "with_recursive_links": """
        <html>
            <head><title>Page with Recursive Links</title></head>
            <body>
                <a href="http://example.com/recursive1.html">Recursive 1</a>
                <a href="http://example.com/recursive2.html">Recursive 2</a>
                <a href="http://example.com/page1.html">Normal Link</a>
            </body>
        </html>
        """,
        "recursive1": """
        <html>
            <head><title>Recursive Page 1</title></head>
            <body>
                <a href="http://example.com/recursive2.html">To Recursive 2</a>
                <a href="http://example.com/recursive1.html">Back to myself</a>
            </body>
        </html>
        """,
        "recursive2": """
        <html>
            <head><title>Recursive Page 2</title></head>
            <body>
                <a href="http://example.com/recursive1.html">To Recursive 1</a>
                <a href="http://example.com/recursive2.html">Back to myself</a>
            </body>
        </html>
        """,
    }


@pytest_asyncio.fixture
async def mock_http_client(
    sample_html_content: dict[str, str],
) -> Callable[[str, float], Awaitable[tuple[str, str | None]]]:
    """
    Creates a mock HTTP client that returns predefined responses based on URLs.

    This fixture simulates HTTP responses for different types of URLs:
    - Regular HTML pages (200 OK with HTML content)
    - Error pages (404 Not Found)
    - Non-HTML content (like PDFs)
    - Empty pages
    - External domains and subdomains

    The mock client is used to test the crawler's behavior without making
    real HTTP requests, ensuring consistent and predictable test results.

    Usage:
        async def test_something(mock_http_client):
            url, content = await mock_http_client("http://example.com")
            assert content is not None  # Successfully fetched HTML
    """
    # Base domain for our tests
    base_domain = "http://example.com"

    # Map of URLs to response content, status codes and content types
    url_responses: dict[str, tuple[int, str | None, str | None]] = {
        f"{base_domain}": (200, "text/html", sample_html_content["basic"]),
        f"{base_domain}/": (200, "text/html", sample_html_content["basic"]),
        f"{base_domain}/page1.html": (
            200,
            "text/html",
            sample_html_content["with_external_links"],
        ),
        f"{base_domain}/page2.html": (
            200,
            "text/html",
            sample_html_content["with_fragments"],
        ),
        f"{base_domain}/page3.html": (
            200,
            "text/html",
            sample_html_content["no_links"],
        ),
        f"{base_domain}/error.html": (404, "text/html", None),
        f"{base_domain}/file.pdf": (200, "application/pdf", "PDF content"),
        f"{base_domain}/malformed.html": (
            200,
            "text/html",
            sample_html_content["malformed"],
        ),
        f"{base_domain}/empty.html": (200, "text/html", ""),
        f"{base_domain}/internal.html": (
            200,
            "text/html",
            sample_html_content["no_links"],
        ),
        f"{base_domain}/special_urls.html": (
            200,
            "text/html",
            sample_html_content["with_special_urls"],
        ),
        f"{base_domain}/recursive.html": (
            200,
            "text/html",
            sample_html_content["with_recursive_links"],
        ),
        f"{base_domain}/recursive1.html": (
            200,
            "text/html",
            sample_html_content["recursive1"],
        ),
        f"{base_domain}/recursive2.html": (
            200,
            "text/html",
            sample_html_content["recursive2"],
        ),
        "http://external.com": (200, "text/html", sample_html_content["basic"]),
        "http://sub.example.com": (200, "text/html", sample_html_content["basic"]),
        "invalid_url": (0, None, None),  # Will trigger an exception
    }

    # Create mock response for a given URL
    async def mock_fetch_page(url: str, timeout: float = 10.0) -> tuple[str, str | None]:
        if url not in url_responses:
            # Return a default response for unknown URLs
            return url, None

        status_code, content_type, content = url_responses[url]

        if status_code != 200 or not content or content_type != "text/html":
            return url, None

        return url, content

    return mock_fetch_page


@pytest.fixture
def crawler_test_data() -> CrawlerTestData:
    """
    Returns test data for the crawler including URLs and their expected links.

    This fixture provides consistent test data for crawler tests, including:
    - The base domain and its network location
    - A list of pages that should be crawled
    - Expected links for each page
    - URLs that should not be crawled (external domains, subdomains, error pages)

    This helps ensure tests are consistent and focused on the crawler's
    behavior rather than the specifics of the test data.

    Usage:
        def test_something(crawler_test_data):
            base_url = crawler_test_data["base_domain"]
            expected_links = crawler_test_data["expected_links"]
            # Use the data in tests...
    """
    # Base domain for our tests
    base_domain = "http://example.com"

    # List of pages to be crawled
    pages_to_crawl = [
        f"{base_domain}",
        f"{base_domain}/page1.html",
        f"{base_domain}/page2.html",
        f"{base_domain}/page3.html",
        f"{base_domain}/internal.html",
        f"{base_domain}/special_urls.html",
        f"{base_domain}/recursive.html",
        f"{base_domain}/recursive1.html",
        f"{base_domain}/recursive2.html",
    ]

    # Map of normalized URLs found on each page
    expected_links: dict[str, set[str]] = {
        f"{base_domain}": {
            f"{base_domain}/page1.html",
            f"{base_domain}/page2.html",
            f"{base_domain}/page3.html",
        },
        f"{base_domain}/page1.html": {
            f"{base_domain}/internal.html",
            "http://external.com/page.html",
            "http://sub.example.com/page.html",
        },
        f"{base_domain}/page2.html": {
            f"{base_domain}/page1.html",
        },
        f"{base_domain}/page3.html": set(),  # No links on this page
        f"{base_domain}/internal.html": set(),  # No links on this page
        f"{base_domain}/special_urls.html": {
            f"{base_domain}/page1.html",  # Only normal link should be included
        },
        f"{base_domain}/recursive.html": {
            f"{base_domain}/recursive1.html",
            f"{base_domain}/recursive2.html",
            f"{base_domain}/page1.html",
        },
        f"{base_domain}/recursive1.html": {
            f"{base_domain}/recursive2.html",
            f"{base_domain}/recursive1.html",  # Self-reference
        },
        f"{base_domain}/recursive2.html": {
            f"{base_domain}/recursive1.html",
            f"{base_domain}/recursive2.html",  # Self-reference
        },
    }

    # URLs that should not be crawled (external domains, subdomains, or error pages)
    urls_not_to_crawl = [
        "http://external.com/page.html",
        "http://sub.example.com/page.html",
        f"{base_domain}/error.html",
        f"{base_domain}/file.pdf",
        "mailto:contact@example.com",
        "tel:+12345678900",
        "ftp://ftp.example.com/files/",
    ]

    return {
        "base_domain": base_domain,
        "base_domain_netloc": "example.com",
        "pages_to_crawl": pages_to_crawl,
        "expected_links": expected_links,
        "urls_not_to_crawl": urls_not_to_crawl,
    }


@pytest_asyncio.fixture
async def crawler(mock_http_client: Callable[[str, float], Awaitable[tuple[str, str | None]]], monkeypatch) -> Crawler:
    """
    Create a Crawler instance with a mocked HTTP client.

    This fixture creates a reusable crawler instance for tests, with a
    mocked HTTP client to avoid actual network requests.

    Args:
        mock_http_client: Mock HTTP client fixture
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        Crawler: A configured crawler instance for testing
    """
    # Patch the fetch_page function to use our mock
    monkeypatch.setattr("crawler_app.utils.fetch_page", mock_http_client)

    # Create and return the crawler instance
    return Crawler("http://example.com")


@pytest.fixture
def mock_console() -> MagicMock:
    """
    Provides a mock console for testing UI output.

    This fixture creates a mock of the Rich Console class, allowing tests to
    verify console output without actually writing to the terminal.

    Returns:
        MagicMock: A mock Rich Console object for capturing UI output
    """
    console = MagicMock(spec=Console)
    return console


@pytest.fixture
def crawler_progress(mock_console: MagicMock) -> CrawlerProgress:
    """
    Creates a CrawlerProgress instance with a mocked console.

    This fixture provides a pre-configured CrawlerProgress instance with
    mocked components to facilitate testing without actual console output.

    Args:
        mock_console: The mocked console from the mock_console fixture

    Returns:
        CrawlerProgress: A configured progress tracker with mocked components
    """
    progress = CrawlerProgress(verbose=True)
    progress.console = mock_console
    progress.progress = MagicMock()
    progress.crawling_task_id = 1  # Mock task ID
    return progress


@pytest.fixture
def runner() -> CliRunner:
    """
    Create a CLI runner for Typer app.

    This fixture provides a runner that allows testing of Typer CLI
    applications without actually running the commands in the real system.

    Returns:
        CliRunner: A Typer CLI runner for testing CLI commands
    """
    return CliRunner()


@pytest.fixture
def mock_crawl_site() -> Generator[MagicMock, None, None]:
    """
    Mock the crawl_site function to avoid actual HTTP requests.

    This fixture replaces the crawler's crawl_site function with a mock
    that returns predefined results, allowing tests to run without making
    actual network requests.

    Returns:
        MagicMock: A mock of the crawl_site function that returns sample results
    """
    with patch("crawler_app.cli.crawl_site") as mock:
        # Set up the mock to return a sample result
        mock.return_value = {"http://example.com": {"http://example.com/page1.html", "http://example.com/page2.html"}}
        yield mock
