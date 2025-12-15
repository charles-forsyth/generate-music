import asyncio
import queue
import threading

import aioconsole
import numpy as np
import sounddevice as sd
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

class LiveDJ:
    def __init__(self, generator):
        self.generator = generator
        self.client = generator.client
        self.model_id = generator.settings.model_id
        self.is_running = False
        self.current_bpm = 120
        self.current_prompts = []
        
        # Audio config
        self.sample_rate = 48000
        self.channels = 2
        self.dtype = 'int16'
        
        # Jitter Buffer
        self.audio_queue = queue.Queue(maxsize=500) 
        self.buffer_threshold = 20 
        self.playback_started = threading.Event()

    async def start_session(self, initial_prompt: str = "ambient electronic"):
        """Starts the interactive music session."""
        self.is_running = True
        self.current_prompts = [types.WeightedPrompt(text=initial_prompt, weight=1.0)]
        self.playback_started.clear()
        
        # Enhanced Startup UI
        # Truncate prompt to prevent UI overflow and markup errors
        clean_prompt = initial_prompt.replace("\n", " ").strip()
        if len(clean_prompt) > 200:
            display_prompt = clean_prompt[:197] + "..."
        else:
            display_prompt = clean_prompt

        # Use Text object for safe rendering of variable content
        prompt_text = Text.assemble(
            ("Initial Prompt: ", "bold cyan"),
            (display_prompt, "white")
        )
        
        welcome_text = (
            f"{prompt_text.markup}\n"
            f"[bold cyan]BPM:[/bold cyan] {self.current_bpm}\n\n"
            "[bold white]Available Commands:[/bold white]\n"
            "• [green]add <text> [weight][/green] : Add layer (e.g. 'add drums')\n"
            "• [green]bpm <number>[/green]        : Change tempo (resets audio)\n"
            "• [green]list[/green]                : Show active prompts\n"
            "• [green]clear[/green]               : Remove all prompts\n"
            "• [green]quit[/green]                : Exit session\n\n"
            "   Use negative weight to remove elements (e.g. 'add drums -1.0').[/dim]"
            "   Use negative weight to remove elements (e.g. 'add drums -1.0').[/dim]"
        )
        
        console.print(Panel(
            welcome_text,
            title="[bold green]🎵 Gen-Music Live DJ Console 🎵[/bold green]",
            expand=False,
            border_style="green"
        ))
        
        console.print("[dim]Buffering audio stream...[/dim]")

        # Start Stream
        stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            latency='high',
            blocksize=2048
        )
        stream.start()

        try:
            async with (
                self.client.aio.live.music.connect(model=self.model_id) as session,
                asyncio.TaskGroup() as tg,
            ):
                # Task 1: Receive Audio (Producer)
                producer_task = tg.create_task(self._api_producer(session))
                
                # Task 2: Play Audio (Consumer - Threaded)
                asyncio.to_thread(self._audio_consumer)
                
                # Task 3: Handle Input
                input_task = tg.create_task(self._input_loop(session))

                # Initial Config
                await session.set_music_generation_config(
                    config=types.LiveMusicGenerationConfig(bpm=self.current_bpm)
                )
                await session.set_weighted_prompts(prompts=self.current_prompts)
                await session.play()
                
                # Main Loop
                while self.is_running:
                    await asyncio.sleep(0.1)
                
                # Cleanup
                producer_task.cancel()
                input_task.cancel()
                self.audio_queue.put(None) 

        except asyncio.CancelledError:
            pass
        except Exception as e:
            console.print(f"[red]Session Error:[/red] {e}")
        finally:
            stream.stop()
            stream.close()
            console.print("[yellow]Session Ended.[/yellow]")

    async def _api_producer(self, session):
        """Receives audio chunks from API and puts them in the queue."""
        try:
            async for message in session.receive():
                if not self.is_running:
                    break
                    
                if message.server_content and message.server_content.audio_chunks:
                    chunk_data = message.server_content.audio_chunks[0].data
                    if chunk_data:
                        audio_array = np.frombuffer(chunk_data, dtype=np.int16)
                        audio_array = audio_array.reshape(-1, 2)
                        
                        await asyncio.to_thread(self.audio_queue.put, audio_array)
                        
                        if not self.playback_started.is_set():
                            if self.audio_queue.qsize() >= self.buffer_threshold:
                                self.playback_started.set()
                                console.print("[bold green]▶ Now Playing[/bold green]")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            if self.is_running:
                console.print(f"[red]API Error:[/red] {e}")

    def _audio_consumer(self):
        """Reads from queue and writes to sounddevice (Blocking)."""
        self.playback_started.wait() 
        
        with sd.OutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            latency='high',
            blocksize=2048
        ) as stream:
            while self.is_running:
                try:
                    chunk = self.audio_queue.get(timeout=1.0)
                    if chunk is None:
                        break
                    stream.write(chunk)
                    self.audio_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    console.print(f"[red]Playback Error:[/red] {e}")
                    break

    async def _input_loop(self, session):
        """Reads user input asynchronously."""
        while self.is_running:
            try:
                line = await aioconsole.ainput("dj> ")
                await self._handle_command(session, line.strip())
            except (EOFError, asyncio.CancelledError):
                self.is_running = False
                break

    async def _handle_command(self, session, command: str):
        """Parses and executes DJ commands."""
        if not command:
            return
            
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("quit", "exit"):
            self.is_running = False
            
        elif cmd == "help":
            # Richer Help Table
            grid = Table(title="Live DJ Commands", border_style="cyan")
            grid.add_column("Command", style="green")
            grid.add_column("Arguments", style="yellow")
            grid.add_column("Description", style="white")
            
            grid.add_row("add", "text [weight]", "Add/Update layer (def 1.0)")
            grid.add_row("", "", "[dim]Ex: 'add drums 1.5' or 'add vocals -1.0'[/dim]")
            grid.add_row("bpm", "number", "Change tempo (resets stream)")
            grid.add_row("list", "", "Show active prompts")
            grid.add_row("clear", "", "Remove all prompts")
            grid.add_row("quit", "", "End session")
            
            console.print(grid)
            console.print(
                "\n[bold]Tips:[/bold]\n"
                "• Changes crossfade smoothly over a few seconds.\n"
                "• Changing BPM causes a hard reset (brief silence).\n"
                "• Use negative weights to suppress instruments."
            )

        elif cmd == "bpm":
            if args and args[0].isdigit():
                new_bpm = int(args[0])
                self.current_bpm = new_bpm
                console.print(
                    f"[yellow]Changing BPM to {new_bpm} (Resets Context)...[/yellow]"
                )
                await session.set_music_generation_config(
                    config=types.LiveMusicGenerationConfig(bpm=new_bpm)
                )
                await session.reset_context()

        elif cmd == "add":
            text = " ".join(args)
            weight = 1.0
            
            # Check for weight argument at the end
            last_arg = args[-1] if args else ""
            is_weight = False
            
            # Check positive float
            if last_arg.replace('.', '', 1).isdigit():
                is_weight = True
            # Check negative float
            elif last_arg.startswith('-'):
                # Split check to avoid long line
                if last_arg[1:].replace('.', '', 1).isdigit():
                    is_weight = True
                
            if is_weight:
                try:
                    weight = float(last_arg)
                    text = " ".join(args[:-1])
                except ValueError:
                    pass
            
            if text:
                self.current_prompts.append(
                    types.WeightedPrompt(text=text, weight=weight)
                )
                console.print(f"[green]Adding:[/green] '{text}' (weight: {weight})")
                await session.set_weighted_prompts(prompts=self.current_prompts)

        elif cmd == "clear":
            self.current_prompts = []
            console.print("[yellow]Prompts cleared.[/yellow]")
            await session.set_weighted_prompts(prompts=[])
            
        elif cmd == "list":
            table = Table(title="Active Prompts")
            table.add_column("Layer", style="cyan")
            table.add_column("Weight", style="magenta")
            for p in self.current_prompts:
                table.add_row(p.text, str(p.weight))
            console.print(table)
                
        else:
            console.print("[red]Unknown command. Type 'help' for list.[/red]")