import asyncio
import wave
from typing import Optional

from google import genai
from google.genai import types

from .config import get_settings


class SmartAssistant:
    """Helper class to use Gemini Flash for text tasks."""
    
    def __init__(self, client: genai.Client):
        self.client = client
        self.model_id = "models/gemini-2.0-flash-exp"

    async def generate_filename_slug(self, prompt: str) -> str:
        """Generates a safe, short filename slug from the prompt."""
        try:
            # Construct prompt for filename generation
            contents = (
                "Generate a short, lowercase, underscore-separated filename slug "
                "(max 5 words, no extension) for a music file described as: "
                f"'{prompt}'. Output ONLY the slug."
            )
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=contents,
            )
            slug = response.text.strip().lower()
            # Basic sanitization
            return "".join(c for c in slug if c.isalnum() or c == "_")
        except Exception as e:
            # Fallback if Gemini fails
            print(f"Smart filename generation failed: {e}")
            return "generated_music"

    async def optimize_prompt(self, prompt: str) -> str:
        """Rewrites the prompt to be more descriptive for a music model."""
        try:
            # Construct prompt for optimization
            contents = (
                "You are an expert music producer. Rewrite the following user request "
                "into a detailed, high-quality music generation prompt for the Lyria "
                "model. Focus on instruments, mood, tempo, genre, and texture. "
                f"Output ONLY the rewritten prompt.\n\nUser Request: '{prompt}'"
            )
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=contents,
            )
            return response.text.strip()
        except Exception as e:
            print(f"Prompt optimization failed: {e}")
            return prompt


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
        
        # Initialize Smart Assistant
        self.smart = SmartAssistant(self.client)

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
        """

        # Audio configuration
        CHANNELS = 2
        SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
        FRAME_RATE = 48000

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
                await session.set_weighted_prompts(
                    prompts=[
                        types.WeightedPrompt(text=prompt, weight=1.0),
                    ]
                )

                # Start playing
                await session.play()

                # Wait for completion
                await receiver_task
