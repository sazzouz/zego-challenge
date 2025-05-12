class CrawlerError(Exception):
    """
    Base exception class for all crawler-related errors.

    All other crawler exceptions inherit from this class, making it
    possible to catch all crawler-specific errors with a single except clause.

    Example:
        ```python
        try:
            # Crawler code that might raise various crawler-specific exceptions
            crawler.crawl()
        except CrawlerError as e:
            # Handle any type of crawler error
            print(f"Crawler error occurred: {e}")
        ```
    """

    pass


class InvalidURLError(CrawlerError):
    """
    Exception raised when a URL is invalid or malformed.

    This exception is raised when a URL cannot be parsed correctly or
    doesn't conform to expected URL format.

    Example:
        ```python
        try:
            if not is_valid_url(url):
                raise InvalidURLError(f"The URL '{url}' is invalid")
        except InvalidURLError as e:
            print(f"URL error: {e}")
        ```
    """

    pass


class InvalidProtocolError(InvalidURLError):
    """
    Exception raised when a URL uses an unsupported protocol.

    This exception occurs when a URL has a protocol that is not in the list
    of supported protocols (typically only 'http://' and 'https://').

    Example:
        ```python
        try:
            protocol = url.split('://', 1)[0] if '://' in url else ''
            if protocol and protocol not in VALID_PROTOCOLS:
                raise InvalidProtocolError(
                    f"URL '{url}' uses unsupported protocol '{protocol}'. "
                    f"Only {', '.join(VALID_PROTOCOLS)} are supported."
                )
        except InvalidProtocolError as e:
            print(f"Protocol error: {e}")
        ```
    """

    pass


class MissingProtocolError(InvalidURLError):
    """
    Exception raised when a URL is missing a protocol specification.

    This is a specific type of InvalidURLError that indicates the URL
    doesn't include any protocol (e.g., 'http://' or 'https://').

    Example:
        ```python
        try:
            if '://' not in url:
                raise MissingProtocolError(f"URL '{url}' is missing a protocol")
        except MissingProtocolError as e:
            # Add a default protocol and retry
            url = f"https://{url}"
        ```
    """

    pass
