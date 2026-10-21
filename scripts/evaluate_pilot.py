"""Usage: python scripts/evaluate_pilot.py manifest.json --output .tmp/pilot-report.json."""

import argparse
import json
from pathlib import Path

from chalkmate.pilot import PilotManifest, evaluate


def main():
    parser = argparse.ArgumentParser(description="Measure an anonymized consented teacher pilot")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = PilotManifest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evaluate(manifest), indent=2), encoding="utf-8")
    print(
        f"Pilot metrics saved to {args.output}. "
        f"{len(manifest.samples)} samples; teacher review required."
    )


if __name__ == "__main__":
    main()
