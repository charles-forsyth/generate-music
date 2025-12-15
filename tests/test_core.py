import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gen_music.core import MusicGenerator


@pytest.fixture
def mock_genai_client():
    with patch("gen_music.core.genai.Client") as MockClient:
        client_instance = MockClient.return_value
        session_mock = AsyncMock()
        
        # Setup the context manager for connect
        connect_ctx = AsyncMock()
        connect_ctx.__aenter__.return_value = session_mock
        connect_ctx.__aexit__.return_value = None
        client_instance.aio.live.music.connect.return_value = connect_ctx
        
        yield client_instance, session_mock

@pytest.mark.asyncio
async def test_generate_music(mock_genai_client, tmp_path):
    client_mock, session_mock = mock_genai_client
    
    # Mock receive to yield one chunk of audio
    # The structure is message.server_content.audio_chunks[0].data
    mock_chunk = b'\x00\x00' * 100 # 100 frames of silence
    
    mock_message = MagicMock()
    mock_message.server_content.audio_chunks = [MagicMock(data=mock_chunk)]
    
    async def fake_receive():
        yield mock_message
        # Sleep briefly to allow the loop to be cancelled or exit
        await asyncio.sleep(0.1)
        
    session_mock.receive.return_value = fake_receive()

    output_file = tmp_path / "test_output.wav"
    
    generator = MusicGenerator()
    # We use a very short duration so the loop condition (bytes target) is met quickly
    # 100 frames at 48k is tiny duration.
    # The code calculates target_bytes = duration * FRAME_RATE * ...
    # Let's override the duration to be very small or rely on the loop reading the chunk.
    
    # Actually, the loop continues until total_bytes >= target_bytes.
    # If duration=1 (default arg in test), target is huge.
    # We should pass a tiny duration.
    # 100 frames / 48000 ~ 0.002 seconds.
    
    await generator.generate(
        prompt="test prompt",
        output_file=str(output_file),
        duration=0.01, # Should be enough to cover the chunk
        bpm=120
    )
    
    # Verify file was created
    assert output_file.exists()
    
    # Verify calls
    session_mock.set_music_generation_config.assert_called_once()
    session_mock.set_weighted_prompts.assert_called_once()
    session_mock.play.assert_called_once()
