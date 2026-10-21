from decimal import Decimal

from fastapi import HTTPException

from chalkmate.assessment_schemas import Suggestion


def latest(db, model, submission_id):
    from sqlalchemy import select

    # Versioned records have an authoritative order even if the database clock
    # moves backwards or an earlier transaction waits on a submission lock.
    ordering = [model.version.desc()] if hasattr(model, "version") else []
    return db.scalar(
        select(model)
        .where(model.submission_id == submission_id)
        .order_by(*ordering, model.created_at.desc(), model.id.desc())
        .limit(1)
    )


def validate_marks(questions, marks):
    criteria = {c["id"]: c for q in questions for c in q["criteria"]}
    provided = [str(mark["criterion_id"]) for mark in marks]
    if len(provided) != len(set(provided)) or set(provided) != set(criteria):
        raise HTTPException(422, "Provide each rubric criterion exactly once")
    total = Decimal("0")
    for item in marks:
        mark = Decimal(str(item["mark"]))
        if (
            not mark.is_finite()
            or mark < 0
            or mark > Decimal(str(criteria[str(item["criterion_id"])]["maximum"]))
        ):
            raise HTTPException(422, "A mark is outside its criterion bounds")
        if mark != mark.quantize(Decimal("0.01")):
            raise HTTPException(422, "Marks support at most two decimal places")
        total += mark
    return total


def validate_suggestion(questions, answers, output):
    result = Suggestion.model_validate(output)
    values = result.model_dump(mode="json")
    validate_marks(questions, values["criteria"])
    mapping = {answer["question_id"]: answer for answer in answers}
    known = {c["id"]: q["id"] for q in questions for c in q["criteria"]}
    for criterion in values["criteria"]:
        question_id = criterion["question_id"]
        answer = mapping.get(question_id)
        if not answer or known[criterion["criterion_id"]] != question_id:
            raise ValueError("Unknown question or mismatched criterion")
        if not answer["page_from"] <= criterion["evidence_page"] <= answer["page_to"]:
            raise ValueError("Evidence page does not match reviewed question mapping")
        quote = criterion["evidence_quote"].strip()
        if quote and quote not in answer["text"]:
            raise ValueError("Evidence quote was not found in reviewed answer text")
        if Decimal(criterion["mark"]) > 0 and not quote:
            raise ValueError("Positive credit requires supporting answer evidence")
    return values
