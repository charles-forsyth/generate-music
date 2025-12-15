import asyncio
import json
import os
import re
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from .core import MusicGenerator
from .utils import add_to_history, load_history, play_audio

app = typer.Typer(help="Generate music using Google's Vertex AI Lyria model.")
console = Console()


@app.command()
def generate(
    prompt: Annotated[
        str, typer.Argument(help="The text prompt for the music.")
    ],
    output_file: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output filename."),
    ] = None,
    duration: Annotated[
        int, typer.Option("--duration", "-d", help="Duration in seconds.")
    ] = 10,
    bpm: Annotated[
        int, typer.Option(help="Beats per minute.")
    ] = 120,
    play: Annotated[
        bool,
        typer.Option("--play", "-p", help="Play immediately after generation."),
    ] = False,
    rerun: Annotated[
        Optional[int], typer.Option(help="Rerun a history item by ID.")
    ] = None,
):
    """
    Generate music from a text prompt.
    """

    # Handle Rerun Logic
    if rerun is not None:
        history = load_history()
        if not history or not (1 <= rerun <= len(history)):
            console.print(
                f"[red]Invalid history ID. Choose between 1 and {len(history)}.[/red]"
            )
            raise typer.Exit(code=1)
        entry = history[rerun - 1]
        prompt = entry.get("prompt", prompt)
        # We can override other params if passed, or use history defaults.
        # For simplicity, we stick to the prompt from history, but current CLI args for others.
        console.print(f"[yellow]Rerunning history item {rerun}: '{prompt}'[/yellow]")

    # Default Output Filename
    if not output_file:
        output_dir = os.path.join(os.path.expanduser("~"), "Music")
        os.makedirs(output_dir, exist_ok=True)

        sane_prompt = re.sub(r"[^a-zA-Z0-9_]+", "_", prompt)
        prompt_part = (
            "_".join(sane_prompt.split("_")[:5]).strip("_") or "generated_music"
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"{prompt_part}_{timestamp}.wav")

    # Generate
    generator = MusicGenerator()
    try:
        asyncio.run(
            generator.generate(
                prompt=prompt, output_file=output_file, duration=duration, bpm=bpm
            )
        )
    except Exception as e:
        console.print(f"[red]Error during generation:[/red] {e}")
        raise typer.Exit(code=1) from e

    # Save History
    add_to_history(
        {
            "prompt": prompt,
            "output_file": output_file,
            "duration": duration,
            "bpm": bpm,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Play
    if play:
        play_audio(output_file)


@app.command()
def history():
    """
    Show command history.
    """
    history_data = load_history()
    if not history_data:
        console.print("No history found.")
        return

    table = Table(title="Generation History")
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Prompt", style="magenta")
    table.add_column("File", style="green")
    table.add_column("Date", style="blue")

    for i, entry in enumerate(history_data):
        table.add_row(
            str(i + 1),
            entry.get("prompt", "N/A"),
            os.path.basename(entry.get("output_file", "N/A")),
            entry.get("timestamp", "N/A"),
        )

    console.print(table)


if __name__ == "__main__":
    app()