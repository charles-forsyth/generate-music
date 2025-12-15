import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

from gen_music.cli import main
from gen_music.utils import HISTORY_FILE, save_history


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

def run_cli(args):
    """Helper to run main() with mocked sys.argv"""
    with patch.object(sys, 'argv', ["gen-music"] + args):
        try:
            main()
        except SystemExit as e:
            return e.code
    return 0

def test_generate_command(mock_generator, clean_history):
    exit_code = run_cli(["test prompt", "--duration", "5"])
    assert exit_code == 0
    
    call_args = mock_generator.generate.call_args
    assert call_args is not None
    
    prompt_arg = call_args.kwargs.get("prompt")
    if prompt_arg is None and call_args.args:
        prompt_arg = call_args.args[0]
    
    assert prompt_arg == "test prompt"

def test_history_command(clean_history, capsys):
    save_history([
        {"prompt": "old prompt", "output_file": "file.wav", "timestamp": "2023-01-01"}
    ])
    exit_code = run_cli(["--history"])
    assert exit_code == 0
    
    captured = capsys.readouterr()
    assert "old prompt" in captured.out

def test_missing_prompt(clean_history):
    exit_code = run_cli([])
    assert exit_code != 0

def test_init_config(tmp_path):
    # Mock Path.home() to return tmp_path so we don't mess with real user config
    with patch("gen_music.cli.Path.home", return_value=tmp_path):
        exit_code = run_cli(["--init"])
        assert exit_code == 0
        
        config_dir = tmp_path / ".config" / "gen-music"
        env_file = config_dir / ".env"
        
        assert config_dir.exists()
        assert env_file.exists()
        assert "PROJECT_ID" in env_file.read_text()