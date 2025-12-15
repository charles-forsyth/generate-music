import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from gen_music.cli import app
from gen_music.utils import HISTORY_FILE, save_history

runner = CliRunner()

@pytest.fixture
def mock_generator():
    with patch("gen_music.cli.MusicGenerator") as MockGen:
        instance = MockGen.return_value
        instance.generate = AsyncMock()
        yield instance

@pytest.fixture
def clean_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    yield
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)

def test_generate_command(mock_generator, clean_history):
    result = runner.invoke(app, ["generate", "test prompt", "--duration", "5"])
    assert result.exit_code == 0
    assert "test prompt" in str(mock_generator.generate.call_args)
    
    # Check history
    assert os.path.exists(HISTORY_FILE)
    with open(HISTORY_FILE) as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["prompt"] == "test prompt"

def test_history_command(clean_history):
    save_history([
        {"prompt": "old prompt", "output_file": "file.wav", "timestamp": "2023-01-01"}
    ])
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0
    assert "old prompt" in result.stdout