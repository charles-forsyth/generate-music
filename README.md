# 🎵 Gen-Music CLI

![CI](https://github.com/charles-forsyth/generate-music/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![License](https://img.shields.io/github/license/charles-forsyth/generate-music)
![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)

**Gen-Music** is a modern, professional command-line interface (CLI) for generating high-quality music in real-time using Google's state-of-the-art **Vertex AI Lyria model**.

Built with a focus on developer experience, reliability, and ease of use.

## ✨ Features

- **🚀 RealTime Generation**: Leverages the Lyria RealTime API for low-latency, streaming audio generation.
- **🎧 Immediate Playback**: Optionally play generated tracks instantly using `pygame`.
- **📜 History Tracking**: Automatically saves prompts and file locations for easy retrieval and playback.
- **🔧 Configurable**: Securely manages credentials via environment variables or `.env` files.
- **📦 Modern Stack**: Built with `typer`, `rich`, `uv`, and `pydantic-settings`.

## 🚀 Installation

### Using `uv` (Recommended)

You can install `gen-music` globally with a single command:

```bash
uv tool install git+https://github.com/charles-forsyth/generate-music.git
```

### From Source

1.  Clone the repository:
    ```bash
    git clone https://github.com/charles-forsyth/generate-music.git
    cd generate-music
    ```
2.  Install dependencies:
    ```bash
    uv sync
    ```

## 🛠️ Configuration

You need a Google Cloud Project with the Vertex AI API enabled.

1.  **Project ID**: Your GCP Project ID.
2.  **Authentication**: Use `gcloud auth application-default login` (Recommended) OR set `GOOGLE_API_KEY`.

**Example `~/.config/gen-music/.env`:**
```env
PROJECT_ID=your-project-id
LOCATION=us-central1
MODEL_ID=models/lyria-realtime-exp
```

## 🎹 Usage

**Generate a Track:**
```bash
gen-music generate "An epic orchestral soundtrack with swelling strings" --duration 30
```

**Options:**
*   `--duration, -d`: Length in seconds (default: 10).
*   `--bpm`: Beats per minute (default: 120).
*   `--play, -p`: Play immediately after generation.

**View History:**
```bash
gen-music history
```

**Rerun a Previous Track:**
```bash
gen-music generate --rerun 1
```

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md).

1.  Fork the repo.
2.  Create a feature branch (`git checkout -b feature/amazing-feature`).
3.  Commit your changes.
4.  Push to the branch.
5.  Open a Pull Request.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.