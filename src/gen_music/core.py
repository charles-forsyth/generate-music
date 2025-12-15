import asyncio
import wave
from typing import Optional

from google import genai
from google.genai import types

from .config import get_settings


class MusicGenerator:
    def __init__(self):
        self.settings = get_settings()

        # Logic to choose between API Key (Google AI) and ADC (Google Cloud Vertex AI)
        if self.settings.google_api_key:
            # Use Google AI API (AI Studio)
            self.client = genai.Client(
                api_key=self.settings.google_api_key,
                http_options={"api_version": "v1alpha"},
            )
        elif self.settings.project_id:
            # Use Google Cloud Vertex AI
            self.client = genai.Client(
                vertexai=True,
                project=self.settings.project_id,
                location=self.settings.location,
                http_options={"api_version": "v1alpha"},
            )
        else:
            raise ValueError(
                "Invalid Configuration: You must provide either a GOOGLE_API_KEY "
                "or a PROJECT_ID in your .env configuration."
            )

    async def generate(
        self,
        prompt: str,
        output_file: str,
        duration: int = 10,
        bpm: int = 120,
        temperature: float = 1.0,
        negative_prompt: Optional[str] = None,
    ):
        """
        Generates music using the Lyria RealTime model.

        Args:
            prompt: Text description of the music.
            output_file: Path to save the WAV file.
            duration: Duration in seconds.
            bpm: Beats per minute.
            temperature: Creativity control.
            negative_prompt: (Currently unused for RealTime API).
        """

        # Audio configuration
        CHANNELS = 2
        SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
        FRAME_RATE = 48000

        print(f"Starting generation: '{prompt}' for {duration}s at {bpm} BPM...")

        async def receive_audio(session, wave_file):
            """Background task to receive and write audio."""
            total_bytes = 0
            target_bytes = duration * FRAME_RATE * CHANNELS * SAMPLE_WIDTH

            try:
                while True:
                    async for message in session.receive():
                        if (
                            message.server_content
                            and message.server_content.audio_chunks
                        ):
                            chunk = message.server_content.audio_chunks[0].data
                            if chunk:
                                wave_file.writeframes(chunk)
                                total_bytes += len(chunk)
                                # Simple progress indicator
                                print(".", end="", flush=True)

                                if total_bytes >= target_bytes:
                                    return

                    await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                pass

        # Prepare wave file
        with wave.open(output_file, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(FRAME_RATE)

            async with (
                self.client.aio.live.music.connect(
                    model=self.settings.model_id
                ) as session,
                asyncio.TaskGroup() as tg,
            ):
                # Start receiver
                receiver_task = tg.create_task(receive_audio(session, wf))

                # Send configuration
                await session.set_music_generation_config(
                    config=types.LiveMusicGenerationConfig(
                        bpm=bpm, temperature=temperature
                    )
                )

                # Send prompt
                # If we had multiple, we could list them. Using single prompt for now.
                await session.set_weighted_prompts(
                    prompts=[
                        types.WeightedPrompt(text=prompt, weight=1.0),
                    ]
                )

                # Start playing
                await session.play()

                # Wait for the duration (managed by the receiver task checking bytes,
                # but we also need to wait here or just wait on the receiver task?)
                # The receiver task returns when done.
                await receiver_task

                # Stop session
                # await session.stop() # Implicitly handled by context manager
                print(f"\nGeneration complete! Saved to {output_file}")
