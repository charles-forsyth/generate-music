import argparse
import asyncio
import os
import re
import subprocess
import sys
import warnings
from datetime import datetime
from pathlib import Path

# Suppress pydub SyntaxWarnings in Python 3.12+
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")

# ruff: noqa: E402
from rich.console import Console
from rich.table import Table

from .core import MusicGenerator
from .utils import add_to_history, convert_audio, load_history, play_audio

console = Console()


def show_history():
    """Show command history."""
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


def init_config():
    """Initialize configuration directory and .env file."""
    config_dir = Path.home() / ".config" / "gen-music"
    config_dir.mkdir(parents=True, exist_ok=True)
    env_file = config_dir / ".env"

    if env_file.exists():
        console.print(f"[yellow]Configuration already exists at {env_file}[/yellow]")
        return

    content = (
        "# Gen-Music Configuration\n"
        "PROJECT_ID=your-google-cloud-project-id\n"
        "LOCATION=us-central1\n"
        "MODEL_ID=models/lyria-realtime-exp\n"
        "# Optional: Only required if not using 'gcloud auth application-default'\n"
        "# GOOGLE_API_KEY=your-api-key\n"
    )

    try:
        env_file.write_text(content)
        # Set permissions to read/write only for the user (600)
        env_file.chmod(0o600)
        console.print(f"[green]Created configuration at {env_file}[/green]")
        console.print(
            f"Please edit [bold]{env_file}[/bold] with your Google Cloud details."
        )
    except Exception as e:
        console.print(f"[red]Failed to create configuration: {e}[/red]")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate music using Google's Vertex AI Lyria model."
    )
    parser.add_argument(
        "prompt", nargs="?", help="The text prompt for the music."
    )
    parser.add_argument(
        "-o", "--output", help="Output filename."
    )
    parser.add_argument(
        "-d", "--duration", type=int, default=10, help="Duration in seconds."
    )
    parser.add_argument(
        "--bpm", type=int, default=120, help="Beats per minute."
    )
    parser.add_argument(
        "-p", "--play", action="store_true", help="Play immediately after generation."
    )
    parser.add_argument(
        "--history", action="store_true", help="Show command history."
    )
    parser.add_argument(
        "--rerun", type=int, help="Rerun a history item by ID."
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize configuration in ~/.config/gen-music/",
    )
    parser.add_argument(
        "-f", "--format", choices=["wav", "mp3"], default="wav", help="Output format."
    )
    parser.add_argument(
        "-b", "--background", action="store_true", help="Run in background."
    )

    args = parser.parse_args()

    # Init Command
    if args.init:
        init_config()
        return

    # History Command
    if args.history:
        show_history()
        return

    # Background Execution Logic
    if args.background:
        # Reconstruct the command without the --background flag
        cmd = [sys.executable, "-m", "gen_music.cli"] + [
            arg for arg in sys.argv[1:] if arg not in ("-b", "--background")
        ]
        
        console.print("[green]Launching generation in background...[/green]")
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return

    # Handle Rerun Logic or New Prompt
    prompt = args.prompt

    if args.rerun is not None:
        history = load_history()
        if not history or not (1 <= args.rerun <= len(history)):
            console.print(
                f"[red]Invalid history ID. Choose between 1 and {len(history)}.[/red]"
            )
            sys.exit(1)
        entry = history[args.rerun - 1]
        prompt = entry.get("prompt")
        console.print(
            f"[yellow]Rerunning history item {args.rerun}: '{prompt}'[/yellow]"
        )

    if not prompt:
        parser.error("the following arguments are required: prompt")

    # Default Output Filename
    output_file = args.output
    if not output_file:
        output_dir = os.path.join(os.path.expanduser("~"), "Music")
        os.makedirs(output_dir, exist_ok=True)

        sane_prompt = re.sub(r"[^a-zA-Z0-9_]+", "_", prompt)
        prompt_part = (
            "_".join(sane_prompt.split("_")[:5]).strip("_") or "generated_music"
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Always generate initially as wav, convert later if needed
        output_file = os.path.join(output_dir, f"{prompt_part}_{timestamp}.wav")

    # Generate
    generator = MusicGenerator()
    try:
        asyncio.run(
            generator.generate(
                prompt=prompt,
                output_file=output_file,
                duration=args.duration,
                bpm=args.bpm,
            )
        )
    except Exception as e:
        console.print(f"[red]Error during generation:[/red] {e}")
        # Hint at configuration if authentication fails
        if "401" in str(e) or "credentials" in str(e).lower():
            console.print(
                "\n[yellow]Tip: Run 'gen-music --init' to set up credentials.[/yellow]"
            )
        sys.exit(1)

    # Convert if requested
    final_output = output_file
    if args.format == "mp3":
        final_output = convert_audio(output_file, "mp3")

    # Save History
    add_to_history(
        {
            "prompt": prompt,
            "output_file": final_output,
            "duration": args.duration,
            "bpm": args.bpm,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Play
    if args.play:
        play_audio(final_output)


if __name__ == "__main__":
    main()