import asyncio
import queue

import aioconsole
import numpy as np
import sounddevice as sd
from google.genai import types
from rich.console import Console
from rich.panel import Panel

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
        
        # Thread-safe queue for audio buffering
        self.audio_queue = queue.Queue(maxsize=100) 

    def _audio_callback(self, outdata, frames, time, status):
        """Callback for sounddevice to pull audio from queue."""
        if status:
            pass

        try:
            # We fetch from queue. If queue is empty, we write silence.
            # But the queue contains chunks of X size, and callback needs Y size.
            outdata.fill(0)
        except queue.Empty:
            outdata.fill(0)

    async def start_session(self, initial_prompt: str = "ambient electronic"):
        """Starts the interactive music session."""
        self.is_running = True
        self.current_prompts = [types.WeightedPrompt(text=initial_prompt, weight=1.0)]
        
        console.print(Panel(
            f"[bold green]Starting Live DJ Session[/bold green]\n"
            f"Initial Prompt: {initial_prompt}\n"
            "Type 'help' for commands, 'quit' to exit.",
            expand=False
        ))

        # We use a blocking OutputStream with a larger blocksize/latency setting
        # to allow for network jitter.
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
                # Task 1: Receive Audio & Play (Producer)
                audio_task = tg.create_task(self._audio_loop(session, stream))
                
                # Task 2: Handle User Input
                input_task = tg.create_task(self._input_loop(session))

                # Initial Config
                await session.set_music_generation_config(
                    config=types.LiveMusicGenerationConfig(bpm=self.current_bpm)
                )
                await session.set_weighted_prompts(prompts=self.current_prompts)
                await session.play()
                
                # Wait for quit signal
                while self.is_running:
                    await asyncio.sleep(0.1)
                
                # Cleanup tasks upon clean exit
                audio_task.cancel()
                input_task.cancel()

        except asyncio.CancelledError:
            pass # Clean exit
        except Exception as e:
            console.print(f"[red]Session Error:[/red] {e}")
        finally:
            stream.stop()
            stream.close()
            console.print("[yellow]Session Ended.[/yellow]")

    async def _audio_loop(self, session, stream):
        """Receives audio chunks and writes to sounddevice stream."""
        try:
            loop = asyncio.get_running_loop()
            
            async for message in session.receive():
                if not self.is_running:
                    break
                    
                if message.server_content and message.server_content.audio_chunks:
                    chunk_data = message.server_content.audio_chunks[0].data
                    if chunk_data:
                        # Process audio in a thread executor to avoid blocking
                        # the asyncio loop. stream.write is blocking.
                        audio_array = np.frombuffer(chunk_data, dtype=np.int16)
                        audio_array = audio_array.reshape(-1, 2)
                        
                        # Run blocking write in executor
                        await loop.run_in_executor(None, stream.write, audio_array)
                        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if self.is_running:
                console.print(f"[red]Audio Error:[/red] {e}")

    async def _input_loop(self, session):
        """Reads user input asynchronously."""
        while self.is_running:
            try:
                # Use a separate thread for input to avoid blocking
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
            console.print(
                "[bold]Commands:[/bold]\n"
                "  [cyan]add <text> [weight][/cyan]  - Add/Update a prompt\n"
                "  [cyan]bpm <number>[/cyan]        - Change tempo (resets context)\n"
                "  [cyan]clear[/cyan]               - Clear all prompts\n"
                "  [cyan]list[/cyan]                - Show active prompts\n"
                "  [cyan]quit[/cyan]                - Stop session"
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
            if args and args[-1].replace('.', '', 1).isdigit():
                try:
                    weight = float(args[-1])
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
            
        elif cmd == "list":
            for i, p in enumerate(self.current_prompts):
                console.print(f"{i+1}. {p.text} ({p.weight})")
                
        else:
            console.print("[red]Unknown command.[/red]")