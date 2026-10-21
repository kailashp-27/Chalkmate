"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BrainCircuit, Sparkles, BookOpen } from "lucide-react";
import { api, downloadApi } from "../lib/api";
import type { components } from "../lib/api-schema";
import { InfoTip, Modal, Notice } from "./ui";
import { AssignmentDetail, refreshFollowup } from "./assignments-workspace";
import { MaterialEditor, MaterialPreview } from "./teaching-material";
type S = components["schemas"];
type Run = S["RunOutput"];
type Source = S["EvidenceSource"];
export type Material = S["MaterialContent"];
const number = (v: string | number | null) =>
  v === null
    ? "—"
    : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });

export function IntelligenceWorkspace({
  classroom,
}: {
  classroom: S["ClassroomOutput"];
}) {
  const [id, setId] = useState("");
  const data = useQuery({
    queryKey: ["assessments", classroom.id],
    queryFn: () =>
      api<S["AssessmentOutput"][]>(
        `/v1/classrooms/${classroom.id}/assessments`,
      ),
  });
  return (
    <div className="tab-content intelligence-workspace">
      <div className="section-heading">
        <div>
          <span className="eyebrow">TEACHING INTELLIGENCE</span>
          <h3>
            Shape the next lesson.{" "}
            <InfoTip label="About teaching intelligence">
              Reviewed marks show patterns. Inspect answer evidence before
              accepting findings or drafting practice. AI suggestions always
              need your review.
            </InfoTip>
          </h3>
        </div>
        <BrainCircuit size={26} />
      </div>
      <Notice error={data.error} />
      <label>
        Assessment to explore
        <select value={id} onChange={(e) => setId(e.target.value)}>
          <option value="">Choose an assessment</option>
          {data.data
            ?.filter((a) => a.status === "active")
            .map((a) => (
              <option key={a.id} value={a.id}>
                {a.title}
              </option>
            ))}
        </select>
      </label>
      {id ? (
        <IntelligenceAssessment key={id} id={id} classroom={classroom} />
      ) : (
        <div className="paper-empty">
          <BrainCircuit size={34} />
          <h3>Start with reviewed evidence.</h3>
          <p>Choose an assessment to explore.</p>
        </div>
      )}
    </div>
  );
}
function IntelligenceAssessment({
  id,
  classroom,
}: {
  id: string;
  classroom: S["ClassroomOutput"];
}) {
  const query = useQueryClient();
  const editable = classroom.can_edit && !classroom.archived;
  const [qid, setQid] = useState("");
  const [topic, setTopic] = useState("");
  const [model, setModel] = useState("");
  const [explicit, setExplicit] = useState(false);
  const [ids, setIds] = useState<string[]>([]);
  const [sources, setSources] = useState<Source[] | null>(null);
  const [manual, setManual] = useState(false);
  const [selected, setSelected] = useState("");
  const summary = useQuery({
    queryKey: ["topic-summary", id],
    queryFn: () =>
      api<S["SummaryOutput"]>(`/v1/assessments/${id}/topic-summary`),
  });
  const roster = useQuery({
    queryKey: ["students", classroom.id],
    queryFn: () =>
      api<S["StudentOutput"][]>(`/v1/classrooms/${classroom.id}/students`),
  });
  const runs = useQuery({
    queryKey: ["intelligence-runs", id],
    queryFn: () => api<Run[]>(`/v1/assessments/${id}/intelligence-runs`),
    refetchInterval: (q) =>
      q.state.data?.some((r) => ["queued", "running"].includes(r.status))
        ? 5000
        : false,
  });
  const request = {
    model: model || null,
    question_id: qid,
    topic,
    student_ids: explicit ? ids : null,
  };
  const refresh = () => {
    void query.invalidateQueries({ queryKey: ["intelligence-runs", id] });
    void query.invalidateQueries({ queryKey: ["intelligence-run"] });
  };
  const evidence = useMutation({
    mutationFn: () =>
      api<Source[]>(`/v1/assessments/${id}/evidence-preview`, {
        method: "POST",
        body: JSON.stringify(request),
      }),
    onSuccess: setSources,
  });
  const start = useMutation({
    mutationFn: (manualResult?: S["AnalysisResult"]) =>
      api<Run>(`/v1/assessments/${id}/intelligence-runs`, {
        method: "POST",
        body: JSON.stringify({
          ...request,
          manual_result: manualResult ?? null,
        }),
      }),
    onSuccess: (r) => {
      setManual(false);
      setSelected(r.id);
      refresh();
    },
  });
  if (selected)
    return (
      <RunInspector
        key={selected}
        runId={selected}
        classroom={classroom}
        back={() => {
          setSelected("");
          refresh();
        }}
        openRun={setSelected}
      />
    );
  return (
    <>
      <Notice error={summary.error ?? roster.error ?? runs.error} />
      {summary.data && (
        <>
          <div className="intelligence-stats">
            {[
              [summary.data.active_students, "active students"],
              [summary.data.missing, "missing papers"],
              [summary.data.unapproved, "awaiting approval"],
              [summary.data.rubric_mismatch, "different rubric"],
            ].map(([count, label]) => (
              <div key={label}>
                <strong>{count}</strong>
                <span>{label}</span>
              </div>
            ))}
          </div>
          <h3>Topic overview</h3>
          <p className="small muted">
            Rubric v{summary.data.rubric_version ?? "—"}. Averages use approved
            question marks; missing work is excluded. {summary.data.withdrawn}{" "}
            withdrawn.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>QUESTION / TOPIC</th>
                  <th>REVIEWED</th>
                  <th>AVERAGE</th>
                  <th>FULL / PARTIAL / ZERO</th>
                  <th>EVIDENCE</th>
                </tr>
              </thead>
              <tbody>
                {summary.data.topics.map((t) => (
                  <tr key={t.question_id}>
                    <td>
                      <strong>{t.label}</strong>
                      <span className="block muted small">{t.prompt}</span>
                    </td>
                    <td>{t.reviewed}</td>
                    <td>
                      {number(t.average)} / {number(t.maximum)}
                    </td>
                    <td>
                      {t.full_credit} / {t.partial_credit} / {t.zero_credit}
                    </td>
                    <td>
                      {t.analyzable} readable · {t.unreadable} unreadable ·{" "}
                      {t.blank} blank
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {editable && (
        <section className="intelligence-panel">
          <span className="eyebrow">FIND A TEACHING PATTERN</span>
          <h3>Choose the evidence to inspect</h3>
          <LocalModelSelect
            label="Local analysis model"
            value={model}
            change={setModel}
          />
          <form
            onChange={() => setSources(null)}
            onSubmit={(e) => {
              e.preventDefault();
              start.mutate(undefined);
            }}
          >
            <div className="followup-filter-grid">
              <label>
                Question for analysis
                <select
                  required
                  value={qid}
                  onChange={(e) => {
                    setQid(e.target.value);
                    setTopic(
                      summary.data?.topics
                        .find((t) => t.question_id === e.target.value)
                        ?.prompt.slice(0, 160) ?? "",
                    );
                  }}
                >
                  <option value="">Choose a current rubric question</option>
                  {summary.data?.topics.map((t) => (
                    <option key={t.question_id} value={t.question_id}>
                      {t.label} · {t.prompt.slice(0, 70)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Teaching topic
                <input
                  required
                  minLength={3}
                  maxLength={160}
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                />
              </label>
            </div>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={explicit}
                onChange={(e) => setExplicit(e.target.checked)}
              />
              Choose a specific student subset
            </label>
            {explicit && (
              <div className="intelligence-cohort">
                {roster.data
                  ?.filter((s) => s.status === "active")
                  .map((s) => (
                    <label className="checkbox-label" key={s.id}>
                      <input
                        type="checkbox"
                        checked={ids.includes(s.id)}
                        onChange={(e) =>
                          setIds(
                            e.target.checked
                              ? [...ids, s.id]
                              : ids.filter((id) => id !== s.id),
                          )
                        }
                      />
                      {s.name} · {s.registration_number}
                    </label>
                  ))}
              </div>
            )}
            <p className="small muted">
              Uses reviewed, readable, nonblank answers from the current
              approved rubric. Up to 30 students per analysis; oversized inputs
              require a smaller explicit subset. Local Ollama suggests patterns;
              you review the evidence.
            </p>
            <Notice error={evidence.error ?? start.error} />
            <div className="inline-actions">
              <button
                type="button"
                className="button"
                disabled={!qid || topic.length < 3 || evidence.isPending}
                onClick={() => evidence.mutate()}
              >
                Inspect source answers
              </button>
              <button
                className="button primary"
                disabled={!qid || topic.length < 3 || start.isPending}
              >
                <Sparkles size={15} />
                Analyze with local Ollama
              </button>
              <button
                type="button"
                className="text-button"
                disabled={!sources?.length}
                onClick={() => setManual(true)}
              >
                Record a manual finding
              </button>
            </div>
          </form>
          {sources && (
            <details open className="source-preview">
              <summary>{sources.length} source answers selected</summary>
              {sources.map((s) => (
                <SourceAnswer key={s.source_id} source={s} />
              ))}
            </details>
          )}
        </section>
      )}
      <section className="intelligence-history">
        <span className="eyebrow">PRESERVED TEACHING HISTORY</span>
        <h3>Analyses & practice materials</h3>
        {runs.data?.length ? (
          runs.data.map((r) => (
            <button
              key={r.id}
              className="intelligence-run-row"
              onClick={() => setSelected(r.id)}
            >
              <BrainCircuit size={22} />
              <div>
                <strong>
                  {r.kind === "analysis"
                    ? "Evidence analysis"
                    : r.request.material_type === "revision"
                      ? "Revision pack"
                      : "Remedial practice"}
                </strong>
                <small>
                  {String(r.request.topic ?? "Teaching material")} ·{" "}
                  {new Date(r.created_at).toLocaleString()} · {r.model}
                </small>
              </div>
              <span className="status">
                {r.stale ? "Source changed" : r.status}
              </span>
            </button>
          ))
        ) : (
          <p className="empty-inline">No teaching runs yet.</p>
        )}
      </section>
      {manual && sources && (
        <ManualFinding
          sources={sources}
          pending={start.isPending}
          error={start.error}
          close={() => setManual(false)}
          save={(r) => start.mutate(r)}
        />
      )}
    </>
  );
}
function SourceAnswer({
  source,
  quote,
  page,
}: {
  source: Source;
  quote?: string;
  page?: number;
}) {
  return (
    <article className="intelligence-source">
      <header>
        <strong>
          {source.source_id} · {source.student_name}
        </strong>
        <small>
          {number(source.mark)} / {number(source.maximum)} · page{" "}
          {page ?? source.page_from}
        </small>
      </header>
      {quote && <blockquote>{quote}</blockquote>}
      <details>
        <summary>Reviewed answer and source versions</summary>
        <p className="preserve-text">{source.text}</p>
        <small className="muted">
          Decision {source.decision_id} · Extraction {source.extraction_id} ·
          Paper {source.submission_id}
        </small>
      </details>
    </article>
  );
}
function ManualFinding({
  sources,
  pending,
  error,
  close,
  save,
}: {
  sources: Source[];
  pending: boolean;
  error: Error | null;
  close: () => void;
  save: (r: S["AnalysisResult"]) => void;
}) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<S["Finding"]["kind"]>("needs_practice");
  const [explanation, setExplanation] = useState("");
  const [action, setAction] = useState("");
  const [sid, setSid] = useState(sources[0].source_id);
  const [quote, setQuote] = useState("");
  const [page, setPage] = useState(sources[0].page_from);
  const source = sources.find((s) => s.source_id === sid)!;
  return (
    <Modal title="Record an evidence-backed finding" close={close}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save({
            findings: [
              {
                title,
                kind,
                explanation,
                suggested_action: action,
                citations: [{ source_id: sid, quote, page }],
              },
            ],
            limitations:
              "Teacher-authored finding from selected reviewed answers; not a class-wide diagnosis.",
          });
        }}
      >
        <label>
          Finding title
          <input
            required
            minLength={3}
            maxLength={160}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label>
          Finding type
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as typeof kind)}
          >
            <option value="needs_practice">Needs practice</option>
            <option value="misconception">Possible misconception</option>
            <option value="strength">Strength</option>
          </select>
        </label>
        <label>
          Evidence explanation
          <textarea
            required
            maxLength={3000}
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
          />
        </label>
        <label>
          Suggested teaching action
          <textarea
            required
            maxLength={3000}
            value={action}
            onChange={(e) => setAction(e.target.value)}
          />
        </label>
        <label>
          Evidence source
          <select
            value={sid}
            onChange={(e) => {
              setSid(e.target.value);
              setPage(
                sources.find((s) => s.source_id === e.target.value)!.page_from,
              );
              setQuote("");
            }}
          >
            {sources.map((s) => (
              <option key={s.source_id} value={s.source_id}>
                {s.source_id} · {s.student_name}
              </option>
            ))}
          </select>
        </label>
        <p className="quoted-source">{source.text}</p>
        <label>
          Exact evidence quote
          <textarea
            required
            maxLength={1000}
            value={quote}
            onChange={(e) => setQuote(e.target.value)}
          />
        </label>
        <label>
          Evidence page
          <input
            required
            type="number"
            min={source.page_from}
            max={source.page_to}
            value={page}
            onChange={(e) => setPage(Number(e.target.value))}
          />
        </label>
        <Notice error={error} />
        <footer>
          <button type="button" className="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={pending}>
            Save manual finding
          </button>
        </footer>
      </form>
    </Modal>
  );
}
function RunInspector({
  runId,
  classroom,
  back,
  openRun,
}: {
  runId: string;
  classroom: S["ClassroomOutput"];
  back: () => void;
  openRun: (id: string) => void;
}) {
  const query = useQueryClient();
  const [reviewIndex, setReviewIndex] = useState<number | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [kind, setKind] = useState<"remedial" | "revision">("remedial");
  const [guidance, setGuidance] = useState("");
  const [model, setModel] = useState("");
  const [manual, setManual] = useState(false);
  const [assignmentId, setAssignmentId] = useState("");
  const data = useQuery({
    queryKey: ["intelligence-run", runId],
    queryFn: () => api<Run>(`/v1/intelligence-runs/${runId}`),
    refetchInterval: (q) =>
      q.state.data && ["queued", "running"].includes(q.state.data.status)
        ? 4000
        : false,
  });
  const refresh = () => {
    void query.invalidateQueries({ queryKey: ["intelligence-run", runId] });
    void query.invalidateQueries({ queryKey: ["intelligence-runs"] });
    void query.invalidateQueries({ queryKey: ["teaching-materials"] });
  };
  const action = useMutation({
    mutationFn: (kind: "cancel" | "retry") =>
      api(`/v1/intelligence-runs/${runId}/${kind}`, { method: "POST" }),
    onSuccess: refresh,
  });
  const generate = useMutation({
    mutationFn: (content?: Material) =>
      api<Run>(
        `/v1/assessments/${data.data!.assessment_id}/teaching-material`,
        {
          method: "POST",
          body: JSON.stringify({
            source_run_id: runId,
            review_ids: selected,
            material_type: kind,
            model: model || null,
            guidance,
            manual_content: content ?? null,
          }),
        },
      ),
    onSuccess: (r) => {
      setManual(false);
      refresh();
      openRun(r.id);
    },
  });
  if (assignmentId)
    return (
      <AssignmentDetail
        versionId={assignmentId}
        back={() => setAssignmentId("")}
        openVersion={setAssignmentId}
      />
    );
  if (!data.data)
    return (
      <>
        <button className="text-button" onClick={back}>
          <ArrowLeft size={15} />
          Topic overview
        </button>
        <Notice error={data.error} />
        {data.isPending && <p>Opening teaching evidence…</p>}
      </>
    );
  const item = data.data;
  const editable = classroom.can_edit && !classroom.archived;
  const canReview = editable && !item.stale && item.status === "succeeded";
  const findings =
    item.kind === "analysis" && item.result
      ? (item.result as unknown as S["AnalysisResult"])
      : null;
  const latest = new Map<number, S["ReviewOutput"]>();
  for (const r of item.reviews)
    if (
      !latest.has(r.finding_index) ||
      latest.get(r.finding_index)!.version < r.version
    )
      latest.set(r.finding_index, r);
  const accepted = [...latest.values()].filter(
    (r) => r.disposition === "accepted",
  );
  return (
    <>
      <button className="text-button back-button" onClick={back}>
        <ArrowLeft size={15} />
        Topic overview
      </button>
      <div className="section-heading">
        <div>
          <span className="eyebrow">
            {item.kind === "analysis"
              ? "REVIEW THE EVIDENCE"
              : "REVIEW THE TEACHING MATERIAL"}
          </span>
          <h3>
            {item.kind === "analysis"
              ? String(item.request.topic)
              : item.request.material_type === "revision"
                ? "Revision pack"
                : "Remedial practice"}
          </h3>
          <p className="small muted">
            {item.model} · {item.prompt_version} · {item.attempts} processing
            attempts
          </p>
        </div>
        <span className="status">{item.status}</span>
      </div>
      <Notice error={data.error ?? action.error} />
      {item.stale && (
        <p className="notice error">
          {item.stale_reason} This record is preserved for inspection.
        </p>
      )}
      {item.error && <p className="notice">{item.error}</p>}
      {["queued", "running"].includes(item.status) && (
        <p className="notice" role="status">
          Local Ollama is{" "}
          {item.status === "queued"
            ? "waiting to process these sources"
            : "working on this draft"}
          . You can leave this page; the run is saved.
        </p>
      )}
      {editable && (
        <div className="inline-actions">
          {["queued", "running", "failed"].includes(item.status) && (
            <button
              className="button"
              disabled={action.isPending}
              onClick={() => action.mutate("cancel")}
            >
              Cancel teaching run
            </button>
          )}
          {item.status === "failed" && !item.stale && item.attempts < 3 && (
            <button
              className="button"
              disabled={action.isPending}
              onClick={() => action.mutate("retry")}
            >
              Retry local generation
            </button>
          )}
        </div>
      )}
      {findings && (
        <>
          <p className="notice">{findings.limitations}</p>
          {!findings.findings.length && (
            <p className="empty-inline">
              No evidence-backed finding proposed. Inspect the reviewed answers
              or record a manual finding.
            </p>
          )}
          {findings.findings.map((f, index) => {
            const review = latest.get(index);
            return (
              <article className="finding-card" key={index}>
                <header>
                  <span className="eyebrow">{f.kind.replaceAll("_", " ")}</span>
                  <span className="status">
                    {review?.disposition ?? "Needs teacher review"}
                  </span>
                </header>
                <h3>{f.title}</h3>
                <p>{f.explanation}</p>
                <p className="small muted">
                  Supported by{" "}
                  {new Set(f.citations.map((c) => c.source_id)).size} of{" "}
                  {item.sources.length} selected reviewed answers.
                </p>
                <div className="teaching-action">
                  <strong>Suggested next step</strong>
                  <p>{f.suggested_action}</p>
                </div>
                <details>
                  <summary>
                    Inspect {f.citations.length} evidence citations
                  </summary>
                  {f.citations.map((c) => {
                    const source = item.sources.find(
                      (s) => s.source_id === c.source_id,
                    );
                    return source ? (
                      <SourceAnswer
                        key={c.source_id}
                        source={source}
                        quote={c.quote}
                        page={c.page}
                      />
                    ) : null;
                  })}
                </details>
                {review && (
                  <p className="small muted">
                    Teacher review v{review.version}: {review.reason}
                  </p>
                )}
                {canReview && (
                  <button
                    className="button"
                    onClick={() => setReviewIndex(index)}
                  >
                    {review ? "Review finding again" : "Review finding"}
                  </button>
                )}
                <details>
                  <summary>Review history</summary>
                  {item.reviews
                    .filter((r) => r.finding_index === index)
                    .map((r) => (
                      <p className="small" key={r.id}>
                        v{r.version} · {r.disposition} · {r.reason}
                      </p>
                    ))}
                </details>
              </article>
            );
          })}
          {canReview && accepted.length > 0 && (
            <section className="intelligence-panel">
              <span className="eyebrow">FROM FINDINGS TO PRACTICE</span>
              <h3>Prepare a teacher-reviewed next step</h3>
              {accepted.map((r) => (
                <label className="checkbox-label" key={r.id}>
                  <input
                    type="checkbox"
                    checked={selected.includes(r.id)}
                    onChange={(e) =>
                      setSelected(
                        e.target.checked
                          ? [...selected, r.id]
                          : selected.filter((id) => id !== r.id),
                      )
                    }
                  />
                  {findings.findings[r.finding_index].title}
                </label>
              ))}
              <LocalModelSelect
                label="Local material model"
                value={model}
                change={setModel}
              />
              <label>
                Material type
                <select
                  value={kind}
                  onChange={(e) => setKind(e.target.value as typeof kind)}
                >
                  <option value="remedial">Remedial assignment</option>
                  <option value="revision">Revision pack</option>
                </select>
              </label>
              <label>
                Teaching guidance (optional)
                <textarea
                  maxLength={1500}
                  value={guidance}
                  onChange={(e) => setGuidance(e.target.value)}
                />
              </label>
              <Notice error={generate.error} />
              <div className="inline-actions">
                <button
                  className="button primary"
                  disabled={!selected.length || generate.isPending}
                  onClick={() => generate.mutate(undefined)}
                >
                  <Sparkles size={15} />
                  Generate practice with Ollama
                </button>
                <button
                  className="button"
                  disabled={!selected.length}
                  onClick={() => setManual(true)}
                >
                  Write practice manually
                </button>
              </div>
              <p className="small muted">
                Generation uses accepted teaching concepts. Individual marks and
                source citations stay in the private evidence view.
              </p>
            </section>
          )}
        </>
      )}
      {item.kind === "material" && item.status === "succeeded" && (
        <MaterialReview
          run={item}
          editable={canReview}
          classroomId={classroom.id}
          openAssignment={setAssignmentId}
        />
      )}
      <details className="intelligence-provenance">
        <summary>Source and model provenance</summary>
        <p className="small muted">
          Run {item.id}
          <br />
          Rubric {item.rubric_id}
          <br />
          Input {item.input_digest}
          <br />
          Model digest{" "}
          {item.model_digest || "Recorded when processing completes"}
        </p>
        <p className="small muted">{JSON.stringify(item.usage)}</p>
      </details>
      {reviewIndex !== null && findings && (
        <FindingReviewDialog
          runId={runId}
          index={reviewIndex}
          current={latest.get(reviewIndex)}
          title={findings.findings[reviewIndex].title}
          close={() => setReviewIndex(null)}
          saved={() => {
            setReviewIndex(null);
            setSelected([]);
            refresh();
          }}
        />
      )}
      {manual && (
        <MaterialEditor
          kind={kind}
          pending={generate.isPending}
          error={generate.error}
          close={() => setManual(false)}
          save={(content) => generate.mutate(content)}
        />
      )}
    </>
  );
}
function FindingReviewDialog({
  runId,
  index,
  current,
  title,
  close,
  saved,
}: {
  runId: string;
  index: number;
  current?: S["ReviewOutput"];
  title: string;
  close: () => void;
  saved: () => void;
}) {
  const [disposition, setDisposition] = useState(
    current?.disposition ?? "accepted",
  );
  const [reason, setReason] = useState("");
  const action = useMutation({
    mutationFn: () =>
      api(`/v1/intelligence-runs/${runId}/findings/${index}/reviews`, {
        method: "POST",
        body: JSON.stringify({
          base_version: current?.version ?? 0,
          disposition,
          reason,
        }),
      }),
    onSuccess: saved,
  });
  return (
    <Modal title="Review this teaching finding" close={close}>
      <p>
        <strong>{title}</strong>
      </p>
      <p className="muted">
        Inspect the cited answer and rubric. Accepting an interpretation does
        not change grades or contact students.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          action.mutate();
        }}
      >
        <label>
          Finding decision
          <select
            value={disposition}
            onChange={(e) => setDisposition(e.target.value)}
          >
            <option value="accepted">Accept for teaching follow-up</option>
            <option value="dismissed">Dismiss this suggestion</option>
          </select>
        </label>
        <label>
          Teacher review reason
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
            Save finding review
          </button>
        </footer>
      </form>
    </Modal>
  );
}
function MaterialReview({
  run,
  editable,
  classroomId,
  openAssignment,
}: {
  run: Run;
  editable: boolean;
  classroomId: string;
  openAssignment: (id: string) => void;
}) {
  const query = useQueryClient();
  const [vid, setVid] = useState("");
  const [editing, setEditing] = useState(false);
  const [approving, setApproving] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [reason, setReason] = useState("");
  const versions = useQuery({
    queryKey: ["teaching-materials", run.id],
    queryFn: () =>
      api<S["MaterialOutput"][]>(`/v1/intelligence-runs/${run.id}/materials`),
  });
  const item = versions.data?.find((v) => v.id === vid) ?? versions.data?.[0];
  const latest = item?.id === versions.data?.[0]?.id;
  const refresh = () => {
    void query.invalidateQueries({ queryKey: ["teaching-materials", run.id] });
    refreshFollowup(query, classroomId);
  };
  const edit = useMutation({
    mutationFn: ({ content, reason }: { content: Material; reason: string }) =>
      api<S["MaterialOutput"]>(`/v1/intelligence-runs/${run.id}/materials`, {
        method: "POST",
        body: JSON.stringify({ base_version: item!.version, content, reason }),
      }),
    onSuccess: (v) => {
      setEditing(false);
      setVid(v.id);
      refresh();
    },
  });
  const approve = useMutation({
    mutationFn: () =>
      api<S["ApprovalOutput"]>(`/v1/teaching-materials/${item!.id}/approve`, {
        method: "POST",
        body: JSON.stringify({
          base_version: item!.version,
          confirmed,
          reason,
        }),
      }),
    onSuccess: () => {
      setApproving(false);
      refresh();
    },
  });
  const download = useMutation({
    mutationFn: (key: boolean) =>
      downloadApi(
        `/v1/teaching-materials/${item!.id}/export?answer_key=${key}`,
        `chalkmate-${key ? "teacher-key" : "student-practice"}-v${item!.version}.md`,
      ),
  });
  return (
    <section className="material-review">
      <Notice
        error={versions.error ?? edit.error ?? approve.error ?? download.error}
      />
      {versions.data && versions.data.length > 1 && (
        <label>
          Material version
          <select value={item?.id} onChange={(e) => setVid(e.target.value)}>
            {versions.data.map((v) => (
              <option value={v.id} key={v.id}>
                Version {v.version} · {v.reason}
              </option>
            ))}
          </select>
        </label>
      )}
      {item && (
        <>
          <div className="section-heading">
            <div>
              <span className="eyebrow">MATERIAL VERSION {item.version}</span>
              <h3>{item.content.title}</h3>
            </div>
            <span className="status">
              {item.approval_assignment_version_id
                ? "Approved to assignment draft"
                : "Teacher review required"}
            </span>
          </div>
          <MaterialPreview content={item.content} />
          <div className="inline-actions">
            <button
              className="button"
              disabled={download.isPending}
              onClick={() => download.mutate(false)}
            >
              Export student pack
            </button>
            <button
              className="button"
              disabled={download.isPending}
              onClick={() => download.mutate(true)}
            >
              Export private teacher key
            </button>
            {editable && latest && (
              <button className="button" onClick={() => setEditing(true)}>
                Edit material as new version
              </button>
            )}
            {editable && latest && !item.approval_assignment_version_id && (
              <button
                className="button primary"
                onClick={() => {
                  setConfirmed(false);
                  setReason("");
                  setApproving(true);
                }}
              >
                Review & approve material
              </button>
            )}
            {item.approval_assignment_version_id && (
              <button
                className="button primary"
                onClick={() =>
                  openAssignment(item.approval_assignment_version_id!)
                }
              >
                <BookOpen size={15} />
                Open assignment draft
              </button>
            )}
          </div>
          <p className="small muted">
            Approval creates an unpublished assignment with student practice
            only. Review the audience and publish separately. Answer keys stay
            private.
          </p>
          {editing && (
            <MaterialEditor
              key={item.id}
              current={item.content}
              kind={run.request.material_type as "remedial" | "revision"}
              pending={edit.isPending}
              error={edit.error}
              close={() => setEditing(false)}
              save={(content, reason) => edit.mutate({ content, reason })}
            />
          )}
          {approving && (
            <Modal
              title="Approve material to an assignment draft"
              close={() => setApproving(false)}
            >
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  approve.mutate();
                }}
              >
                <p>
                  Create a draft from <strong>{item.content.title}</strong>,
                  version {item.version}. This does not publish or send
                  messages.
                </p>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                  />
                  I reviewed the student content, hints, and separate teacher
                  answers for accuracy and suitability.
                </label>
                <label>
                  Material approval reason
                  <textarea
                    required
                    minLength={3}
                    maxLength={2000}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <Notice error={approve.error} />
                <footer>
                  <button
                    type="button"
                    className="button"
                    onClick={() => setApproving(false)}
                  >
                    Keep reviewing
                  </button>
                  <button
                    className="button primary"
                    disabled={!confirmed || approve.isPending}
                  >
                    Approve & create assignment draft
                  </button>
                </footer>
              </form>
            </Modal>
          )}
        </>
      )}
    </section>
  );
}

function LocalModelSelect({
  label,
  value,
  change,
}: {
  label: string;
  value: string;
  change: (v: string) => void;
}) {
  const data = useQuery({
    queryKey: ["processing-status"],
    queryFn: () => api<S["ProcessingStatus"]>("/v1/processing/status"),
  });
  return (
    <div>
      <label>
        {label}
        <select value={value} onChange={(e) => change(e.target.value)}>
          <option value="">
            Configured model
            {data.data?.grading_model ? ` · ${data.data.grading_model}` : ""}
          </option>
          {data.data?.models.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <p className="small muted">
        Choose an installed local model for this run. Smaller models use less
        memory; every suggestion still needs teacher review. This does not
        change assessment grading.
      </p>
      <Notice error={data.error} />
      {data.data && !data.data.available && (
        <p className="small muted">{data.data.detail}</p>
      )}
      <button
        className="text-button"
        type="button"
        disabled={data.isFetching}
        onClick={() => void data.refetch()}
      >
        Refresh local models
      </button>
    </div>
  );
}
