import sys
import importlib.util
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

spec = importlib.util.spec_from_file_location("_backend_app", SRC_DIR / "app.py")
backend_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_app)
app = backend_app.app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8090, reload=True)
