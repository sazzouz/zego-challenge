# HTTP-related constants
# -----------------------

# Default request headers to mimic a browser request for better compatibility with websites
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",  # noqa: E501
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Valid protocols for URLs
SUPPORTED_PROTOCOLS = {"http", "https"}

# HTTP Status Codes considered successful for crawling
# For now, only 200 OK is considered useful as we need content to parse
HTTP_SUPPORTED_SUCCESS_CODES = {200}

# HTTP Status code descriptions for better logging
HTTP_SUCCESS_CODE_DESCRIPTIONS = {
    200: "OK - Standard successful response with content",
    201: "Created - Resource has been created",
    202: "Accepted - Request accepted but processing not completed",
    203: "Non-Authoritative Information - Modified response from origin server",
    204: "No Content - Request succeeded but no content returned",
    205: "Reset Content - Request succeeded, client should reset document view",
    206: "Partial Content - Partial GET request fulfilled",
}


# Crawler behavior constants
# --------------------------

# Default timeout for requests in seconds to prevent hanging on slow responses
DEFAULT_TIMEOUT = 10.0

# Default maximum number of pages to crawl to prevent infinite loops or excessive crawling
DEFAULT_MAX_PAGES = 1000

# Default number of concurrent requests to optimize performance
DEFAULT_CONCURRENCY = 5
