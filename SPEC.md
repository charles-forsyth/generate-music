# gen-music specification

Version 0.3.1 (2026-10-20; code 0.3.1). Owner: Chuck Forsyth.
Repository: `charles-forsyth/generate-music` (local checkout `~/Projects/Gen-Music-IVXX`). License: MIT.

## 1. Purpose and scope

`gen-music` is a Python CLI for generating instrumental music and running interactive live DJ sessions with Google's **Lyria** model family via the `google-genai` SDK:
- **Lyria 3 Clip (`lyria-3-clip-preview`)** — generates ~30-second instrumental music clips (selected automatically when `--duration <= 30`).
- **Lyria 3.5 (`lyria-3.5`)** — generates full-length multi-minute tracks (selected automatically when `--duration > 30`).
- **Lyria RealTime (`models/lyria-realtime-exp`)** — bidirectional streaming WebSocket session (`--live`) for real-time interactive music generation with live prompt steering and BPM control.
- **Gemini 3.8 Flash (`gemini-3.8-flash`)** — used by `SmartAssistant` to generate safe filename slugs from prompts and to rewrite user prompts into rich instrumental producer prompts when `--optimize` is passed.

Mirage (`~/Projects/mirage`) shells out to `gen-music` to create background music beds for its `hybrid`, `weather`, `research`, and `news-short` modes.

## 2. Design decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Automatic model routing (`SONG_MODEL_ID=auto`) | Requests with `--duration <= 30` route to `lyria-3-clip-preview` (~$0.04/clip); requests with `--duration > 30` route to `lyria-3.5` (~$0.08/track). Users can override via `SONG_MODEL_ID` in `~/.config/gen-music/.env`. |
| D2 | Up to 3 retries on empty Lyria responses | Lyria occasionally returns an empty response without audio parts when a prompt brushes against vocal/lyric safety filters. `generate_music_Sync()` retries up to 3 times with a clear error message on exhaustion. |
| D3 | Container auto-detection via `ffprobe` | Lyria returns MP3 or WAV bytes in `part.inline_data`. `gen-music` inspects the returned stream with `ffprobe` (`ffmpeg` package) and converts or trims via `ffmpeg` when the user requests `-f wav` or `-f mp3`. |
| D4 | Instrumental-only prompt optimization (`SmartAssistant.optimize_prompt`) | Lyria rejects vocal/lyric requests. `--optimize` instructs `gemini-3.8-flash` to focus strictly on instruments, mood, tempo, genre, and texture without vocals or lyrics. |

## 3. Architecture

```text
gen-music CLI (src/gen_music/cli.py)
  |-- get_settings() (src/gen_music/config.py)
  |     `-- ~/.config/gen-music/.env (GOOGLE_API_KEY, SONG_MODEL_ID, LIVE_MODEL_ID)
  |-- Mode selection (cli.py)
  |     |-- `--init` -> creates ~/.config/gen-music/.env
  |     |-- `--history` / `--rerun ID` -> reads ~/.music_history.json
  |     |-- `--live` -> LiveSession (src/gen_music/live.py, lyria-realtime-exp + pyaudio/pygame)
  |     `-- Standard generation -> generate_music_Sync() (src/gen_music/core.py)
  `-- Synthesis & post-processing (core.py)
        |-- genai.Client(api_key=GOOGLE_API_KEY) (or Vertex AI fallback)
        |-- SmartAssistant (gemini-3.8-flash):
        |     |-- optimize_prompt() (if --optimize)
        |     `-- generate_filename_slug() (if -o omitted)
        |-- Model selection: duration <= 30 -> lyria-3-clip-preview, else lyria-3.5
        |-- client.models.generate_content(..., response_modalities=["AUDIO"]) (up to 3 retries)
        |-- ffprobe / ffmpeg format conversion (MP3 <-> WAV)
        `-- Optional playback via pygame (`--play` / `--temp`)
```

### Module map

| File | Responsibility |
|---|---|
| `src/gen_music/cli.py` | Argument parser, `--init`, `--history`, `--rerun`, `--background` daemon fork, `--temp`, `--play`, entry point `main()`. |
| `src/gen_music/config.py` | `Settings` (`pydantic-settings`), `get_settings()` loading `~/.config/gen-music/.env` and `./.env`. |
| `src/gen_music/core.py` | `SmartAssistant` (`gemini-3.8-flash`), `generate_music()` / `generate_music_Sync()`, Lyria model routing, retry loop, `ffprobe`/`ffmpeg` transcoding. |
| `src/gen_music/live.py` | Interactive `--live` DJ mode over `client.aio.live.music.connect(model=settings.live_model_id)`. |
| `src/gen_music/utils.py` | Prompt history persistence (`~/.music_history.json`) and audio playback helpers. |

## 4. Configuration (`~/.config/gen-music/.env`)

| Variable | Field | Default | Description |
|---|---|---|---|
| `GOOGLE_API_KEY` | `settings.google_api_key` | `None` | Gemini API key restricted to `generativelanguage.googleapis.com`. |
| `PROJECT_ID` | `settings.project_id` | `None` | GCP project ID for Vertex AI fallback when `GOOGLE_API_KEY` is unset. |
| `LOCATION` | `settings.location` | `"us-central1"` | GCP region for Vertex AI fallback. |
| `SONG_MODEL_ID` | `settings.song_model_id` | `"auto"` | `"auto"` (`lyria-3-clip-preview` for `<=30s`, `lyria-3.5` for `>30s`) or explicit model ID. |
| `LIVE_MODEL_ID` | `settings.live_model_id` | `"models/lyria-realtime-exp"` | Model ID for `--live` interactive streaming mode. |

## 5. CLI interface

```text
gen-music [prompt]
          [-o OUTPUT | --output OUTPUT]
          [-d DURATION | --duration DURATION]   # default: 10 (<=30s uses Lyria 3 Clip)
          [--bpm BPM]                           # default: 120
          [-p | --play]
          [--history]
          [--rerun ID]
          [--init]
          [-f {wav,mp3} | --format {wav,mp3}]   # default: mp3 (or inferred from -o)
          [-b | --background]
          [--optimize]
          [--temp]
          [--live]
```

Runtime dependency requirements:
- Requires `ffmpeg` and `ffprobe` on `PATH` (`/opt/homebrew/bin/ffprobe` on macOS) for inspecting and converting returned audio streams.
- Requires Python 3.12 (`uv tool install --python 3.12`) for prebuilt `pygame` wheels.

## 6. Cost model

| Tier | Model | Typical duration | List price (USD) |
|---|---|---|---|
| Clip (`-d <= 30`) | `lyria-3-clip-preview` | ~30 s | ~$0.04 / request |
| Full track (`-d > 30`) | `lyria-3.5` | 60–180 s | ~$0.08 / request |
| Prompt optimization (`--optimize`) | `gemini-3.8-flash` | — | <$0.001 / call |

## 7. Requirements traceability

| ID | Requirement | Verified by |
|---|---|---|
| REQ-CLI-1 | Basic prompt generation invokes `generate_music_Sync` with default duration (`10`) and BPM (`120`). | `tests/test_cli.py::test_generate_command` |
| REQ-CLI-2 | Output format defaults to `mp3` when `--format` is omitted. | `tests/test_cli.py::test_mp3_default` |
| REQ-CLI-3 | Prompt can be piped via non-TTY `stdin` when positional `prompt` is omitted. | `tests/test_cli.py::test_piped_input` |
| REQ-CORE-1 | `SmartAssistant` generates sanitized lowercase filename slugs and instrumental-only optimized prompts. | `tests/test_core.py` |

## 8. Known gaps and backlog

- **K1 (Confirmed):** `lyria-3-clip-preview` always returns a ~30.7-second clip regardless of `-d 10`; `gen-music` writes the full ~30.7-second clip rather than trimming to `-d` seconds with `ffmpeg -t <duration>`. Downstream callers like Mirage trim/loop the clip themselves during mixdown.
- **K2 (Confirmed):** `get_settings()` loads both `~/.config/gen-music/.env` and `./.env` (if present in cwd); removing `./.env` from the lookup path would match `generate-gemini-voice`'s strict single-file isolation.
