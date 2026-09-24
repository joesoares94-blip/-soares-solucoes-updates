from __future__ import annotations
import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent
parts = sorted(HERE.glob("app_runtime.b64.part*"))
if not parts:
    raise RuntimeError("Arquivos da aplicação não encontrados. Execute a atualização novamente.")
encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
code = base64.b64decode(encoded).decode("utf-8")
runtime_path = HERE / "app_runtime.py"
runtime_path.write_text(code, encoding="utf-8")
namespace = {"__name__": "__main__", "__file__": str(runtime_path)}
exec(compile(code, str(runtime_path), "exec"), namespace)
