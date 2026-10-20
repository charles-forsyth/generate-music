# Gen-Music CLI

![CI](https://github.com/charles-forsyth/generate-music/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![License](https://img.shields.io/github/license/charles-forsyth/generate-music)

**Gen-Music** (`v0.3.1`) is a CLI for generating instrumental music with Google's **Lyria** models:
- `lyria-3-clip-preview` for clips up to 30 s (returns ~30 s, ~$0.04),
- `lyria-3.5` for full-length tracks (`--duration > 30`, ~$0.08), and
- `models/lyria-realtime-exp` for interactive `--live` DJ sessions.

See [SPEC.md](SPEC.md) for the full system specification, architecture, model routing, and requirement traceability.

## Installation

### Prerequisites
- **ffmpeg / ffprobe** on `PATH` (`brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Linux).
- **Python 3.12** recommended for prebuilt `pygame` wheels.

### Install via `uv`

```bash
uv tool install --python 3.12 git+https://github.com/charles-forsyth/generate-music.git
```

## Configuration

Initialize `~/.config/gen-music/.env`:

```bash
gen-music --init
```

Edit `~/.config/gen-music/.env` (chmod `0600`) to set your Gemini API key (restricted to `generativelanguage.googleapis.com`):

```env
SONG_MODEL_ID=auto
GOOGLE_API_KEY=your_gemini_api_key_here
```

## Usage

### 1. Generate a 30s Clip (`lyria-3-clip-preview`)
```bash
gen-music "Warm acoustic fingerstyle guitar, calm morning" -d 10 -f wav -o morning.wav
```

### 2. Generate a Full-Length Track (`lyria-3.5`)
```bash
gen-music "Cinematic ambient synthwave with driving bass" -d 90 --bpm 110 -o synthwave.mp3
```

### 3. Prompt Optimization (`--optimize`)
Rewrite a short idea into a rich instrumental arrangement using `gemini-3.8-flash` before generating:
```bash
gen-music "upbeat coding background track" --optimize --temp
```

### 4. Interactive Live Session (`--live`)
```bash
gen-music "Lo-fi chill beats" --live
```

### 5. History & Replay
```bash
gen-music --history
gen-music --rerun 1
```

## Options Reference

| Option | Description | Default |
| :--- | :--- | :--- |
| `prompt` | Text prompt for the music (or pipe via `stdin`). | — |
| `-o`, `--output FILE` | Output filename (auto-generated via Gemini slug if omitted). | Auto |
| `-d`, `--duration SEC` | Target duration in seconds (`<=30` uses Lyria 3 Clip; `>30` uses Lyria 3.5). | `10` |
| `--bpm INT` | Beats per minute. | `120` |
| `-f`, `--format {wav,mp3}` | Output audio container format. | `mp3` |
| `--optimize` | Rewrite prompt into an instrumental producer prompt via `gemini-3.8-flash`. | `False` |
| `-p`, `--play` | Play audio immediately after generation. | `False` |
| `--temp` | Generate to a temporary file, play once, and delete. | `False` |
| `-b`, `--background` | Run generation in a background daemon process. | `False` |
| `--history` | Show prompt history (`~/.music_history.json`). | — |
| `--rerun ID` | Re-run a prompt from history by 1-based ID. | — |
| `--live` | Start an interactive real-time Lyria DJ session. | `False` |
| `--init` | Initialize `~/.config/gen-music/.env`. | — |

## Development

```bash
uv sync --python 3.12
uv run --python 3.12 pytest
```

## License

MIT License. See [LICENSE](LICENSE) for details.
