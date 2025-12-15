# Contributing to Gen-Music

First off, thanks for taking the time to contribute! 🎉

The following is a set of guidelines for contributing to Gen-Music. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Development Setup

This project uses [`uv`](https://github.com/astral-sh/uv) for dependency management and packaging.

1.  **Clone the repository**
    ```bash
    git clone https://github.com/charles-forsyth/generate-music.git
    cd generate-music
    ```

2.  **Install dependencies**
    ```bash
    uv sync
    ```

3.  **Run Tests**
    ```bash
    uv run pytest
    ```

4.  **Linting**
    ```bash
    uv run ruff check .
    ```

## Submitting a Pull Request

1.  Fork the repo and create your branch from `main`.
2.  If you've added code that should be tested, add tests.
3.  Ensure the test suite passes (`uv run pytest`).
4.  Make sure your code lints (`uv run ruff check .`).
5.  Issue that pull request!

## Code Style

*   We use `ruff` for linting and formatting.
*   We use strict type hints where possible.
*   We use `pytest` for testing.
