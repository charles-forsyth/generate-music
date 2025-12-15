import json
import os
import sys
from contextlib import contextmanager
from typing import Any

from pydub import AudioSegment

HISTORY_FILE = ".music_history.json"


@contextmanager
def suppress_stdout_stderr():
    """A context manager that redirects stdout and stderr to devnull."""
    with open(os.devnull, "w") as fnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = fnull
        sys.stderr = fnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


def play_audio(file_path: str):
    """Plays an audio file using pygame."""
    try:
        # Redirect stdout/stderr to suppress pygame welcome message effectively
        with suppress_stdout_stderr():
            import pygame
            pygame.init()
            pygame.mixer.init()
            
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
    except ImportError:
        # We can't print error to stdout if we want strict silence for piping.
        # Print to actual stderr if needed, or fail silently?
        # Let's print to original stderr.
        sys.stderr.write("\nError: The 'pygame' library is required to play audio.\n")
        return
    except Exception as e:
        sys.stderr.write(f"\nError playing audio: {e}\n")
        return

    # Wait for playback
    try:
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    except KeyboardInterrupt:
        pass
    finally:
        with suppress_stdout_stderr():
            pygame.mixer.quit()
            pygame.quit()


def load_history() -> list[dict[str, Any]]:
    """Loads the prompt history from the history file."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_history(history: list[dict[str, Any]]):
    """Saves the prompt history to the history file."""
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)


def add_to_history(entry: dict[str, Any]):
    """Adds a new entry to history."""
    history = load_history()
    if entry not in history:
        history.append(entry)
        save_history(history)


def convert_audio(input_path: str, output_format: str = "mp3") -> str:
    """Converts audio file to the specified format using pydub."""
    if output_format == "wav":
        return input_path

    # Check if pydub/ffmpeg is silenced?
    # We rely on CLI to handle status messages.
    # pydub itself doesn't print much unless error.
    
    from pathlib import Path
    path = Path(input_path)
    output_path = path.with_suffix(f".{output_format}")
    
    try:
        audio = AudioSegment.from_wav(str(path))
        audio.export(str(output_path), format=output_format)
        return str(output_path)
    except Exception as e:
        sys.stderr.write(f"Error converting audio: {e}\n")
        return input_path