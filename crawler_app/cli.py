import asyncio
import logging
import sys
import time

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn
from typeguard import typechecked

from .constants import DEFAULT_CONCURRENCY, SUPPORTED_PROTOCOLS
from .crawler import crawl_site
from .exceptions import InvalidProtocolError, InvalidURLError, MissingProtocolError

# Configure logging for async use, i.e. streaming data to the console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# Typer instance for creating a CLI application
app = typer.Typer()


@typechecked
class CrawlerProgress:
    """
    Class to track and display crawler progress using the `rich` (Rich) Python package.

    This class provides real-time visual feedback about the crawling process using
    the Rich library's progress display features. It shows the current URL being
    processed and maintains a count of pages crawled.

    Attributes:
        console: Rich console for output
        progress: Rich progress display manager
        crawling_task_id: ID of the progress tracking task
        pages_crawled: Number of pages crawled so far
        latest_url: Most recent URL being processed
        verbose: Whether to print additional details
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize the progress tracker.

        Args:
            verbose: Whether to print additional details about the crawling process
        """
        self.console = Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            console=self.console,
        )
        self.crawling_task_id: TaskID | None = None
        self.pages_crawled = 0
        self.latest_url = ""
        self.verbose = verbose

    def start(self) -> None:
        """
        Start the progress display and create the tracking task.

        This method initializes the Rich progress display and creates
        a new task to track the crawling progress.
        """
        self.progress.start()
        self.crawling_task_id = self.progress.add_task("Crawling...", total=None)

    def update(self, crawled: int, latest_url: str) -> None:
        """
        Update the progress display with current crawling status.

        Args:
            crawled: Number of pages crawled so far
            latest_url: The URL currently being processed
        """
        self.pages_crawled = crawled
        self.latest_url = latest_url

        # Truncate long URLs in the display for better readability
        truncated_url = self.latest_url[:50] + ("..." if len(self.latest_url) > 50 else "")

        # Update the progress task with new information
        self.progress.update(
            self.crawling_task_id,
            completed=self.pages_crawled,
            description=f"Crawling: {truncated_url}",
        )

        # Print the full URL in verbose mode
        if self.verbose:
            self.progress.console.print(f"Crawling: {latest_url}")

    def stop(self) -> None:
        """
        Stop the progress display.

        This method safely stops the Rich progress display if it's active.
        """
        if self.progress.live:
            self.progress.stop()


@typechecked
async def monitor_crawler_progress(crawler_progress: CrawlerProgress, result_dict: dict[str, set[str]]) -> None:
    """
    Asynchronously monitor crawler progress and update the display.

    This coroutine runs concurrently with the crawler, periodically checking
    the result dictionary for changes and updating the progress display accordingly.
    It uses asyncio.sleep() to yield control back to the event loop between checks,
    enabling cooperative multitasking.

    Args:
        crawler_progress: The progress tracker instance to update
        result_dict: The dictionary that will be populated with results by the crawler
    """
    last_count = 0
    last_url = ""

    while True:
        # Get current count of pages crawled
        current_count = len(result_dict)

        # Find the latest URL (the last key added to the dictionary)
        current_urls = list(result_dict.keys())
        current_url = current_urls[-1] if current_urls else last_url

        # Update the progress if there's a change
        if current_count != last_count or current_url != last_url:
            crawler_progress.update(current_count, current_url)
            last_count = current_count
            last_url = current_url

        # Yield control back to the event loop
        # This is a key component of asyncio's cooperative multitasking
        await asyncio.sleep(0.1)


@typechecked
@app.command()
def main(
    url: str = typer.Argument(..., help="Base URL to crawl"),
    concurrency: int = typer.Option(
        DEFAULT_CONCURRENCY, "--concurrency", "-c", help="Maximum number of concurrent requests"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    """
    Crawl a website starting from the given URL.

    This command-line interface function is the entry point for the crawler.
    It handles command-line arguments, sets up the crawler, manages the progress
    display, and presents the results.

    The crawler uses asyncio for high-performance concurrent processing, but this
    function provides a synchronous interface using asyncio.run() to simplify CLI usage.

    Args:
        url: Base URL to crawl
        concurrency: Maximum number of concurrent requests
        verbose: Whether to enable verbose output

    The crawler will only process URLs within the same domain and will not follow links
    to external sites or subdomains. For each page visited, it will print the URL and
    all links found on that page.
    """
    # Configure logging level based on verbose flag
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    console = Console()
    original_url = url
    start_time = time.time()  # Record the start time

    try:
        # Try to use the URL as provided
        # If it's missing a protocol, automatically add https://
        if "://" not in url:
            url = f"https://{url}"
            console.print(f"[yellow]Adding default protocol to URL:[/yellow] '{original_url}' -> '{url}'")
            logger.info(f"Added HTTPS protocol to URL: {original_url} -> {url}")
        else:
            # Check if the protocol is valid
            protocol = url.split("://", 1)[0].lower()
            if protocol not in SUPPORTED_PROTOCOLS:
                valid_protocols_str = ", ".join(f"'{p}'" for p in SUPPORTED_PROTOCOLS)
                console.print(
                    f"[bold red]Error:[/bold red] URL '{url}' uses unsupported protocol '{protocol}'. "
                    f"Only {valid_protocols_str} are supported."
                )
                sys.exit(1)

        logger.info(f"Starting crawler at URL: {url}")
        logger.info(f"Concurrency level: {concurrency}")

        # Initialize result dictionary to be shared between crawler and progress monitor
        result: dict[str, set[str]] = {}

        # Create progress tracker
        crawler_progress = CrawlerProgress(verbose=verbose)

        # Start the progress display
        crawler_progress.start()

        # Define the async function that coordinates the crawler and progress monitor
        async def run_with_progress() -> None:
            """
            Coordinate crawler and progress monitor coroutines.

            This async function:
            1. Starts the progress monitoring task
            2. Runs the crawler
            3. Cancels the monitor when crawling is complete

            It demonstrates asyncio's task management capabilities, running
            multiple coroutines concurrently and handling their lifecycle.
            """
            # Start progress monitoring task
            monitor_task = asyncio.create_task(monitor_crawler_progress(crawler_progress, result))

            try:
                # Run the crawler and update the result dictionary
                result.update(await crawl_site(url, concurrency))
            finally:
                # Ensure monitor task is always cancelled properly
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass

        # Run the crawler with progress monitoring
        # asyncio.run creates a new event loop, runs the coroutine, and closes the loop
        asyncio.run(run_with_progress())

        # Stop the progress display
        crawler_progress.stop()

        # Calculate elapsed time
        elapsed_time = time.time() - start_time

        # Print the results
        display_results(result, elapsed_time)

    except MissingProtocolError:
        handle_missing_protocol_error(original_url)
    except InvalidProtocolError as e:
        handle_invalid_protocol_error(e)
    except InvalidURLError as e:
        handle_url_error(e)
    except ValueError as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        handle_keyboard_interrupt(crawler_progress)
    except Exception as e:
        handle_unexpected_error(e, crawler_progress)


def display_results(result: dict[str, set[str]], elapsed_time: float = 0) -> None:
    """
    Display the crawling results in a formatted way.

    Args:
        result: Dictionary mapping each crawled URL to the set of URLs found on that page
        elapsed_time: Total time spent crawling in seconds
    """
    console = Console()
    console.print("\n[bold green]Crawl Results:[/bold green]")
    console.print("=" * 80)

    # Handle empty results
    if not result:
        console.print("[yellow]No pages were crawled.[/yellow]")
        return

    # Display results for each page
    for page_url, links in result.items():
        console.print(f"\n[bold cyan]Page:[/bold cyan] {page_url}")

        if links:
            console.print("[bold]Links found:[/bold]")
            for link in sorted(links):
                console.print(f"  • {link}")
        else:
            console.print("[italic]No links found on this page.[/italic]")

    console.print("=" * 80)

    # Format elapsed time
    minutes, seconds = divmod(int(elapsed_time), 60)
    time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    console.print(f"[bold green]Total pages crawled:[/bold green] {len(result)}")
    console.print(f"[bold green]Total crawling time:[/bold green] {time_str}")


def handle_missing_protocol_error(url: str) -> None:
    """
    Handle missing protocol error by providing helpful guidance.

    Args:
        url: The URL that caused the error
    """
    logger.error(f"Error: URL '{url}' is missing a protocol")
    console = Console()
    console.print(f"\n[bold red]Error:[/bold red] URL '{url}' is missing a protocol")
    console.print("\n[yellow]Hint:[/yellow] Try adding 'http://' or 'https://' to the beginning of your URL.")
    console.print(f"Example: 'https://{url}' instead of '{url}'")
    sys.exit(1)


def handle_invalid_protocol_error(error: InvalidProtocolError) -> None:
    """
    Handle invalid protocol error by providing helpful guidance.

    Args:
        error: The protocol error that occurred
    """
    logger.error(f"Error: {str(error)}")
    console = Console()
    console.print(f"\n[bold red]Error:[/bold red] {str(error)}")
    valid_protocols_str = ", ".join(f"'{p}'" for p in SUPPORTED_PROTOCOLS)
    console.print(f"\n[yellow]Hint:[/yellow] Only {valid_protocols_str} protocols are supported.")
    sys.exit(1)


def handle_url_error(error: InvalidURLError) -> None:
    """
    Handle URL error by providing helpful guidance.

    Args:
        error: The URL error that occurred
    """
    logger.error(f"Error: {str(error)}")
    console = Console()
    console.print(f"\n[bold red]Error:[/bold red] {str(error)}")
    console.print("\nPlease provide a valid URL in the format: https://example.com")
    sys.exit(1)


def handle_keyboard_interrupt(crawler_progress: CrawlerProgress) -> None:
    """
    Handle keyboard interrupt (Ctrl+C) gracefully.

    Args:
        crawler_progress: The progress tracker to stop
    """
    logger.info("Crawling interrupted by user.")
    crawler_progress.stop()
    console = Console()
    console.print("\n[yellow]Crawling interrupted by user.[/yellow]")
    sys.exit(1)


def handle_unexpected_error(error: Exception, crawler_progress: CrawlerProgress) -> None:
    """
    Handle unexpected errors by providing error information.

    Args:
        error: The unexpected error that occurred
        crawler_progress: The progress tracker to stop
    """
    logger.error(f"Unexpected error: {str(error)}")
    crawler_progress.stop()
    console = Console()
    console.print(f"\n[bold red]Unexpected error:[/bold red] {str(error)}")
    sys.exit(1)
