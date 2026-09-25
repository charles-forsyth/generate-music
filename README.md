# 🎵 Gen-Music CLI

![CI](https://github.com/charles-forsyth/generate-music/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![License](https://img.shields.io/github/license/charles-forsyth/generate-music)
![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)

**Gen-Music** is a CLI for generating music with Google's **Lyria** models: `lyria-3.5` for full-length tracks, `lyria-3-clip-preview` for clips up to 30 s (Clip always returns ~30 s), and `lyria-realtime-exp` for the interactive `--live` DJ mode. Set `SONG_MODEL_ID` (default `auto`) and `LIVE_MODEL_ID` in `~/.config/gen-music/.env`.

## 🚀 Installation

### Using `uv` (Recommended)

```bash
uv tool install git+https://github.com/charles-forsyth/generate-music.git
```

## 🛠️ Configuration

After installation, initialize the configuration to set up your credentials:

```bash
gen-music --init
```

This creates a configuration file at `~/.config/gen-music/.env`. Edit it to add your **Google Cloud Project ID**.

## 🎹 Usage

**Generate a Track:**
```bash
gen-music "An epic orchestral soundtrack with swelling strings"
```

**Options:**
*   `--duration, -d`: Length in seconds (default: 10).
*   `--bpm`: Beats per minute (default: 120).
*   `--play, -p`: Play immediately after generation.

**View History:**
```bash
gen-music --history
```

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md).

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.