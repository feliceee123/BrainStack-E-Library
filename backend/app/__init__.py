# E-Library AI backend package
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env regardless of which directory starts the server.
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")
