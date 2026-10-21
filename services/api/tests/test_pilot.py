import pytest
from pydantic import ValidationError

from chalkmate.pilot import PilotManifest, evaluate


def sample(**changes):
    return {
        "sample_id": "a1",
        "sheet_id": "s1",
        "split": "held_out",
        "consented": True,
        "answer_type": "descriptive",
        "scan_quality": "clear",
        "maximum": 10,
        "teacher_mark": 8,
        "model_mark": 9,
        "second_teacher_mark": 8.5,
        "identity_correct": True,
        "question_correct": True,
        "rubric_version": "r1",
        "model_digest": "local:hash",
        "baseline_seconds": 100,
        "review_seconds": 60,
        "latency_seconds": 12,
        "flagged_for_review": True,
        "reference_text": "A stack uses LIFO",
        "extracted_text": "A stack uses FIFO",
        **changes,
    }


def test_pilot_metrics_keep_severe_errors_and_groups():
    manifest = PilotManifest(
        dataset="synthetic",
        samples=[
            sample(),
            sample(sample_id="a2", sheet_id="s2", model_mark=4, scan_quality="poor"),
            sample(sample_id="cal", sheet_id="calibration", split="calibration"),
        ],
    )
    result = evaluate(manifest)
    assert result["held_out"]["mean_absolute_error"] == 2.5
    assert result["held_out"]["within_10_percent"] == 0.5
    assert result["held_out"]["severe_errors"] == [{"sample_id": "a2", "direction": "under"}]
    assert result["held_out"]["review_time_reduction"] == 0.4
    assert result["calibration_answers_excluded"] == 1
    assert len(result["groups"]) == 2
    assert not result["publication_authorized"]
    assert result["held_out"]["word_error_rate"] == 0.25


def test_pilot_rejects_leakage_and_unconsented_or_invalid_samples():
    for rows in [
        [sample(), sample(sample_id="cal", split="calibration")],
        [sample(consented=False)],
        [sample(model_mark=11)],
        [sample(model_mark=float("nan"))],
    ]:
        with pytest.raises(ValidationError):
            PilotManifest(dataset="pilot", samples=rows)
