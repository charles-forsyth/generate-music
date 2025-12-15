import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gen_music.cli import main
from gen_music.utils import HISTORY_FILE


@pytest.fixture
def mock_generator():
    with patch("gen_music.cli.MusicGenerator") as MockGen:
        instance = MockGen.return_value
        instance.generate = AsyncMock()
        instance.smart = MagicMock()
        instance.smart.generate_filename_slug = AsyncMock(return_value="test_slug")
        instance.smart.optimize_prompt = AsyncMock(return_value="optimized prompt")
        yield instance

@pytest.fixture
def mock_convert():
    with patch("gen_music.cli.convert_audio") as MockConv:
        MockConv.return_value = "/path/to/converted.mp3"
        yield MockConv

@pytest.fixture
def clean_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    yield
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)

def run_cli(args, input_str=None):
    with patch.object(sys, 'argv', ["gen-music"] + args):
        if input_str is not None:
            with patch('sys.stdin') as mock_stdin:
                mock_stdin.isatty.return_value = False
                mock_stdin.read.return_value = input_str
                try:
                    main()
                except SystemExit as e:
                    return e.code
        else:
            with patch('sys.stdin') as mock_stdin:
                mock_stdin.isatty.return_value = True
                try:
                    main()
                except SystemExit as e:
                    return e.code
    return 0

def test_generate_command(mock_generator, mock_convert, clean_history, capsys):
    exit_code = run_cli(["test prompt", "--duration", "5"])
    assert exit_code == 0
    
    # Check that ONLY filename is printed to stdout
    captured = capsys.readouterr()
    assert "converted.mp3" in captured.out
    
    # Status messages are now removed/silenced in stderr too for standard run?
    # CLI code removed explicit status prints.
    assert "Generating music..." not in captured.err

def test_mp3_default(mock_generator, mock_convert, clean_history):
    exit_code = run_cli(["test prompt"])
    assert exit_code == 0
    mock_convert.assert_called_once() 

def test_piped_input(mock_generator, mock_convert, clean_history):
    exit_code = run_cli([], input_str="piped prompt")
    assert exit_code == 0
    
    call_args = mock_generator.generate.call_args
    prompt_arg = call_args.kwargs.get("prompt")
    assert prompt_arg == "piped prompt"
