import json
from pathlib import Path

from chalkmate.main import app

root = Path(__file__).resolve().parents[1]
(root / "contracts/openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n")
print("OpenAPI exported")
