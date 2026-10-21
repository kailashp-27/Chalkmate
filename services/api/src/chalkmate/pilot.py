"""Offline pilot measurements; a metric report is never permission to publish marks."""

from collections import defaultdict
from statistics import mean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnswerSample(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    sample_id: str = Field(min_length=1, max_length=100)
    sheet_id: str = Field(min_length=1, max_length=100)
    split: Literal["calibration", "held_out"]
    consented: bool
    answer_type: str = Field(min_length=1, max_length=80)
    scan_quality: Literal["clear", "mixed", "poor"]
    maximum: float = Field(gt=0, le=1000)
    teacher_mark: float = Field(ge=0)
    model_mark: float = Field(ge=0)
    second_teacher_mark: float | None = Field(default=None, ge=0)
    identity_correct: bool
    question_correct: bool
    rubric_version: str = Field(min_length=1, max_length=100)
    model_digest: str = Field(min_length=1, max_length=100)
    baseline_seconds: float = Field(gt=0)
    review_seconds: float = Field(ge=0)
    latency_seconds: float = Field(ge=0)
    flagged_for_review: bool
    reference_text: str | None = Field(default=None, max_length=20000)
    extracted_text: str | None = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def validate_sample(self):
        if not self.consented:
            raise ValueError("Only consented/anonymized samples may enter pilot evaluation")
        if any(
            v is not None and v > self.maximum
            for v in (self.teacher_mark, self.model_mark, self.second_teacher_mark)
        ):
            raise ValueError("Marks exceed question maximum")
        if (self.reference_text is None) != (self.extracted_text is None):
            raise ValueError("Supply both reference and extracted text")
        return self


class PilotManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(min_length=1, max_length=100)
    synthetic: bool = True
    samples: list[AnswerSample] = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def validate_splits(self):
        if len({s.sample_id for s in self.samples}) != len(self.samples):
            raise ValueError("Sample IDs must be unique")
        calibration = {s.sheet_id for s in self.samples if s.split == "calibration"}
        held_out = {s.sheet_id for s in self.samples if s.split == "held_out"}
        if calibration & held_out:
            raise ValueError("Calibration and held-out sheets must not overlap")
        if not held_out:
            raise ValueError("At least one held-out sample is required")
        return self


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, item in enumerate(a, 1):
        current = [i]
        for j, other in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (item != other)))
        previous = current
    return previous[-1]


def metrics(samples):
    errors = [abs(s.teacher_mark - s.model_mark) for s in samples]
    normalized = [e / s.maximum for e, s in zip(errors, samples, strict=True)]
    transcribed = [s for s in samples if s.reference_text]
    double_marked = [s for s in samples if s.second_teacher_mark is not None]
    baseline = sum(s.baseline_seconds for s in samples)
    latencies = sorted(s.latency_seconds for s in samples)
    return {
        "answers": len(samples),
        "sheets": len({s.sheet_id for s in samples}),
        "mean_absolute_error": mean(errors),
        "mean_normalized_error": mean(normalized),
        "within_10_percent": sum(v <= 0.1 + 1e-10 for v in normalized) / len(samples),
        "severe_errors": [
            {
                "sample_id": s.sample_id,
                "direction": "over" if s.model_mark > s.teacher_mark else "under",
            }
            for s, e in zip(samples, normalized, strict=True)
            if e > 0.2 + 1e-10
        ],
        "identity_mismatches": sum(not s.identity_correct for s in samples),
        "question_mismatches": sum(not s.question_correct for s in samples),
        "review_rate": sum(s.flagged_for_review for s in samples) / len(samples),
        "review_time_reduction": 1 - sum(s.review_seconds for s in samples) / baseline,
        "latency_p50_seconds": latencies[(len(latencies) - 1) // 2],
        "latency_p95_seconds": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))],
        "human_mean_normalized_disagreement": mean(
            abs(s.teacher_mark - s.second_teacher_mark) / s.maximum for s in double_marked
        )
        if double_marked
        else None,
        "double_marked_answers": len(double_marked),
        "character_error_rate": sum(
            distance(s.reference_text, s.extracted_text) for s in transcribed
        )
        / sum(len(s.reference_text) for s in transcribed)
        if transcribed
        else None,
        "word_error_rate": sum(
            distance(s.reference_text.split(), s.extracted_text.split()) for s in transcribed
        )
        / sum(max(1, len(s.reference_text.split())) for s in transcribed)
        if transcribed
        else None,
    }


def evaluate(manifest: PilotManifest):
    held_out = [s for s in manifest.samples if s.split == "held_out"]
    groups = defaultdict(list)
    for s in held_out:
        groups[f"{s.answer_type} / {s.scan_quality}"].append(s)
    overall = metrics(held_out)
    return {
        "dataset": manifest.dataset,
        "synthetic": manifest.synthetic,
        "status": "Synthetic rehearsal only"
        if manifest.synthetic
        else "Teacher review required; targets are provisional",
        "held_out": overall,
        "groups": {key: metrics(rows) for key, rows in groups.items()},
        "calibration_answers_excluded": len(manifest.samples) - len(held_out),
        "provisional_targets": {
            "agreement_at_least_90_percent": overall["within_10_percent"] >= 0.9,
            "review_time_reduction_at_least_30_percent": overall["review_time_reduction"] >= 0.3,
            "no_identity_or_question_mismatches": overall["identity_mismatches"] == 0
            and overall["question_mismatches"] == 0,
            "at_least_30_held_out_sheets": overall["sheets"] >= 30,
            "double_marked_subset_available": overall["double_marked_answers"] > 0,
        },
        "publication_authorized": False,
    }
