import asyncio
import logging

from typeguard import typechecked

from .constants import DEFAULT_CONCURRENCY, DEFAULT_MAX_PAGES, DEFAULT_TIMEOUT, SUPPORTED_PROTOCOLS
from .exceptions import InvalidProtocolError, InvalidURLError, MissingProtocolError
from .parser import extract_links
from .utils import fetch_page, get_domain_netloc, is_same_domain, normalize_url

logger = logging.getLogger(__name__)


@typechecked
class Crawler:
    """
    Asynchronous web crawler that stays within a single domain.

    This crawler implements a concurrent crawling strategy using asyncio, respecting
    domain boundaries and efficiently managing visited URLs. It processes pages
    in parallel up to a configurable concurrency limit.

    The crawler uses asyncio's cooperative multitasking model to efficiently handle
    multiple concurrent HTTP requests without blocking. This approach is particularly
    well-suited for I/O-bound tasks like web crawling, as it allows the crawler to
    make progress on other URLs while waiting for HTTP responses.

    Concurrency is controlled using asyncio.Semaphore to limit the number of
    simultaneous requests, preventing overloading of the target server and ensuring
    efficient resource usage.

    Attributes:
        base_url: The starting URL for crawling
        base_domain_netloc: The network location of the base domain
        concurrency: Maximum number of concurrent requests
        timeout: Timeout for HTTP requests in seconds
        max_pages: Maximum number of pages to crawl
        urls_to_visit: Queue of URLs to be processed
        visited_urls: Set of URLs that have been visited or queued
        found_links_map: Dictionary mapping crawled URLs to their found links
        semaphore: Semaphore limiting concurrent requests
    """

    def __init__(
        self,
        base_url: str,
        concurrency: int = DEFAULT_CONCURRENCY,
        timeout: float = DEFAULT_TIMEOUT,
        max_pages: int = DEFAULT_MAX_PAGES,
    ):
        """
        Initialize the crawler with the specified parameters.

        Args:
            base_url: The starting URL for crawling
            concurrency: Maximum number of concurrent requests
            timeout: Timeout for HTTP requests in seconds
            max_pages: Maximum number of pages to crawl to prevent infinite loops

        Raises:
            MissingProtocolError: If the URL doesn't include a protocol
            InvalidProtocolError: If the URL uses an unsupported protocol
            InvalidURLError: If the URL is malformed or cannot be parsed

        Example:
            ```python
            crawler = Crawler("https://example.com", concurrency=10, max_pages=500)
            results = await crawler.crawl()
            ```
        """

        # Check if the URL has a protocol
        if "://" not in base_url:
            raise MissingProtocolError(
                f"URL '{base_url}' is missing a protocol. Please provide a complete URL with a protocol."
            )

        # Validate the protocol
        protocol = base_url.split("://", 1)[0].lower()
        if protocol not in SUPPORTED_PROTOCOLS:
            valid_protocols_str = ", ".join(f"'{p}'" for p in SUPPORTED_PROTOCOLS)
            raise InvalidProtocolError(
                f"URL '{base_url}' uses unsupported protocol '{protocol}'. Only {valid_protocols_str} are supported."
            )

        # Normalize and validate the base URL
        self.base_url = normalize_url(base_url, base_url)
        self.base_domain_netloc = get_domain_netloc(self.base_url)

        # Handle invalid base URL
        if not self.base_domain_netloc:
            raise InvalidURLError(f"Invalid base URL: '{base_url}'. The URL could not be parsed correctly.")

        # Set crawler parameters
        self.concurrency = concurrency
        self.timeout = timeout
        self.max_pages = max_pages

        # Initialize data structures
        self.urls_to_visit: asyncio.Queue = asyncio.Queue()
        self.visited_urls: set[str] = set()
        self.found_links_map: dict[str, set[str]] = {}

        # Semaphore to control concurrency
        self.semaphore = asyncio.Semaphore(concurrency)

        # Add initial URL to the queue and visited set
        self.urls_to_visit.put_nowait(self.base_url)
        self.visited_urls.add(self.base_url)

    async def crawl(self) -> dict[str, set[str]]:
        """
        Start the crawling process.

        This method coordinates the asynchronous crawling process by:
        1. Creating worker tasks to process URLs concurrently
        2. Waiting for all URLs to be processed
        3. Handling cancellation and cleanup
        4. Returning the crawl results

        The method leverages asyncio's task management to efficiently handle multiple
        concurrent workers, each processing URLs from the queue. The semaphore ensures
        that we never exceed the specified concurrency limit.

        Returns:
            A dictionary mapping each crawled URL to the set of URLs found on that page

        Example:
            ```python
            crawler = Crawler("https://example.com")
            results = await crawler.crawl()
            for url, links in results.items():
                print(f"Page {url} contains {len(links)} links")
            ```
        """
        # Create worker tasks
        workers = [asyncio.create_task(self._worker()) for _ in range(self.concurrency)]
        logger.info(f"Starting crawl with {self.concurrency} workers from {self.base_url}")

        try:
            # Wait for the queue to be fully processed
            await self.urls_to_visit.join()
            logger.info(f"Crawl completed. Processed {len(self.found_links_map)} pages.")
        except asyncio.CancelledError:
            logger.info("Crawling was cancelled")
        finally:
            # Cancel any remaining workers
            for worker in workers:
                worker.cancel()

            # Wait for all workers to be cancelled
            if workers:
                await asyncio.gather(*workers, return_exceptions=True)

        return self.found_links_map

    async def _worker(self) -> None:
        """
        Worker coroutine that processes URLs from the queue.

        Each worker:
        1. Takes a URL from the queue
        2. Acquires a semaphore slot (limiting concurrency)
        3. Fetches the page content
        4. Extracts and processes links
        5. Releases the semaphore
        6. Repeats until the queue is empty or max pages is reached

        This approach ensures that we never exceed the configured concurrency limit,
        even if many workers are running. The semaphore is a key component of asyncio's
        concurrency control mechanisms, allowing us to limit resource usage efficiently.
        """
        while True:
            try:
                # Check if we've reached the maximum number of pages
                if len(self.found_links_map) >= self.max_pages:
                    logger.warning(f"Reached maximum page limit of {self.max_pages}. Stopping crawl.")
                    # Empty the queue to signal completion to all workers
                    self._empty_queue()
                    break

                # Get a URL from the queue
                url = await self.urls_to_visit.get()
                logger.debug(f"Processing: {url}")

                try:
                    # Use semaphore to limit concurrency
                    async with self.semaphore:
                        # Fetch the page content
                        fetched_url, html = await fetch_page(url, self.timeout)

                        if html:
                            # Extract and process links
                            links = extract_links(html, fetched_url)
                            self.found_links_map[fetched_url] = links
                            await self._process_links(links)
                            logger.debug(f"Processed {url}: found {len(links)} links")
                        else:
                            logger.debug(f"Failed to retrieve HTML content from {url}")
                except Exception as e:
                    logger.error(f"Error processing {url}: {str(e)}")

                # Mark the task as done
                self.urls_to_visit.task_done()
            except asyncio.CancelledError:
                # Handle cancellation
                logger.debug("Worker cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in worker: {str(e)}")
                # Mark the task as done even if there was an error
                self.urls_to_visit.task_done()

    def _empty_queue(self) -> None:
        """
        Empty the URL queue and mark all tasks as done.

        This is used when stopping the crawl early (e.g., when reaching max pages).
        The method works synchronously to quickly clear the queue without waiting
        for async operations.
        """
        while not self.urls_to_visit.empty():
            try:
                self.urls_to_visit.get_nowait()
                self.urls_to_visit.task_done()
            except asyncio.QueueEmpty:
                break

    async def _process_links(self, links: set[str]) -> None:
        """
        Process extracted links and add new URLs to the queue.

        This method:
        1. Filters links to include only those from the same domain
        2. Excludes URLs that have already been visited or queued
        3. Adds new URLs to both the visited set and the queue

        While this method is async, it doesn't use await for the bulk of its processing,
        only when adding new URLs to the queue. This makes it efficient for processing
        large sets of links.

        Args:
            links: Set of links to process
        """
        for link in links:
            # Add to queue only if:
            # 1. Link is in the same domain as the base URL
            # 2. Link hasn't been visited or queued yet
            if is_same_domain(link, self.base_domain_netloc) and link not in self.visited_urls:
                # Mark as visited before adding to queue to prevent duplicates
                self.visited_urls.add(link)
                await self.urls_to_visit.put(link)


@typechecked
async def crawl_site(
    url: str, concurrency: int = DEFAULT_CONCURRENCY, max_pages: int = DEFAULT_MAX_PAGES
) -> dict[str, set[str]]:
    """
    Convenience function to crawl a site from a given URL, i.e. for simpler use in the CLI.

    This is a high-level async function that creates a Crawler instance and runs the crawl process.
    It leverages asyncio to perform concurrent crawling of the target site, making it much faster
    than a synchronous approach would be for this I/O-bound task.

    Args:
        url: The starting URL for crawling
        concurrency: Maximum number of concurrent requests
        max_pages: Maximum number of pages to crawl to prevent infinite loops

    Returns:
        A dictionary mapping each crawled URL to the set of URLs found on that page

    Example:
        ```python
        # This must be called from an async context or using asyncio.run()
        results = await crawl_site("https://example.com", concurrency=5)
        print(f"Crawled {len(results)} pages")
        ```
    """
    crawler = Crawler(url, concurrency=concurrency, max_pages=max_pages)
    return await crawler.crawl()
