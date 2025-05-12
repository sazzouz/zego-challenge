import logging
from urllib.parse import quote, urljoin, urlparse

import httpx
from typeguard import typechecked

from .constants import DEFAULT_HEADERS, DEFAULT_TIMEOUT, HTTP_SUCCESS_CODE_DESCRIPTIONS, HTTP_SUPPORTED_SUCCESS_CODES

logger = logging.getLogger(__name__)


@typechecked
async def fetch_page(url: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[str, str | None]:
    """
    Fetches the HTML content of a web page.

    Handles the full lifecycle of an HTTP request, including:
    - Creating an HTTP client with appropriate configuration
    - Making the request with error handling
    - Processing and validating the response
    - Returning the fetched URL (which may differ from input due to redirects) and content

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds

    Returns:
        A tuple (url, html_content) where:
        - url is the URL that was fetched (could be different from input due to redirects)
        - html_content is the HTML content of the page or None if the request failed

    Example:
        ```python
        url, html = await fetch_page("https://example.com")
        if html:
            # Process the HTML content
            print(f"Successfully fetched {url}, content length: {len(html)}")
        ```
    """
    try:
        # Create a configured HTTP client with proper headers, timeout, and redirect handling
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=timeout, follow_redirects=True) as client:
            try:
                # Make the HTTP request
                response = await client.get(url)

                # Log appropriate message based on status code
                if response.status_code not in HTTP_SUPPORTED_SUCCESS_CODES:
                    # Check if it's still a successful status (2xx) but not in our SUCCESS_RES_CODES
                    if response.is_success:
                        status_desc = HTTP_SUCCESS_CODE_DESCRIPTIONS.get(
                            response.status_code, "Successful but not processable"
                        )
                        logger.warning(
                            f"Received HTTP {response.status_code} ({status_desc}) for {url}. "
                            f"This is technically a successful response but not suitable for crawling."
                        )
                    else:
                        logger.warning(f"Failed to fetch {url}: HTTP {response.status_code}")

                    return url, None

                # Verify response is HTML content
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type:
                    logger.warning(
                        f"Non-HTML content at {url} (Content-Type: {content_type}). "
                        f"Only HTML content can be processed for crawling."
                    )
                    return url, None

                logger.debug(f"Successfully fetched HTML content from {url}")
                return url, response.text

            except (httpx.TimeoutException, httpx.RequestError) as e:
                logger.warning(f"Request error while fetching {url}: {str(e)}")
                return url, None

    except Exception as e:
        logger.error(f"Unexpected error while fetching {url}: {str(e)}")
        return url, None


@typechecked
def get_domain_netloc(url: str) -> str:
    """
    Extract the network location (hostname and optional port) from a URL.

    This function parses a URL and returns its network location component,
    which consists of the hostname and optionally a port number.

    Args:
        url: The URL to parse

    Returns:
        The network location (e.g., 'example.com', 'example.com:8080')
        Returns an empty string if the URL is invalid or has no netloc

    Examples:
        >>> get_domain_netloc('https://example.com/path')
        'example.com'
        >>> get_domain_netloc('http://example.com:8080/path')
        'example.com:8080'
        >>> get_domain_netloc('invalid')
        ''
    """
    try:
        parsed_url = urlparse(url)
        return parsed_url.netloc
    except ValueError:
        return ""


@typechecked
def normalize_url(url: str, base_url: str) -> str:
    """
    Normalize a URL by resolving it against a base URL and ensuring proper formatting.

    This function:
    1. Resolves relative URLs against the provided base URL
    2. Removes fragments (the part after #)
    3. Properly escapes special characters in the path
    4. Ensures the URL has a scheme (protocol)

    Args:
        url: The URL to normalize (can be relative or absolute)
        base_url: The base URL to resolve relative URLs against

    Returns:
        The normalized absolute URL string
        Returns an empty string if normalization fails

    Examples:
        >>> normalize_url('/page', 'https://example.com')
        'https://example.com/page'
        >>> normalize_url('page?q=test', 'https://example.com/dir/')
        'https://example.com/dir/page?q=test'
        >>> normalize_url('#section', 'https://example.com/page')
        'https://example.com/page'
    """
    try:
        # Strip whitespace and resolve against base_url
        abs_url = urljoin(base_url, url.strip())
        parsed = urlparse(abs_url)

        # Rebuild the URL with the quoted path, preserving query parameters
        return f"{parsed.scheme}://{parsed.netloc}{quote(parsed.path)}{f'?{parsed.query}' if parsed.query else ''}"
    except ValueError:
        return ""


@typechecked
def is_same_domain(url: str, base_domain_netloc: str) -> bool:
    """
    Check if a URL belongs to the same domain as the base domain.

    This function determines if a URL is within the same domain (network location)
    as the provided base domain. Subdomains are considered different domains.
    The function handles various edge cases like default ports (80 for HTTP, 443 for HTTPS).

    Args:
        url: The URL to check
        base_domain_netloc: The network location of the base domain (e.g., 'example.com')

    Returns:
        True if the URL is within the same domain, False otherwise

    Examples:
        >>> is_same_domain('https://example.com/page', 'example.com')
        True
        >>> is_same_domain('https://subdomain.example.com', 'example.com')
        False
        >>> is_same_domain('https://example.com:443', 'example.com')
        True
        >>> is_same_domain('http://example.com:80', 'example.com')
        True
    """
    if not base_domain_netloc:  # Cannot compare if base_domain_netloc is empty
        return False

    try:
        parsed_url = urlparse(url)

        # Only process HTTP/HTTPS URLs
        if parsed_url.scheme not in ("http", "https"):
            return False

        url_netloc = parsed_url.netloc

        # Handle default ports that may be explicitly included in one URL but not the other
        if (url_netloc == f"{base_domain_netloc}:80" and parsed_url.scheme == "http") or (
            url_netloc == f"{base_domain_netloc}:443" and parsed_url.scheme == "https"
        ):
            return True

        # Standard comparison
        return url_netloc == base_domain_netloc
    except ValueError:
        return False
