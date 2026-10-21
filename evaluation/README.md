# Evaluation

Run `scripts/evaluate_pilot.py` against `pilot-example.json` for a synthetic
workflow rehearsal. The runner validates consent, unique sample IDs, nonoverlapping
calibration/held-out sheets, finite bounded marks and transcription pairs. Reports
include per-type/scan-quality grading and transcription error, severe-error IDs,
identity/question mismatches, review time, latency and human disagreement.

Read `docs/phase-seven.md` before collecting a real pilot. Keep private manifests
outside Git; never commit actual student work or personal data. The supplied
example is synthetic and establishes no educational quality or time-saving result.
