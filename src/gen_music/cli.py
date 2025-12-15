import argparse
import asyncio
import atexit
import os
import signal
import subprocess
import sys
import tempfile
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

# Create console for stderr (logs/status)
console = Console(stderr=True)

# Global state for cleanup
CURRENT_OUTPUT_FILE = None
IS_TEMP_MODE = False
GENERATION_COMPLETE = False


def cleanup_handler():
    """Handles file cleanup on exit."""
    global CURRENT_OUTPUT_FILE, IS_TEMP_MODE, GENERATION_COMPLETE
    
    if not CURRENT_OUTPUT_FILE or not os.path.exists(CURRENT_OUTPUT_FILE):
        return

    # Delete if it's a temp run OR if generation was interrupted (partial file)
    if IS_TEMP_MODE or not GENERATION_COMPLETE:
        try:
            os.remove(CURRENT_OUTPUT_FILE)
        except OSError:
            pass


def signal_handler(sig, frame):
    """Handles Ctrl+C gracefully."""
    console.print("\n[yellow]Stopped by user.[/yellow]")
    cleanup_handler()
    sys.exit(0)


# Register handlers
atexit.register(cleanup_handler)
signal.signal(signal.SIGINT, signal_handler)


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
        env_file.chmod(0o600)
        console.print(f"[green]Created configuration at {env_file}[/green]")
        console.print(
            f"Please edit [bold]{env_file}[/bold] with your Google Cloud details."
        )
    except Exception as e:
        console.print(f"[red]Failed to create configuration: {e}[/red]")
        sys.exit(1)

def main():
    global CURRENT_OUTPUT_FILE, IS_TEMP_MODE, GENERATION_COMPLETE

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
        "-f", "--format", choices=["wav", "mp3"], default="mp3", help="Output format."
    )
    parser.add_argument(
        "-b", "--background", action="store_true", help="Run in background."
    )
    parser.add_argument(
        "--optimize", action="store_true", help="Use Gemini to optimize the prompt."
    )
    parser.add_argument(
        "--temp",
        action="store_true",
        help="Generate a temporary file, play it, and delete it.",
    )
    parser.add_argument(
        "--live", action="store_true", help="Start an interactive live DJ session."
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

    # Initialize Generator
    try:
        generator = MusicGenerator()
    except Exception as e:
        console.print(f"[red]Initialization Error:[/red] {e}")
        if "credentials" in str(e).lower():
             console.print("[yellow]Tip: Run 'gen-music --init'[/yellow]")
        sys.exit(1)

    # Live Mode
    if args.live:
        try:
            from .live import LiveDJ
            prompt = args.prompt or "ambient electronic"
            
            # Optimize prompt if requested
            if args.optimize:
                console.print("[cyan]✨ Optimizing Live DJ prompt...[/cyan]")
                try:
                    prompt = asyncio.run(generator.smart.optimize_prompt(prompt))
                    console.print(f"[dim]Optimized: {prompt}[/dim]")
                except Exception as e:
                    console.print(f"[red]Optimization failed: {e}[/red]")

            dj = LiveDJ(generator)
            asyncio.run(dj.start_session(initial_prompt=prompt))
            return
        except ImportError as e:
            console.print("[red]Live mode requires extra dependencies.[/red]")
            console.print(f"Error: {e}")
            return

    # Handle Input (Arg vs Pipe)
    prompt = args.prompt
    
    if not prompt and not sys.stdin.isatty():
        try:
            prompt = sys.stdin.read().strip()
        except Exception:
            pass

    # Rerun Logic overrides prompt
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
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(1)
        else:
            console.print("[red]Error: No prompt provided via argument or pipe.[/red]")
            sys.exit(1)

    # Smart Prompt Optimization
    final_prompt = prompt
    if args.optimize:
        console.print("[cyan]✨ Optimizing prompt with Gemini...[/cyan]")
        try:
            final_prompt = asyncio.run(generator.smart.optimize_prompt(prompt))
        except Exception as e:
            console.print(f"[red]Optimization failed, using original:[/red] {e}")

    # Determine Output Filename
    # Temp Mode Logic
    if args.temp:
        IS_TEMP_MODE = True
        args.play = True # Force play
        
        # Create a temp file path (we close the handle so other libs can use it)
        tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tf.close()
        output_file = tf.name
    else:
        # Normal Mode Logic
        output_file = args.output
        if not output_file:
            output_dir = os.path.join(os.path.expanduser("~"), "Music")
            os.makedirs(output_dir, exist_ok=True)
            
            try:
                slug = asyncio.run(generator.smart.generate_filename_slug(final_prompt))
            except Exception:
                slug = "generated_music"
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"{slug}_{timestamp}.wav")

    # Set Global state for cleanup
    CURRENT_OUTPUT_FILE = output_file

    console.print("[green]Generating music...[/green]")
    
    # Generate
    try:
        asyncio.run(
            generator.generate(
                prompt=final_prompt,
                output_file=output_file,
                duration=args.duration,
                bpm=args.bpm,
            )
        )
        GENERATION_COMPLETE = True
    except Exception as e:
        console.print(f"[red]Error during generation:[/red] {e}")
        sys.exit(1)

    # Convert if requested (Default MP3)
    final_output = output_file
    if args.format == "mp3":
        final_output = convert_audio(output_file, "mp3")
        # Update cleanup target to new file
        if IS_TEMP_MODE or not GENERATION_COMPLETE:
             if output_file != final_output and os.path.exists(output_file):
                 os.remove(output_file)
                 
        CURRENT_OUTPUT_FILE = final_output

    # Save History (Skip for temp?)
    if not args.temp:
        add_to_history(
            {
                "prompt": prompt,
                "optimized_prompt": final_prompt if args.optimize else None,
                "output_file": final_output,
                "duration": args.duration,
                "bpm": args.bpm,
                "timestamp": datetime.now().isoformat(),
            }
        )

    # Output filename
    print(os.path.basename(final_output))

    # Play
    if args.play:
        play_audio(final_output)


if __name__ == "__main__":
    main()