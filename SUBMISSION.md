# Zego Web Crawler Project Submission

## 1. Project Overview

This project implements a performant web crawler designed to efficiently traverse websites within a single domain, following specific requirements and constraints.

### Problem Statement

> Create a Python CLI application that crawls a website starting from a base URL, processing only the specified domain (not subdomains), and outputting each page URL along with all URLs found on that page.

### Key Task Requirements & Personal Objectives

- Implement a command-line Python crawler that processes a single domain
- Print each crawled URL and all links found on that page
- Optimise for speed without sacrificing accuracy or resource efficiency
- Avoid using tools like Scrapy or Playwright
- Handle errors gracefully
- Implement DRY business logic ideal for TDD
- Apply modular code structuring ideal for future improvements

## 2. Solution Overview

The solution is a Python CLI application built with a modular architecture to ensure strong maintainability and testability. The project structure emphasises separation of concerns and follows object-oriented programming principles.

### Project Structure

```
.
├── crawler_app/
│   ├── __init__.py         # Package initialisation
│   ├── __main__.py         # Entry point for module execution
│   ├── cli.py              # Command-line interface implementation
│   ├── constants.py        # Application-wide constants
│   ├── crawler.py          # Core crawler engine
│   ├── exceptions.py       # Custom exception classes
│   ├── parser.py           # HTML parsing functionality
│   └── utils.py            # Utility functions for URL handling and HTTP requests
├── tests/
│   ├── conftest.py         # Test fixtures and configuration
│   ├── test_cli.py         # CLI tests
│   ├── test_crawler.py     # Crawler engine tests
│   ├── test_parser.py      # HTML parser tests
│   └── test_utils.py       # Utility function tests
└── Makefile                # Convenience commands for development and execution
```

### Environment and Setup

This project uses Poetry (v2) for dependency management and environment setup, providing reproducible builds and easy management of Python dependencies. A Makefile is included for convenient command execution.

```bash
# Initialise your environment
poetry shell

# Install dependencies
poetry install
```

#### Key Makefile Commands

- `make run url=example.com`: Run the crawler with the specified URL
- `make test`: Run the test suite
- `make cov`: Run tests with coverage reporting

### Sample Flow

```bash
# Initialise your environment
poetry shell && poetry install
OR
make install

# Basic usage (protocol will default to HTTPS if not provided)
python -m crawler_app example.com
OR
make run url=example.com

# With additional options
python -m crawler_app example.com --concurrency 10 --verbose
OR
make run url=example.com -- --concurrency 10 --verbose
```

> **NOTE**: Some websites may have many links to crawl. Press `Ctrl+C` to stop the crawler early and print the links crawled up to that point.

## 3. Design Approach

### Architectural Overview

The crawler is built with a modular architecture that clearly separates concerns:

```
┌─────────────────────┐
│  Command Line       │
│  Interface (cli.py) │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│  Crawler Engine     │
│  (crawler.py)       │
└─────────┬───────────┘
          │
┌─────────▼───────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  URL Processing     │     │  HTML Parsing       │     │  Error Handling     │
│  (utils.py)         │◄────┤  (parser.py)        │─────►  (exceptions.py)    │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

This architecture enables:

- Clear separation of responsibilities
- Ease of testing individual components
- Flexibility for future enhancements
- Maintainable and readable codebase

### Key Design Attributes

- **Asynchronous**: Non-blocking, concurrent I/O operations for improved performance for network-heavy operations
- **Worker Pool Pattern**: Multiple concurrent workers process URLs from a shared queue
- **Producer-Consumer Pattern**: The crawler adds URLs to a queue that workers consume
- **Facade Pattern**: Crawler engine abstracts complex internal logic behind a simple interface
- **State Management**: Encapsulates and manages crawler's internal state for more predictable and simpler state tracking
- **Error Handling**: Comprehensive error management and validation preventing unexpected failures and provides clear error information
- **Resource Management**: Efficient resource allocation and cleanup, such as using context managers, Semaphore for controlling concurrency and graceful cancellation handling to prevent resource leaks and ensures clean shutdown.
- **Configuration Control**: Flexible configuration with sensible defaults for concurrency, timeout and max pages, configurable through constructor for easy customisation with minimal setup
- **Composition over Inheritance**: Favours object composition by breaking complex logic into focused methods, where each method has a single responsibility making the solution more flexible and easier to maintain design

## 4. Technical Implementation

### Core Components

1. **CLI Interface (`cli.py`)**: Processes command-line arguments, displays real-time progress, and handles interruptions using Rich for visualisation.

2. **Crawler Engine (`crawler.py`)**: Manages async crawling with worker tasks, URL queue, concurrency control, and domain boundary enforcement.

3. **URL Processing (`utils.py`)**: Handles URL normalisation, domain validation, HTTP requests/responses, and error management.

4. **HTML Parser (`parser.py`)**: Extracts links from HTML content using BeautifulSoup, filters by protocol, and resolves relative URLs.

### Algorithm Details

The crawler implements a breadth-first approach using `asyncio`:

1. Initialise with a base URL, add it to the work queue
2. Spawn concurrent worker tasks
3. Workers fetch pages, extract links, and add valid same-domain URLs to the queue
4. Track visited URLs to prevent cycles
5. Process until the queue is empty or maximum pages limit is reached

### Performance Optimisations

- **Connection Pooling**: Reuses HTTP connections via httpx
- **Efficient Data Structures**: Uses sets for lightweight lookup of visited URLs
- **Minimal Memory Footprint**: Processes HTML without storing full content
- **Configurable Concurrency**: Adjustable parallelism to balance throughput and load

### Error Handling

The crawler implements robust error handling through custom exceptions, graceful failure recovery, timeout management, and content validation, ensuring the process continues despite encountering problematic pages.

### Key Optimisations & Edge Case Handling

- **URL Handling**: Normalises URLs, removes fragments, handles relative paths
- **Domain Boundary**: Correctly identifies same-domain URLs with port and protocol variations
- **Graceful Error Recovery**: Continues processing despite network errors or malformed HTML
- **Resource Management**: Controls memory usage through queue management and efficient data structures
- **URL Variations**: Handling URLs with/without trailing slashes, fragments, query parameters
- **Malformed HTML**: Robust parsing of incomplete or non-standard HTML
- **Redirect Chains**: Following redirects while maintaining domain boundaries

### Progress Reporting

The crawler provides real-time progress visualisation using the Rich library:

- **Live Status**: Shows the current URL being processed
- **Activity Indicator**: Displays a spinner during crawling
- **Statistics**: Updates metrics for pages crawled and links found
- **Summary**: Shows total pages, links, and duration upon completion

This visual feedback allows users to monitor the crawling process and gain insights into the website structure as it's being explored rather than sitting idle waiting for it to finish.

## 5. Workflow & Development Environment

The development followed a structured, iterative approach combining research, testing, and continuous refinement:

### Development Approach

- **Research**: Investigated web crawling best practices and concurrency patterns
- **Architecture**: Designed modular components with clear boundaries
- **Test-Driven**: Wrote tests alongside implementation for high coverage
- **Iterative**: Built MVP first, then incrementally improved functionality

### Tools & Technologies

- **IDE & Assistance**: Cursor IDE with Claude 3.7 Sonnet
- **Environment**: Poetry for dependency management, Makefile for commands
- **Quality Assurance**: Type annotations, runtime type checking with Typeguard, Ruff
- **Key Libraries**: httpx, BeautifulSoup4, asyncio, Typer with Rich, pytest

### Elaboration on AI Tool Usage

#### Initial Research for Theoretical Foundation

AI tools like ChatGPT and Grok were instrumental in rapidly synthesizing complex technical research. They helped quickly distill fundamental theories and best practices in:

- Web crawling architectures
- Concurrent programming techniques, such as leveraging the 'Semaphore' for constraining concurrency
- Python asynchronous development strategies
- Performance optimization for network-intensive applications

This research phase provided a structured approach to understanding the technical challenges and potential solution strategies before writing a single line of code.

#### Iterative Development with Test-Driven Methodology

After implementing the raw baseline solution, AI tools (Cursor IDE with Claude 3.7 Sonnet) enhanced the solution through a structured, test-driven approach:

- Generated comprehensive test cases and identified exhaustive edge case scenarios
- Supported progressive code refinement and high test coverage
- Helped refine algorithms to be as lean and DRY as possible whilst maintaining readibility and modularity
- Helped maintain high-quality and comprehensive code documentation through comments for improving readability fellow engineers

#### Scaffolding Boilerplate

Leveraged AI to speed up development when implementing generic boilerplate code which is still essential for the solution. For example, it was used to rapidly implement the CLI application to achieve the desired UX whilst making iterative improvements to ensure compatability with async data processing, allowing us to see logs during the process across all workers. In time-constrained scenarios such as this, this proves invaluable to allow more time to be spent on the real business logic.

## 6. Testing Strategy

The project maintains good test coverage (>80%) through a multi-layered approach:

### Testing Approach

- **Unit Tests**: Isolated component testing with extensive mocking and parameterisation
- **Integration Tests**: Verifies component interactions with mock HTTP clients
- **Edge Case Coverage**: Special handling for URL variations, errors, and boundary conditions through exhaustive pytest parameterization technique

Key test modules focus on specific components (`test_utils.py`, `test_parser.py`, `test_crawler.py`), ensuring each module's functionality is thoroughly verified both in isolation and integration.

## 7. Performance Analysis

### Crawling Efficiency Metrics

The performance of crawlers is generally optimised around several key metrics which we aligned our solution with:

- **Pages per Second**: Maximising the number of pages processed per unit time
- **Resource Utilisation**: Keeping CPU and memory usage within reasonable bounds
- **Response to Latency**: Gracefully handling slow-responding pages without blocking others
- **Time to Completion**: Minimising overall crawl time for a given site

### Memory Management

Memory efficiency is achieved through:

- **Streaming Processing**: Processing HTML without storing complete page content
- **Minimal State**: Storing only essential information (URLs and links)
- **Reference-Based Storage**: Using sets and dictionaries for efficient lookups
- **Queue Management**: Processing items in batches to control memory growth

### URL Processing Optimisation

Several techniques optimise URL handling:

- **Early Filtering**: Checking domain boundaries before queuing
- **Normalisation**: Converting URLs to a standard form to avoid duplicates
- **Efficient Comparison**: O(1) lookups for visited URL checks
- **Protocol Awareness**: Handling HTTP and HTTPS URLs appropriately

### Concurrency Model

```
┌───────────────────┐
│ Main Crawler Task │
└─────────┬─────────┘
          │ spawns
          ▼
┌───────────────────┐     controls     ┌───────────────┐
│ Worker Tasks      │◄────────────────►│ URL Queue     │
└─────────┬─────────┘                  └───────────────┘
          │ use
          ▼
┌───────────────────┐
│ Semaphore         │ limits concurrent operations
└───────────────────┘
```

The crawler uses an asynchronous approach to maximise throughput:

- **Asyncio**: Leverages Python's asyncio for non-blocking I/O operations
- **Semaphore Control**: Limits the number of concurrent requests to avoid overwhelming target servers and local sockets
- **Work Queue**: Efficiently distributes crawling tasks among workers
- **Deduplication**: Uses efficient data structures (sets) to track visited URLs and avoid duplicate requests

### Concurrency Plateau Effect

When increasing concurrency, performance improvements follow a plateau curve:

```
Performance
    │   ┌─────────▲─────────────────────
    │   │         │
    │   │         │  Plateau region
    │   │         │
    │  ┌┴─────────┘
    │  │
    │  │  Steep improvement region
    │ ┌┘
    │ │
    └─┴───────────────────────────────► Concurrency
        Optimal
        range
```

This plateau occurs due to several factors:

1. **Network and Server Limits**:

   - Bandwidth saturation
   - Server-side rate limiting
   - Remote server processing capacity

2. **Local System Constraints**:

   - Ephemeral port exhaustion
   - Socket/file descriptor limits
   - asyncio scheduling overhead

3. **CPU-bound Processing**:
   - Python's Global Interpreter Lock (GIL) limits true parallelism
   - HTML parsing and URL processing becomes a bottleneck

The crawler's configurable concurrency allows tuning to find the optimal point before diminishing returns, typically between 5-20 concurrent requests depending on the target server.

## 8. Future Enhancements

While the current implementation provides a solid foundation, several enhancements would elevate this crawler if we had the time and opportunity to do so:

### Core Functionality Extensions

1. **Robots.txt Support**: Adding respect for website crawling policies
2. **Politeness Controls**: Implementing configurable delays between requests
3. **Depth Control**: Adding crawl depth constraints would provide more focused exploration of specific sections of websites
4. **Proxy Support**: Enabling the use of proxies for crawling with production-ready features such as IP rotation
5. **JavaScript Rendering**: Supporting JavaScript-rendered content using headless browsers
6. **Rate Limiting**: Intelligent throttling with configurable delay strategies would enable respectful crawling of even sensitive sites
7. **Retry Logic**: Better tolerance of potentially temporary error responses to avoid losing data, utilising standard timing techniques such as exponential backoff for targeted error response codes

### Scaling Considerations

For handling larger crawling tasks, such as multi-domain:

- **Distributed Crawling**: Implementing a distributed architecture using message queues
- **Persistent Storage**: Adding database integration for storing crawl results
- **Incremental Crawling**: Supporting resumable crawls with state persistence for long-running tasks

### Architectural Evolution

Other approaches that could be considered for evolving the solution into something more production ready:

- **Distributed Architecture**: Implementing a distributed design would enable large-scale crawling across multiple machines.
- **API Interface**: Adding a RESTful API would make the crawler serviceable to other applications.
- **Persistent Storage**: Integrating database storage would allow for incremental crawling and result preservation, as well as result exploration.

(Assuming we wouldn't be making use of existing production-scale crawling frameworks)
