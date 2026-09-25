import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gen_music.core import MusicGenerator


@pytest.fixture
def mock_genai_client():
    with patch("gen_music.core.genai.Client") as MockClient:
        client_instance = MockClient.return_value
        # session is MagicMock as receive() is not awaited (returns async iterator)
        session_mock = MagicMock()
        session_mock.set_music_generation_config = AsyncMock()
        session_mock.set_weighted_prompts = AsyncMock()
        session_mock.play = AsyncMock()
        
        # Setup the context manager for connect
        connect_ctx = AsyncMock()
        connect_ctx.__aenter__.return_value = session_mock
        connect_ctx.__aexit__.return_value = None
        client_instance.aio.live.music.connect.return_value = connect_ctx
        
        yield client_instance, session_mock

@pytest.fixture
def mock_settings():
    with patch("gen_music.core.get_settings") as MockSettings:
        settings_instance = MockSettings.return_value
        # Test with API Key path
        settings_instance.google_api_key = "test-key"
        settings_instance.project_id = None
        settings_instance.location = "us-central1"
        settings_instance.model_id = "models/test-model"
        yield settings_instance

@pytest.mark.asyncio
async def test_generate_music(mock_genai_client, mock_settings, tmp_path):
    client_mock, _ = mock_genai_client
    mock_settings.song_model_id = "auto"
    part = MagicMock()
    part.inline_data.data = b"ID3fake-mp3"
    part.inline_data.mime_type = "audio/mpeg"
    resp = MagicMock()
    resp.candidates = [MagicMock(content=MagicMock(parts=[part]))]
    client_mock.aio.models.generate_content = AsyncMock(return_value=resp)

    output_file = tmp_path / "test_output.mp3"
    generator = MusicGenerator()
    await generator.generate(prompt="test prompt", output_file=str(output_file), duration=10)

    assert output_file.read_bytes() == b"ID3fake-mp3"
    kwargs = client_mock.aio.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "lyria-3-clip-preview"
    assert "test prompt" in kwargs["contents"]


@pytest.mark.asyncio
async def test_generate_long_uses_lyria_35(mock_genai_client, mock_settings, tmp_path):
    client_mock, _ = mock_genai_client
    mock_settings.song_model_id = "auto"
    part = MagicMock()
    part.inline_data.data = b"ID3x"
    part.inline_data.mime_type = "audio/mpeg"
    resp = MagicMock()
    resp.candidates = [MagicMock(content=MagicMock(parts=[part]))]
    client_mock.aio.models.generate_content = AsyncMock(return_value=resp)
    await MusicGenerator().generate("p", str(tmp_path / "o.mp3"), duration=90)
    assert client_mock.aio.models.generate_content.call_args.kwargs["model"] == "lyria-3.5"
