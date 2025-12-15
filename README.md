# Generate Music CLI

A modern, professional CLI tool for generating music using Google's Vertex AI Lyria model (RealTime API).

## Features

- **RealTime Music Generation**: Uses the latest Lyria RealTime API for low-latency generation.
- **Robust CLI**: Built with `typer` and `rich` for a great user experience.
- **Configuration**: Securely manages credentials via `.env` files.
- **Reproducible**: Built with `uv` and `pyproject.toml`.

## Installation

```bash
# Install directly from Git using uv
uv tool install git+https://github.com/charles-forsyth/generate-music.git
```

## Usage

```bash
# Generate a track
gen-music generate "An epic orchestral soundtrack" --duration 30

# View history
gen-music history
```

## Development

1.  Clone the repo.
2.  Install dependencies: `uv sync`
3.  Run tests: `uv run pytest`
