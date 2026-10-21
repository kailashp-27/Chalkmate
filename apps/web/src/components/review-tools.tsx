"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  GitCompareArrows,
  History,
  RotateCcw,
} from "lucide-react";
import { api } from "../lib/api";
import { refreshAssessment, refreshPaper } from "../lib/review-cache";
import type { components } from "../lib/api-schema";
import { Modal, Notice } from "./ui";

type S = components["schemas"];
type Paper = S["SubmissionOutput"];
type Assessment = S["AssessmentOutput"];
type Question = S["QuestionOutput"];
const score = (value: string | number) =>
  Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });

export function ReviewDesk({
  assessment,
  papers,
  canEdit,
  openPaper,
  editRubric,
}: {
  assessment: Assessment;
  papers: Paper[];
  canEdit: boolean;
  openPaper: (id: string) => void;
  editRubric: () => void;
}) {
  const [tab, setTab] = useState("queue");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [questionId, setQuestionId] = useState("");
  const [comparison, setComparison] = useState("");
  const queue = useQuery({
    queryKey: [
      "review-queue",
      assessment.id,
      papers
        .map(
          (p) =>
            `${p.id}:${p.status}:${p.rubric.id}:${p.question_reviews.map((r) => r.id).join()}:${p.jobs.map((j) => j.status).join()}`,
        )
        .join(),
    ],
    queryFn: () =>
      api<S["QueueItem"][]>(`/v1/assessments/${assessment.id}/review-queue`),
    enabled: tab === "queue",
  });
  const versions = useQuery({
    queryKey: ["rubric-versions", assessment.id],
    queryFn: () =>
      api<S["RubricOutput"][]>(`/v1/assessments/${assessment.id}/rubrics`),
    enabled: tab === "rubrics" || tab === "calibration",
  });
  const calibrations = useQuery({
    queryKey: ["calibrations", assessment.id],
    queryFn: () =>
      api<S["CalibrationOutput"][]>(
        `/v1/assessments/${assessment.id}/calibrations`,
      ),
    enabled: tab === "calibration",
  });
  const question =
    assessment.rubric?.questions.find((q) => q.id === questionId) ??
    assessment.rubric?.questions[0];
  const visible = queue.data?.filter(
    (item) =>
      `${item.student_name} ${item.registration_number}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (filter === "all" ||
        (filter === "pending" && item.status !== "released") ||
        (filter === "approved" && item.status === "approved") ||
        (filter === "stale" &&
          item.rubric_version !== item.latest_rubric_version) ||
        (filter === "failed" && item.failed_jobs > 0)),
  );
  return (
    <section className="review-desk" aria-label="Reliable review">
      <div className="review-desk-header">
        <div>
          <span className="eyebrow">RELIABLE REVIEW</span>
          <h3>A clear path through every paper.</h3>
        </div>
        <span className="small muted">
          Versions stay traceable. Release stays yours.
        </span>
      </div>
      <div className="review-tool-tabs" role="group" aria-label="Review tools">
        {[
          ["queue", "Review queue"],
          ["questions", "Question review"],
          ["calibration", "Calibration"],
          ["rubrics", "Rubric history"],
        ].map(([value, label]) => (
          <button
            key={value}
            className={tab === value ? "button chosen" : "button"}
            aria-pressed={tab === value}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "queue" && (
        <>
          <div className="review-filters">
            <label>
              Find a student
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Name or registration number"
              />
            </label>
            <label>
              Queue filter
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              >
                <option value="all">All papers</option>
                <option value="pending">Awaiting review or release</option>
                <option value="approved">Ready for release</option>
                <option value="stale">New rubric available</option>
                <option value="failed">Processing needs attention</option>
              </select>
            </label>
          </div>
          <Notice error={queue.error} />
          {queue.isPending ? (
            <p role="status">Loading review queue…</p>
          ) : visible?.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>STUDENT</th>
                    <th>REVIEW STAGE</th>
                    <th>QUESTIONS</th>
                    <th>RUBRIC</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {visible.map((item) => (
                    <tr key={item.submission_id}>
                      <td>
                        <strong>{item.student_name}</strong>
                        <small className="block">
                          {item.registration_number}
                        </small>
                      </td>
                      <td>
                        <span className="status">
                          {item.status.replaceAll("_", " ")}
                        </span>
                        {item.reasons.map((reason) => (
                          <small className="block" key={reason}>
                            {reason}
                          </small>
                        ))}
                      </td>
                      <td>
                        {item.reviewed_questions} / {item.question_count} saved
                      </td>
                      <td>
                        v{item.rubric_version}
                        {item.rubric_version !== item.latest_rubric_version && (
                          <small className="block warning-text">
                            v{item.latest_rubric_version} available
                          </small>
                        )}
                      </td>
                      <td>
                        <button
                          className="text-button"
                          onClick={() => openPaper(item.submission_id)}
                        >
                          {item.status === "released"
                            ? "View result"
                            : "Review paper"}
                          <ArrowRight size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty-inline">
              {papers.length
                ? "No papers match this filter."
                : "Upload papers to start your review queue."}
            </p>
          )}
        </>
      )}
      {tab === "questions" && (
        <>
          <p className="muted small">
            Review the same question across papers. Save each question’s marks
            and feedback, then approve and release the complete paper.
          </p>
          {question && (
            <label>
              Question to review
              <select
                value={question.id}
                onChange={(e) => setQuestionId(e.target.value)}
              >
                {assessment.rubric!.questions.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.label} · {q.prompt.slice(0, 90)}
                  </option>
                ))}
              </select>
            </label>
          )}
          {question &&
            papers
              .filter(
                (p) =>
                  p.rubric.id === assessment.rubric?.id &&
                  p.extraction?.reviewed_by &&
                  p.status !== "released",
              )
              .map((p) => (
                <article className="question-lane-card" key={p.id}>
                  <header>
                    <div>
                      <h4>{p.student_name}</h4>
                      <span className="small muted">
                        {p.registration_number}
                      </span>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => openPaper(p.id)}
                    >
                      Open original & full review <ArrowRight size={14} />
                    </button>
                  </header>
                  <QuestionDraft
                    key={`${p.id}:${question.id}:${p.question_reviews.find((r) => r.question_id === question.id)?.id}`}
                    paper={p}
                    question={question}
                    editable={canEdit}
                  />
                </article>
              ))}
          {!papers.some(
            (p) =>
              p.rubric.id === assessment.rubric?.id &&
              p.extraction?.reviewed_by &&
              p.status !== "released",
          ) && (
            <p className="empty-inline">
              Review a paper’s extraction first. Papers on older rubrics need
              explicit re-evaluation before joining this queue.
            </p>
          )}
        </>
      )}
      {tab === "calibration" && (
        <>
          <p className="muted small">
            Capture teacher-marked low, middle, and high examples from a paper’s
            review screen. Model comparisons use that paper’s exact rubric,
            extraction, and model snapshot. Reference-only examples have no
            model error score.
          </p>
          <Notice error={calibrations.error} />
          {calibrations.isPending ? (
            <p>Loading calibration examples…</p>
          ) : calibrations.data?.length ? (
            calibrations.data.map((c) => (
              <article className="calibration-card" key={c.id}>
                <header>
                  <span className="status">{c.band} example</span>
                  <span className="small muted">
                    Rubric v
                    {versions.data?.find((r) => r.id === c.rubric_id)
                      ?.version ??
                      (assessment.rubric?.id === c.rubric_id
                        ? assessment.rubric.version
                        : "older")}{" "}
                    · {new Date(c.created_at).toLocaleDateString()}
                  </span>
                </header>
                <p>{c.note}</p>
                <div className="calibration-values">
                  <span>
                    Teacher reference{" "}
                    <strong>{score(c.snapshot.expected_total)}</strong>
                  </span>
                  <span>
                    Model suggestion{" "}
                    <strong>
                      {c.snapshot.observed_total !== null
                        ? score(c.snapshot.observed_total)
                        : "Reference only"}
                    </strong>
                  </span>
                  <span>
                    Mean absolute error / criterion{" "}
                    <strong>
                      {c.snapshot.mean_absolute_error !== null
                        ? score(c.snapshot.mean_absolute_error)
                        : "Not compared"}
                    </strong>
                  </span>
                </div>
                {c.snapshot.model && (
                  <small className="muted">
                    {c.snapshot.model} · {c.snapshot.model_digest?.slice(0, 12)}{" "}
                    · {c.snapshot.prompt_version}
                  </small>
                )}
                <details>
                  <summary>Criterion comparison</summary>
                  <ul>
                    {c.snapshot.criteria.map((criterion) => (
                      <li key={criterion.criterion_id}>
                        Reference {criterion.expected} · model{" "}
                        {criterion.observed ?? "—"} · delta{" "}
                        {criterion.delta ?? "—"}
                      </li>
                    ))}
                  </ul>
                </details>
              </article>
            ))
          ) : (
            <p className="empty-inline">
              No calibration examples yet. Open a reviewed paper and choose
              “Capture calibration example”.
            </p>
          )}
          <p className="small muted">
            These examples support review and adjustment. They are not a
            held-out accuracy benchmark.
          </p>
        </>
      )}
      {tab === "rubrics" && (
        <>
          <div className="section-heading">
            <p className="muted small">
              Every saved version is preserved. Activation affects new papers;
              existing papers stay pinned until re-evaluation.
            </p>
            {canEdit && (
              <button className="button" onClick={editRubric}>
                Revise rubric
              </button>
            )}
          </div>
          <Notice error={versions.error} />
          {versions.data?.map((r) => (
            <article className="rubric-version-row" key={r.id}>
              <div>
                <strong>Version {r.version}</strong>
                <span className="small muted">
                  {r.approved_at ? "Approved" : "Draft"}
                  {r.id === assessment.rubric?.id &&
                  assessment.status === "active"
                    ? " · current"
                    : ""}
                </span>
                <p>{r.reason || "Initial marking rubric"}</p>
              </div>
              <button className="button" onClick={() => setComparison(r.id)}>
                <GitCompareArrows size={15} />
                Review changes
              </button>
            </article>
          ))}
        </>
      )}
      {comparison && (
        <RubricComparison
          assessment={assessment}
          rubricId={comparison}
          canEdit={canEdit}
          close={() => setComparison("")}
        />
      )}
    </section>
  );
}

function RubricComparison({
  assessment,
  rubricId,
  canEdit,
  close,
}: {
  assessment: Assessment;
  rubricId: string;
  canEdit: boolean;
  close: () => void;
}) {
  const query = useQueryClient();
  const diff = useQuery({
    queryKey: ["rubric-diff", assessment.id, rubricId],
    queryFn: () =>
      api<S["RubricDiff"]>(
        `/v1/assessments/${assessment.id}/rubrics/${rubricId}/diff`,
      ),
  });
  const [confirmed, setConfirmed] = useState(false);
  const activate = useMutation({
    mutationFn: () =>
      api(`/v1/assessments/${assessment.id}/activate`, {
        method: "POST",
        body: JSON.stringify({ rubric_id: rubricId }),
      }),
    onSuccess: () => {
      refreshAssessment(query, assessment.id);
      close();
    },
  });
  return (
    <Modal title="Review rubric changes" close={close}>
      <Notice error={diff.error ?? activate.error} />
      {diff.data && (
        <>
          <p>
            Version {diff.data.base_version} → version{" "}
            {diff.data.candidate.version} · {diff.data.affected_submissions}{" "}
            existing papers stay pinned to their versions.
          </p>
          <p className="muted">{diff.data.candidate.reason}</p>
          <div className="rubric-diff-list">
            {diff.data.changes.map((c, i) => (
              <article key={i}>
                <strong>
                  {c.path
                    .replace(/^questions\./, "")
                    .replace(/\.criteria\./g, " / ")
                    .replace(/\.maximum$/, " · maximum marks")
                    .replace(/\.model_answer$/, " · model answer")
                    .replace(
                      /\.accepted_alternatives$/,
                      " · accepted alternatives",
                    )
                    .replace(/\.guidance$/, " · guidance")
                    .replace(/\.prompt$/, " · question text")
                    .replace(/\.label$/, " · label")
                    .replace(/\.order$/, " · order")}
                </strong>
                <div>
                  <span className="diff-before">
                    {c.before === "[]" ? "None" : c.before}
                  </span>
                  <ArrowRight size={15} />
                  <span>{c.after}</span>
                </div>
              </article>
            ))}
          </div>
          {!diff.data.changes.length && (
            <p>No question or criterion changes.</p>
          )}
          {canEdit &&
            !diff.data.candidate.approved_at &&
            (assessment.draft_rubric?.id === rubricId ||
              assessment.status === "draft") && (
              <>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                  />
                  I reviewed these changes. Existing papers require separate
                  re-evaluation.
                </label>
                <button
                  className="button primary"
                  disabled={!confirmed || activate.isPending}
                  onClick={() => activate.mutate()}
                >
                  Activate this rubric version
                </button>
              </>
            )}
        </>
      )}
    </Modal>
  );
}

export function QuestionDraft({
  paper,
  question,
  editable,
}: {
  paper: Paper;
  question: Question;
  editable: boolean;
}) {
  const saved = paper.question_reviews.find(
    (r) => r.question_id === question.id,
  );
  const [marks, setMarks] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      question.criteria.map((c) => [
        c.id,
        saved?.marks.find((m) => m.criterion_id === c.id)?.mark ??
          paper.decision?.marks.find((m) => m.criterion_id === c.id)?.mark ??
          paper.proposal?.output.criteria.find((m) => m.criterion_id === c.id)
            ?.mark ??
          "",
      ]),
    ),
  );
  const [feedback, setFeedback] = useState(saved?.feedback ?? "");
  const query = useQueryClient();
  const save = useMutation({
    mutationFn: () =>
      api(`/v1/submissions/${paper.id}/questions/${question.id}/reviews`, {
        method: "POST",
        body: JSON.stringify({
          extraction_id: paper.extraction!.id,
          rubric_id: paper.rubric.id,
          base_review_id: saved?.id ?? null,
          marks: question.criteria.map((c) => ({
            criterion_id: c.id,
            mark: marks[c.id],
          })),
          feedback,
        }),
      }),
    onSuccess: () => {
      refreshPaper(query, paper);
    },
  });
  const answer = paper.extraction?.answers.find(
    (a) => a.question_id === question.id,
  );
  return (
    <div className="question-draft">
      <p className="small muted">{question.prompt}</p>
      <blockquote className="reviewed-answer">
        {answer?.text || "Blank answer"}
        <small>
          Reviewed page {answer?.page_from ?? "—"}
          {answer?.page_to !== answer?.page_from ? `–${answer?.page_to}` : ""}
        </small>
      </blockquote>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div className="question-draft-marks">
          {question.criteria.map((c) => (
            <label key={c.id}>
              {c.label}
              <input
                aria-label={`${question.label} reference score: ${c.label}`}
                type="number"
                step="0.01"
                min="0"
                max={c.maximum}
                required
                disabled={!editable}
                value={marks[c.id]}
                onChange={(e) => setMarks({ ...marks, [c.id]: e.target.value })}
              />
              <span className="small muted">/ {c.maximum}</span>
            </label>
          ))}
        </div>
        <label>
          Question feedback
          <textarea
            value={feedback}
            maxLength={4000}
            required
            disabled={!editable}
            onChange={(e) => setFeedback(e.target.value)}
            rows={2}
          />
        </label>
        <Notice error={save.error} />
        {editable && (
          <button className="button" disabled={save.isPending}>
            Save question review
          </button>
        )}
        {saved && (
          <p className="small saved-review">
            <Check size={14} />
            Question review saved ·{" "}
            {new Date(saved.created_at).toLocaleString()}
          </p>
        )}
      </form>
    </div>
  );
}

export function PaperReviewTools({
  paper,
  assessment,
  canEdit,
}: {
  paper: Paper;
  assessment: Assessment;
  canEdit: boolean;
}) {
  const [dialog, setDialog] = useState<
    "" | "history" | "reevaluate" | "calibration"
  >("");
  const stale = paper.rubric.id !== assessment.rubric?.id;
  return (
    <>
      <div className="paper-review-tools">
        <span className="small muted">
          This paper uses rubric v{paper.rubric.version}
          {stale ? ` · v${assessment.rubric?.version} is available` : ""}
        </span>
        <div className="inline-actions">
          <button className="button" onClick={() => setDialog("history")}>
            <History size={15} />
            Review history
          </button>
          {canEdit &&
            (stale || ["approved", "released"].includes(paper.status)) && (
              <button
                className="button"
                onClick={() => setDialog("reevaluate")}
              >
                <RotateCcw size={15} />
                Re-evaluate paper
              </button>
            )}
          {canEdit && paper.extraction?.reviewed_by && (
            <button className="button" onClick={() => setDialog("calibration")}>
              Capture calibration example
            </button>
          )}
        </div>
      </div>
      {paper.released_decision_id && paper.status !== "released" && (
        <p className="notice">
          Re-evaluation in progress. The previous released result stays visible
          to the student until you release its replacement.
        </p>
      )}
      {dialog === "history" && (
        <HistoryDialog paper={paper} close={() => setDialog("")} />
      )}
      {dialog === "reevaluate" && (
        <ReevaluateDialog
          paper={paper}
          assessment={assessment}
          close={() => setDialog("")}
        />
      )}
      {dialog === "calibration" && (
        <CalibrationDialog paper={paper} close={() => setDialog("")} />
      )}
    </>
  );
}

function ReevaluateDialog({
  paper,
  assessment,
  close,
}: {
  paper: Paper;
  assessment: Assessment;
  close: () => void;
}) {
  const [reason, setReason] = useState("");
  const query = useQueryClient();
  const action = useMutation({
    mutationFn: () =>
      api(`/v1/submissions/${paper.id}/reevaluate`, {
        method: "POST",
        body: JSON.stringify({
          rubric_id: assessment.rubric!.id,
          base_extraction_version: paper.extraction?.version ?? 0,
          reason,
        }),
      }),
    onSuccess: () => {
      refreshPaper(query, paper);
      close();
    },
  });
  return (
    <Modal title="Re-evaluate this paper" close={close}>
      <p>
        Use approved rubric v{assessment.rubric?.version}. Previous marks and
        feedback stay in history. You’ll review the extraction again, approve
        fresh marks, and separately release the replacement.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          action.mutate();
        }}
      >
        <label>
          Reason for re-evaluation
          <textarea
            required
            minLength={3}
            maxLength={2000}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
        <Notice error={action.error} />
        <footer>
          <button type="button" className="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={action.isPending}>
            Start re-evaluation
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function HistoryDialog({ paper, close }: { paper: Paper; close: () => void }) {
  const history = useQuery({
    queryKey: ["review-history", paper.id],
    queryFn: () =>
      api<S["ReviewHistory"]>(`/v1/submissions/${paper.id}/history`),
  });
  return (
    <Modal title="Review history" close={close}>
      <Notice error={history.error} />
      {history.isPending ? (
        <p>Loading preserved history…</p>
      ) : (
        <>
          <p className="muted small">
            Rubrics, extractions, question reviews, approvals, and releases
            retain their own records.
          </p>
          {history.data?.reevaluations.map((r) => (
            <article className="history-event" key={r.id}>
              <strong>
                Re-evaluation · {new Date(r.created_at).toLocaleString()}
              </strong>
              <p>{r.reason}</p>
              <small className="muted">
                Rubric v
                {
                  history.data?.rubrics.find((b) => b.id === r.from_rubric_id)
                    ?.version
                }{" "}
                → v
                {
                  history.data?.rubrics.find((b) => b.id === r.to_rubric_id)
                    ?.version
                }
              </small>
            </article>
          ))}
          {history.data?.decisions.map((d) => {
            const rubric = history.data?.rubrics.find(
              (r) => r.id === d.rubric_id,
            );
            const release = history.data?.releases.find(
              (r) => r.decision_id === d.id,
            );
            return (
              <article className="history-event" key={d.id}>
                <header>
                  <strong>
                    {score(d.total)} / {score(d.maximum)} · rubric v
                    {rubric?.version}
                  </strong>
                  <span className="status">
                    {release ? "Released" : "Approved only"}
                  </span>
                </header>
                <p>{d.feedback}</p>
                <p className="small muted">{d.reason}</p>
                {rubric && (
                  <FeedbackCards
                    questions={rubric.questions}
                    marks={d.marks}
                    feedback={d.question_feedback}
                  />
                )}
                <small className="muted">
                  Approved {new Date(d.created_at).toLocaleString()}
                  {release
                    ? ` · released ${new Date(release.created_at).toLocaleString()}`
                    : ""}
                </small>
              </article>
            );
          })}
          <div className="history-event">
            <strong>Extraction versions</strong>
            {history.data?.extractions.map((e) => (
              <details key={e.id}>
                <summary>
                  v{e.version} · {e.source} ·{" "}
                  {e.reviewed_by ? "Reviewed" : "Needs review"}
                </summary>
                {e.answers.map((a) => (
                  <blockquote key={a.question_id}>
                    {a.text || "Blank answer"}
                  </blockquote>
                ))}
              </details>
            ))}
          </div>
          <p className="small muted">
            {history.data?.question_reviews.length ?? 0} saved question review
            snapshots.
          </p>
        </>
      )}
    </Modal>
  );
}

function CalibrationDialog({
  paper,
  close,
}: {
  paper: Paper;
  close: () => void;
}) {
  const [marks, setMarks] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      paper.rubric.questions.flatMap((q) =>
        q.criteria.map((c) => [
          c.id,
          paper.decision?.marks.find((m) => m.criterion_id === c.id)?.mark ??
            paper.question_reviews
              .flatMap((r) => r.marks)
              .find((m) => m.criterion_id === c.id)?.mark ??
            "",
        ]),
      ),
    ),
  );
  const [band, setBand] = useState("middle");
  const [note, setNote] = useState("");
  // Enter reference marks independently; linking a proposal is always explicit.
  const [compare, setCompare] = useState(false);
  const query = useQueryClient();
  const save = useMutation({
    mutationFn: () =>
      api(`/v1/submissions/${paper.id}/calibrations`, {
        method: "POST",
        body: JSON.stringify({
          extraction_id: paper.extraction!.id,
          rubric_id: paper.rubric.id,
          proposal_id: compare ? paper.proposal?.id : null,
          band,
          note,
          marks: Object.entries(marks).map(([criterion_id, mark]) => ({
            criterion_id,
            mark,
          })),
        }),
      }),
    onSuccess: () => {
      refreshPaper(query, paper);
      close();
    },
  });
  return (
    <Modal title="Capture calibration example" close={close}>
      <p className="muted">
        Enter the teacher’s reference marks. This saves an example against
        rubric v{paper.rubric.version}; it does not approve or release any
        result.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <label>
          Example band
          <select value={band} onChange={(e) => setBand(e.target.value)}>
            <option value="low">Low</option>
            <option value="middle">Middle</option>
            <option value="high">High</option>
          </select>
        </label>
        {paper.rubric.questions.map((q) => (
          <fieldset className="calibration-question" key={q.id}>
            <legend>
              {q.label} · {q.prompt}
            </legend>
            {q.criteria.map((c) => (
              <label key={c.id}>
                {c.label}
                <input
                  aria-label={`Calibration score: ${c.label}`}
                  type="number"
                  min={0}
                  max={c.maximum}
                  step="0.01"
                  required
                  value={marks[c.id]}
                  onChange={(e) =>
                    setMarks({ ...marks, [c.id]: e.target.value })
                  }
                />
              </label>
            ))}
          </fieldset>
        ))}
        <label>
          Why this is a useful example
          <textarea
            required
            minLength={3}
            maxLength={2000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
        {paper.proposal ? (
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={compare}
              onChange={(e) => setCompare(e.target.checked)}
            />
            Compare against the current {paper.proposal.model} proposal.
          </label>
        ) : (
          <p className="small muted">
            Reference only. Request a local grading suggestion first to capture
            a model comparison.
          </p>
        )}
        <Notice error={save.error} />
        <footer>
          <button type="button" className="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={save.isPending}>
            Save calibration example
          </button>
        </footer>
      </form>
    </Modal>
  );
}

export function FeedbackCards({
  questions,
  marks,
  feedback,
}: {
  questions: Question[];
  marks: S["DecisionOutput"]["marks"];
  feedback?: Record<string, string>;
}) {
  return (
    <div className="feedback-cards">
      {questions.map((q) => (
        <section className="feedback-card" key={q.id}>
          <header>
            <h4>{q.label}</h4>
            <strong>
              {score(
                q.criteria.reduce(
                  (sum, c) =>
                    sum +
                    Number(
                      marks.find((m) => m.criterion_id === c.id)?.mark ?? 0,
                    ),
                  0,
                ),
              )}{" "}
              / {score(q.maximum)}
            </strong>
          </header>
          <p className="small muted">{q.prompt}</p>
          {feedback?.[q.id] && (
            <p className="question-feedback">{feedback[q.id]}</p>
          )}
          <ul>
            {q.criteria.map((c) => (
              <li key={c.id}>
                <span>{c.label}</span>
                <strong>
                  {score(marks.find((m) => m.criterion_id === c.id)?.mark ?? 0)}{" "}
                  / {score(c.maximum)}
                </strong>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
