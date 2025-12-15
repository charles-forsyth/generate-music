import json
import os
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from pydub import AudioSegment

HISTORY_FILE = ".music_history.json"


def play_audio(file_path: str):
    """Plays an audio file using pygame."""
    try:
        import pygame
    except ImportError:
        print("\nError: The 'pygame' library is required to play audio.")
        print("Please install it using: pip install pygame")
        return

    # Suppress pygame welcome message
    with redirect_stdout(None):
        pygame.init()
        pygame.mixer.init()

    print(f"Playing {file_path}...")
    try:
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    except pygame.error as e:
        print(f"\nError playing audio with pygame: {e}")
    finally:
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
    # Simple duplicate check based on exact match of entry
    if entry not in history:
        history.append(entry)
        save_history(history)

def convert_audio(input_path: str, output_format: str = "mp3") -> str:
    """Converts audio file to the specified format using pydub."""
    if output_format == "wav":
        return input_path

    path = Path(input_path)
    output_path = path.with_suffix(f".{output_format}")
    
    print(f"Converting to {output_format}...")
    try:
        audio = AudioSegment.from_wav(str(path))
        audio.export(str(output_path), format=output_format)
        # Optionally remove the original wav if not requested? 
        # For safety we keep it or we can delete it. 
        # Let's keep it simple: Return the new path.
        return str(output_path)
    except Exception as e:
        print(f"Error converting audio: {e}")
        return input_path
