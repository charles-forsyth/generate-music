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

# Suppress warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")
warnings.filterwarnings("ignore", module="google.genai")

# ruff: noqa: E402
from .core import MusicGenerator
from .utils import add_to_history, convert_audio, load_history, play_audio

# Global state for cleanup
CURRENT_OUTPUT_FILE = None
IS_TEMP_MODE = False
GENERATION_COMPLETE = False


def cleanup_handler():
    """Handles file cleanup on exit."""
    global CURRENT_OUTPUT_FILE, IS_TEMP_MODE, GENERATION_COMPLETE
    
    if not CURRENT_OUTPUT_FILE or not os.path.exists(CURRENT_OUTPUT_FILE):
        return

    if IS_TEMP_MODE or not GENERATION_COMPLETE:
        try:
            os.remove(CURRENT_OUTPUT_FILE)
        except OSError:
            pass


def signal_handler(sig, frame):
    """Handles Ctrl+C gracefully."""
    sys.stderr.write("\nStopped by user.\n")
    cleanup_handler()
    sys.exit(0)


# Register handlers
atexit.register(cleanup_handler)
signal.signal(signal.SIGINT, signal_handler)


def show_history():
    """Show command history."""
    history_data = load_history()
    if not history_data:
        print("No history found.")
        return

    print("Generation History:")
    print("ID  | Prompt")
    print("----|-------")
    for i, entry in enumerate(history_data):
        prompt = entry.get("prompt", "N/A")
        print(f"{i+1:<3} | {prompt}")


def init_config():
    """Initialize configuration directory and .env file."""
    config_dir = Path.home() / ".config" / "gen-music"
    config_dir.mkdir(parents=True, exist_ok=True)
    env_file = config_dir / ".env"

    if env_file.exists():
        sys.stderr.write(f"Configuration already exists at {env_file}\n")
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
        sys.stderr.write(f"Created configuration at {env_file}\n")
    except Exception as e:
        sys.stderr.write(f"Failed to create configuration: {e}\n")
        sys.exit(1)


async def async_main(args):
    """Async entry point for the CLI logic."""
    global CURRENT_OUTPUT_FILE, IS_TEMP_MODE, GENERATION_COMPLETE

    try:
        generator = MusicGenerator()
    except Exception as e:
        sys.stderr.write(f"Initialization Error: {e}\n")
        if "credentials" in str(e).lower():
             sys.stderr.write("Tip: Run 'gen-music --init'\n")
        sys.exit(1)

    # Live Mode
    if args.live:
        try:
            from .live import LiveDJ
            prompt = args.prompt or "ambient electronic"
            
            if args.optimize:
                try:
                    prompt = await generator.smart.optimize_prompt(prompt)
                except Exception:
                    pass

            dj = LiveDJ(generator)
            await dj.start_session(initial_prompt=prompt)
            return
        except ImportError as e:
            sys.stderr.write("Live mode requires extra dependencies.\n")
            sys.stderr.write(f"Error: {e}\n")
            return

    # Handle Input (Arg vs Pipe)
    prompt = args.prompt
    
    if not prompt and not sys.stdin.isatty():
        try:
            prompt = sys.stdin.read().strip()
        except Exception:
            pass

    # Rerun Logic
    if args.rerun is not None:
        history = load_history()
        if not history or not (1 <= args.rerun <= len(history)):
            sys.stderr.write(
                f"Invalid history ID. Choose between 1 and {len(history)}.\n"
            )
            sys.exit(1)
        entry = history[args.rerun - 1]
        prompt = entry.get("prompt")
        # Status silenced

    if not prompt:
        sys.stderr.write("Error: No prompt provided via argument or pipe.\n")
        sys.exit(1)

    # Smart Prompt Optimization (Silent)
    final_prompt = prompt
    if args.optimize:
        try:
            final_prompt = await generator.smart.optimize_prompt(prompt)
        except Exception:
            pass

    # Determine Output Filename
    if args.temp:
        IS_TEMP_MODE = True
        args.play = True
        tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tf.close()
        output_file = tf.name
    else:
        output_file = args.output
        if not output_file:
            output_dir = os.path.join(os.path.expanduser("~"), "Music")
            os.makedirs(output_dir, exist_ok=True)
            
            try:
                slug = await generator.smart.generate_filename_slug(final_prompt)
            except Exception:
                slug = "generated_music"
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"{slug}_{timestamp}.wav")

    CURRENT_OUTPUT_FILE = output_file
    
    # Generate
    try:
        await generator.generate(
            prompt=final_prompt,
            output_file=output_file,
            duration=args.duration,
            bpm=args.bpm,
        )
        GENERATION_COMPLETE = True
    except Exception as e:
        sys.stderr.write(f"Error during generation: {e}\n")
        sys.exit(1)

    # Convert
    final_output = output_file
    if args.format == "mp3":
        final_output = convert_audio(output_file, "mp3")
        if IS_TEMP_MODE or not GENERATION_COMPLETE:
             if output_file != final_output and os.path.exists(output_file):
                 os.remove(output_file)
        CURRENT_OUTPUT_FILE = final_output

    # History
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

    # Only print filename to stdout
    print(os.path.basename(final_output))

    if args.play:
        play_audio(final_output)


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

    # Sync commands
    if args.init:
        init_config()
        return

    if args.history:
        show_history()
        return

    if args.background:
        cmd = [sys.executable, "-m", "gen_music.cli"] + [
            arg for arg in sys.argv[1:] if arg not in ("-b", "--background")
        ]
        # Silent launch
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return

    # Run Async Main Loop
    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()