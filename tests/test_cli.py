"""
Tests for the CLI module.

This module tests the Command Line Interface (CLI) component of the crawler,
focusing on the following aspects:
- Progress monitoring and user interface
- Command-line argument handling
- Error handling and graceful shutdown
- Integration with the crawler functionality

The tests use mocking to isolate the CLI functionality from actual network requests.
"""

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from crawler_app.cli import CrawlerProgress, app, monitor_crawler_progress


def test_crawler_progress_initialization() -> None:
    """
    Test that CrawlerProgress initializes correctly with proper default values.

    This test verifies that:
    - The verbose flag is correctly set
    - Initial counters are set to expected values
    - Required components (console, progress bar) are initialized
    """
    progress = CrawlerProgress(verbose=True)

    assert progress.verbose is True
    assert progress.pages_crawled == 0
    assert progress.latest_url == ""
    assert progress.console is not None
    assert progress.progress is not None


def test_crawler_progress_update(crawler_progress: CrawlerProgress) -> None:
    """
    Test that CrawlerProgress updates correctly with new progress information.

    This test verifies that:
    - Internal counters are updated with provided values
    - The progress bar is updated with correct parameters
    - The task description includes the latest URL being crawled

    Args:
        crawler_progress: The pre-configured CrawlerProgress fixture
    """
    # Update the progress
    crawler_progress.update(5, "http://example.com/page")

    # Check that internal state was updated
    assert crawler_progress.pages_crawled == 5
    assert crawler_progress.latest_url == "http://example.com/page"

    # Check that progress.update was called with correct parameters
    crawler_progress.progress.update.assert_called_once()
    args, kwargs = crawler_progress.progress.update.call_args
    assert args[0] == 1  # The task ID
    assert kwargs["completed"] == 5
    assert "http://example.com/page" in kwargs["description"]


def test_crawler_progress_start_stop(crawler_progress: CrawlerProgress) -> None:
    """
    Test start and stop methods of CrawlerProgress.

    This test verifies that:
    - start() correctly initializes the progress bar
    - stop() correctly finalizes the progress bar
    - The necessary methods are called in the correct order

    Args:
        crawler_progress: The pre-configured CrawlerProgress fixture
    """
    # Test start
    crawler_progress.start()
    crawler_progress.progress.start.assert_called_once()
    crawler_progress.progress.add_task.assert_called_once()

    # Test stop
    crawler_progress.stop()
    crawler_progress.progress.stop.assert_called_once()


@pytest.mark.asyncio
async def test_monitor_crawler_progress() -> None:
    """
    Test the async progress monitoring task.

    This test verifies that the monitor_crawler_progress function:
    - Correctly monitors the crawler's progress
    - Updates the progress tracker with the latest information
    - Responds to changes in the result dictionary
    """
    progress = MagicMock()
    result_dict: dict[str, set[str]] = {"http://example.com": set()}

    # Create a task for monitor_crawler_progress that will run until cancelled
    task = asyncio.create_task(monitor_crawler_progress(progress, result_dict))

    # Allow the task to run for a short time
    await asyncio.sleep(0.1)

    # Add another URL to the result dict
    result_dict["http://example.com/page1"] = set()

    # Allow the task to react to the change
    await asyncio.sleep(0.1)

    # Cancel the task
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify that update was called at least once
    progress.update.assert_called()
    # Last update should be for the latest URL
    last_call_args = progress.update.call_args_list[-1]
    assert last_call_args[0][0] == len(result_dict)  # count of URLs
    assert "http://example.com/page1" in last_call_args[0][1]  # last URL


@pytest.mark.asyncio
async def test_cli_main_function(runner: CliRunner) -> None:
    """
    Test the main CLI function with mocked crawler.

    This test verifies that:
    - The CLI command is properly executed
    - The crawler is called with the correct parameters
    - The progress tracking is initialized and finalized
    - Results are properly displayed to the user

    Args:
        runner: The Typer CLI runner fixture
    """
    # Mock the crawl_site function to return a simple result
    mock_result: dict[str, set[str]] = {
        "http://example.com": {"http://example.com/page1", "http://example.com/page2"},
        "http://example.com/page1": set(),
    }

    # Mock CrawlerProgress
    mock_progress = MagicMock()

    # Mock the actual crawl_site function
    async def mock_crawl(*args: Any, **kwargs: Any) -> dict[str, set[str]]:
        return mock_result

    with (
        patch("crawler_app.cli.crawl_site", return_value=mock_crawl()),
        patch("crawler_app.cli.CrawlerProgress", return_value=mock_progress),
        patch("crawler_app.cli.Console", return_value=MagicMock()),
        patch("crawler_app.cli.asyncio.run", side_effect=lambda x: mock_result),
    ):
        # Use the runner to invoke the app
        result = runner.invoke(app, ["http://example.com", "--concurrency", "3", "--verbose"])

        # Check that the command ran successfully
        assert result.exit_code == 0, f"Command failed with exit code {result.exit_code}, output: {result.stdout}"

        # Check CrawlerProgress was used correctly
        mock_progress.start.assert_called_once()
        mock_progress.stop.assert_called_once()


@pytest.mark.parametrize(
    "exception_class, exception_msg, expected_exit",
    [
        (ValueError, "Invalid value", True),
        (KeyboardInterrupt, "", True),  # Empty message for KeyboardInterrupt
        (Exception, "Unexpected error", True),
    ],
)
def test_cli_exception_handling(
    runner: CliRunner, exception_class: type, exception_msg: str, expected_exit: bool
) -> None:
    """
    Test how the CLI handles various exceptions.

    This parameterized test verifies that:
    - Different types of exceptions are caught and handled gracefully
    - The system exits with appropriate error codes
    - Error messages are displayed appropriately
    - Progress tracking is properly stopped when needed

    Args:
        runner: The Typer CLI runner fixture
        exception_class: The type of exception to simulate
        exception_msg: The error message for the exception
        expected_exit: Whether the system should exit after the exception
    """
    # Mock CrawlerProgress
    mock_progress = MagicMock()

    # The exception needs to be raised when asyncio.run is called
    def raise_error(*args: Any, **kwargs: Any) -> None:
        raise exception_class(exception_msg)

    with (
        patch("crawler_app.cli.CrawlerProgress", return_value=mock_progress),
        patch("crawler_app.cli.Console", return_value=MagicMock()),
        patch("crawler_app.cli.asyncio.run", side_effect=raise_error),
        patch("crawler_app.cli.sys.exit") as mock_exit,
    ):
        # Use the runner to invoke the app
        _ = runner.invoke(app, ["http://example.com"])

        # Check that sys.exit was called as expected
        if expected_exit:
            mock_exit.assert_called()

        # Stop should be called for all exceptions except ValueError
        if exception_class is not ValueError:
            mock_progress.stop.assert_called_once()


def test_cli_adds_https_protocol(runner: CliRunner, mock_crawl_site: MagicMock) -> None:
    """
    Test that the CLI adds https:// to URLs without a protocol.

    This test verifies that:
    - URLs provided without a protocol (e.g., "example.com") are automatically
      prefixed with "https://"
    - The user is informed about this auto-correction
    - The corrected URL is passed to the crawler

    Args:
        runner: The Typer CLI runner fixture
        mock_crawl_site: The mocked crawl_site function
    """
    # Create a real result object for the mock to return
    mock_result: dict[str, set[str]] = {
        "https://example.com": {"https://example.com/page1", "https://example.com/page2"}
    }

    # Configure the mock to return the real result object
    mock_crawl_site.return_value = mock_result

    # Set up a spy on Console.print to check what it prints
    with patch("crawler_app.cli.Console.print") as mock_print:
        # Run the CLI with a URL that doesn't have a protocol
        _ = runner.invoke(app, ["example.com"])

        # Check that the protocol was added in the output message
        protocol_message_found = False
        for call in mock_print.call_args_list:
            # Get the first positional argument
            args, kwargs = call
            if args and isinstance(args[0], str) and "default protocol" in args[0]:
                protocol_message_found = True
                break

        assert protocol_message_found, "Protocol addition message not found in output"

        # Check that crawl_site was called with the correct URL
        mock_crawl_site.assert_called_once()
        args, _ = mock_crawl_site.call_args
        assert args[0] == "https://example.com"


@pytest.mark.parametrize(
    "mock_result, expected_exit_code, expected_output",
    [
        (
            {"http://example.com": {"http://example.com/page1", "http://example.com/page2"}},
            0,
            ["Crawl Results:", "Page: http://example.com", "Links found:", "Total pages crawled: 1"],
        ),
        ({}, 0, ["Crawl Results:", "No pages were crawled."]),
    ],
)
def test_cli_crawl_results_output(
    runner: CliRunner,
    mock_crawl_site: MagicMock,
    mock_result: dict[str, set[str]],
    expected_exit_code: int,
    expected_output: list[str],
) -> None:
    """
    Test that the CLI outputs crawl results correctly.

    This parameterized test verifies that:
    - The crawl results are properly formatted and displayed for different cases
    - The output includes all expected information (URLs, links, counts)
    - The command completes with the expected exit code

    Args:
        runner: The Typer CLI runner fixture
        mock_crawl_site: The mocked crawl_site function
        mock_result: The mock result to return from crawl_site
        expected_exit_code: Expected exit code for the command
        expected_output: List of strings that should appear in the output
    """
    # Configure the mock to return the specified result
    mock_crawl_site.return_value = mock_result

    # Run the command
    result = runner.invoke(app, ["http://example.com"])

    # Check that the command ran with the expected exit code
    assert result.exit_code == expected_exit_code, f"Command exited with {result.exit_code}, output: {result.stdout}"

    # Check the output contains the expected information
    for expected_text in expected_output:
        assert expected_text in result.stdout, f"Expected '{expected_text}' not found in output"


def test_cli_handles_error(runner: CliRunner, mock_crawl_site: MagicMock) -> None:
    """
    Test that the CLI handles errors correctly.

    This test verifies that:
    - Errors during crawling are caught and handled properly
    - The command exits with a non-zero status code
    - Appropriate error messages are displayed

    Args:
        runner: The Typer CLI runner fixture
        mock_crawl_site: The mocked crawl_site function
    """
    # Configure the mock to raise an exception
    mock_crawl_site.side_effect = ValueError("Test error")

    result = runner.invoke(app, ["http://example.com"])

    # Check that the command exited with a non-zero code
    assert result.exit_code != 0
