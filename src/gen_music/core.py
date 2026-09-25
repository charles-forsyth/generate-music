from typing import Optional

from google import genai
from google.genai import types

from .config import get_settings


class SmartAssistant:
    """Helper class to use Gemini Flash for text tasks."""
    
    def __init__(self, client: genai.Client):
        self.client = client
        self.model_id = "gemini-3.8-flash"

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
                "model. IMPORTANT: The model is INSTRUMENTAL ONLY. Do NOT ask for "
                "vocals, lyrics, singing, or voice. Focus on instruments, mood, "
                "tempo, genre, and texture. Output ONLY the rewritten prompt.\n\n"
                f"User Request: '{prompt}'"
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
        """Generate a track with Lyria 3.5 (or lyria-3-clip-preview for <=30 s).

        Lyria 3.5/3 Clip return a finished MP3 from one generate_content call.
        The result is written to output_file (converted to WAV if the name ends
        in .wav). Live DJ mode still uses the realtime model (settings.live_model_id).
        """
        model = self.settings.song_model_id
        if model == "auto":
            model = "lyria-3-clip-preview" if duration <= 30 else "lyria-3.5"
        text = (
            f"{prompt}. Instrumental only, no vocals. About {duration} seconds long, "
            f"around {bpm} BPM."
        )
        if negative_prompt:
            text += f" Avoid: {negative_prompt}."
        audio = None
        finish = None
        for _attempt in range(3):
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"], temperature=temperature
                ),
            )
            cand = response.candidates[0] if response.candidates else None
            finish = getattr(cand, "finish_reason", None)
            parts = (cand.content.parts or []) if cand and cand.content else []
            for part in parts:
                if part.inline_data and part.inline_data.data:
                    audio = part.inline_data
                    break
            if audio is not None:
                break
        if audio is None:
            raise RuntimeError(
                f"{model} returned no audio after 3 tries (finish_reason={finish}). "
                "Try rewording the prompt."
            )
        if output_file.lower().endswith(".wav") and "mpeg" in (audio.mime_type or ""):
            import io

            from pydub import AudioSegment

            AudioSegment.from_file(io.BytesIO(audio.data), format="mp3").export(
                output_file, format="wav"
            )
        else:
            with open(output_file, "wb") as f:
                f.write(audio.data)
