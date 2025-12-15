import warnings

# Suppress annoying warnings globally for the CLI tool
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")
warnings.filterwarnings("ignore", module="google.genai")

__version__ = "0.2.4"
