import os
import sys
import tempfile
from pathlib import Path

# Base de datos temporal y modo demostración para las pruebas
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'pruebas.db'}"
os.environ["LLM_MODO"] = "demo"
os.environ["STORAGE_DIR"] = str(Path(_tmp) / "exports")
os.environ["SMTP_USUARIO"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
