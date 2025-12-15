import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gen_music.cli import main
from gen_music.utils import HISTORY_FILE, save_history


@pytest.fixture
def mock_generator():
    with patch("gen_music.cli.MusicGenerator") as MockGen:
        instance = MockGen.return_value
        instance.generate = AsyncMock()
        # Mock the smart assistant
        instance.smart = MagicMock()
        instance.smart.generate_filename_slug = AsyncMock(return_value="test_slug")
        instance.smart.optimize_prompt = AsyncMock(return_value="optimized prompt")
        yield instance

@pytest.fixture
def mock_convert():
    with patch("gen_music.cli.convert_audio") as MockConv:
        MockConv.return_value = "converted.mp3"
        yield MockConv

@pytest.fixture
def clean_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    yield
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)

def run_cli(args, input_str=None):
    """Helper to run main() with mocked sys.argv and stdin"""
    with patch.object(sys, 'argv', ["gen-music"] + args):
        if input_str is not None:
            # Mock stdin for piping
            with patch('sys.stdin') as mock_stdin:
                mock_stdin.isatty.return_value = False
                mock_stdin.read.return_value = input_str
                try:
                    main()
                except SystemExit as e:
                    return e.code
        else:
            # Mock stdin as TTY (normal interactive)
            with patch('sys.stdin') as mock_stdin:
                mock_stdin.isatty.return_value = True
                try:
                    main()
                except SystemExit as e:
                    return e.code
    return 0

def test_generate_command(mock_generator, clean_history):
    exit_code = run_cli(["test prompt", "--duration", "5"])
    assert exit_code == 0
    
    # Check filename generation called
    mock_generator.smart.generate_filename_slug.assert_called_with("test prompt")

def test_piped_input(mock_generator, clean_history):
    # Test piping "piped prompt"
    exit_code = run_cli([], input_str="piped prompt")
    assert exit_code == 0
    
    call_args = mock_generator.generate.call_args
    prompt_arg = call_args.kwargs.get("prompt")
    assert prompt_arg == "piped prompt"

def test_optimize_flag(mock_generator, clean_history):
    exit_code = run_cli(["raw prompt", "--optimize"])
    assert exit_code == 0
    
    mock_generator.smart.optimize_prompt.assert_called_with("raw prompt")
    # Verify generator called with OPTIMIZED prompt
    call_args = mock_generator.generate.call_args
    assert call_args.kwargs.get("prompt") == "optimized prompt"

def test_history_command(clean_history, capsys):
    save_history([
        {"prompt": "old prompt", "output_file": "file.wav", "timestamp": "2023-01-01"}
    ])
    exit_code = run_cli(["--history"])
    assert exit_code == 0
    
    # Check stderr for history output (since we moved console to stderr)
    captured = capsys.readouterr()
    assert "old prompt" in captured.err

def test_mp3_conversion(mock_generator, mock_convert, clean_history):
    exit_code = run_cli(["test prompt", "--format", "mp3"])
    assert exit_code == 0
    mock_convert.assert_called_once()