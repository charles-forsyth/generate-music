import asyncio
import queue
import threading

import aioconsole
import numpy as np
import sounddevice as sd
from google.genai import types


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
        
        # Simple Text UI
        print("\n=== Gen-Music Live DJ Console ===")
        print(f"Initial Prompt: {initial_prompt}")
        print(f"BPM: {self.current_bpm}")
        print("---------------------------------")
        print("Commands:")
        print("  add <text> [weight]  : Add layer")
        print("  bpm <number>         : Change tempo")
        print("  list                 : Show prompts")
        print("  clear                : Clear prompts")
        print("  quit                 : Exit")
        print("---------------------------------")
        print("Buffering audio stream...\n")

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
                # Correctly schedule the threaded consumer
                # We assign to a var to prevent GC but we don't access it
                tg.create_task(asyncio.to_thread(self._audio_consumer))
                
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
                # Stop consumer loop by sending sentinel
                self.audio_queue.put(None) 

        except asyncio.CancelledError:
            pass
        except Exception as e:
            if self.is_running:
                print(f"Session Error: {e}")
        finally:
            stream.stop()
            stream.close()
            print("\nSession Ended.")

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
                                print("▶ Now Playing")

        except asyncio.CancelledError:
            pass
        except Exception:
            pass

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
                except Exception:
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
            print("Commands:")
            print("  add <text> [weight]  : Add layer")
            print("  bpm <number>         : Change tempo")
            print("  list                 : Show prompts")
            print("  clear                : Clear prompts")
            print("  quit                 : Exit")

        elif cmd == "bpm":
            if args and args[0].isdigit():
                new_bpm = int(args[0])
                self.current_bpm = new_bpm
                print(f"Changing BPM to {new_bpm} (Resets Context)...")
                await session.set_music_generation_config(
                    config=types.LiveMusicGenerationConfig(bpm=new_bpm)
                )
                await session.reset_context()

        elif cmd == "add":
            text = " ".join(args)
            weight = 1.0
            
            last_arg = args[-1] if args else ""
            is_weight = False
            
            if last_arg.replace('.', '', 1).isdigit():
                is_weight = True
            elif last_arg.startswith('-'):
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
                print(f"Adding: '{text}' (weight: {weight})")
                await session.set_weighted_prompts(prompts=self.current_prompts)

        elif cmd == "clear":
            self.current_prompts = []
            print("Prompts cleared.")
            await session.set_weighted_prompts(prompts=[])
            
        elif cmd == "list":
            print("Active Prompts:")
            for i, p in enumerate(self.current_prompts):
                print(f"  {i+1}. {p.text} ({p.weight})")
                
        else:
            print("Unknown command. Type 'help' for list.")
