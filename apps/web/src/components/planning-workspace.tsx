"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  Check,
  CheckCheck,
  FileStack,
  Languages,
  ListChecks,
  Plus,
  Search,
  Sparkles,
  StickyNote,
  Trash2,
  WandSparkles,
} from "lucide-react";
import { api, downloadApi } from "../lib/api";
import type { components } from "../lib/api-schema";
import {
  BankPerformance,
  MarksTemplateFields,
  ReportingTools,
} from "./reporting-tools";
import { InfoTip, Modal, Notice } from "./ui";

type S = components["schemas"];
type Doc = S["PlanningOutput"];
type Content = S["PlanningContent-Input"];
type Kind = S["PlanningInput"]["kind"];
type Class = S["ClassroomOutput"];
const tools = [
  {
    kind: "marks_template",
    title: "Marks template",
    icon: ListChecks,
    hint: "Your columns, your format",
  },
  {
    kind: "syllabus",
    title: "Syllabus",
    icon: BookOpen,
    hint: "Topics & coverage",
  },
  {
    kind: "blueprint",
    title: "Blueprint",
    icon: ListChecks,
    hint: "Balance your paper",
  },
  {
    kind: "paper",
    title: "Question paper",
    icon: FileStack,
    hint: "Draft, check, refine",
  },
  {
    kind: "question_bank",
    title: "Question bank",
    icon: StickyNote,
    hint: "Keep good questions",
  },
  {
    kind: "meeting",
    title: "Meeting notes",
    icon: CheckCheck,
    hint: "Decisions into actions",
  },
  {
    kind: "announcement",
    title: "Translate",
    icon: Languages,
    hint: "Your words, another language",
  },
  {
    kind: "report_template",
    title: "Report template",
    icon: ListChecks,
    hint: "Choose what matters",
  },
] as const;
const columns = [
  "classroom",
  "students",
  "assessments",
  "approved_decisions",
  "assignments",
  "activity_events",
] as const;
const empty = (): Content => ({
  text: "",
  original: "",
  topics: [],
  allocations: [],
  questions: [],
  actions: [],
  columns: [],
  language: "English",
  total_marks: null,
  score_basis: "released",
  include_withdrawn: false,
  export_columns: [],
});
const topic = () => ({ name: "", text: "" });
const question = (): NonNullable<Content["questions"]>[number] => ({
  topic: "",
  text: "",
  marks: "5",
  solution: "",
  rubric: "",
  references: [],
});

export function PlanningWorkspace({ classroom }: { classroom: Class }) {
  const query = useQueryClient();
  const [editing, setEditing] = useState<{
    kind: Kind;
    old?: Doc;
    seed?: Doc;
    variant?: boolean;
  } | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [search, setSearch] = useState("");
  const [history, setHistory] = useState(false);
  const [filter, setFilter] = useState("all");
  const documents = useQuery({
    queryKey: ["planning", classroom.id],
    queryFn: () => api<Doc[]>(`/v1/classrooms/${classroom.id}/planning`),
  });
  const jobs = useQuery({
    queryKey: ["planning-jobs", classroom.id],
    queryFn: async () => {
      const rows = await api<S["chalkmate__planning_schemas__JobOutput"][]>(
        `/v1/classrooms/${classroom.id}/planning-jobs`,
      );
      const cached = query.getQueryData<Doc[]>(["planning", classroom.id]);
      if (
        rows.some(
          (j) =>
            j.result_id && cached && !cached.some((d) => d.id === j.result_id),
        )
      )
        query.invalidateQueries({ queryKey: ["planning", classroom.id] });
      return rows;
    },
    refetchInterval: (q) =>
      q.state.data?.some((j) => ["queued", "running"].includes(j.status))
        ? 3000
        : false,
  });
  const refresh = () => {
    query.invalidateQueries({ queryKey: ["planning", classroom.id] });
    query.invalidateQueries({ queryKey: ["planning-jobs", classroom.id] });
    query.invalidateQueries({ queryKey: ["readiness", classroom.id] });
  };
  const action = useMutation({
    mutationFn: async ({
      path,
      exportKey,
    }: {
      path: string;
      exportKey?: boolean;
    }) =>
      exportKey !== undefined
        ? downloadApi(
            `${path}?teacher_key=${exportKey}`,
            `chalkmate-${exportKey ? "teacher" : "student"}.md`,
          )
        : api<Doc>(path, { method: "POST" }),
    onSuccess: refresh,
  });
  const all = documents.data ?? [];
  const current = all.find((d) => d.id === selected);
  const results = all.filter(
    (d) =>
      (history || d.latest) &&
      (filter === "all" || d.kind === filter) &&
      `${d.title} ${d.content.questions?.map((q) => `${q.topic} ${q.text}`).join(" ")} ${d.content.topics?.map((t) => t.name).join(" ")}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const canEdit = classroom.can_edit && !classroom.archived;
  return (
    <div className="planning-studio tab-content">
      <div className="studio-heading">
        <div>
          <span className="eyebrow">ROOM FOR YOUR NEXT IDEA</span>
          <h2>
            Planning studio{" "}
            <InfoTip label="About planning">
              Start with a syllabus. Approve it, then use it to ground papers
              and questions. Everything stays a private draft until you review
              it. Publishing and sending happen in their own workflows.
            </InfoTip>
          </h2>
        </div>
        <span className="studio-emblem">
          <WandSparkles size={30} />
        </span>
      </div>
      {canEdit && (
        <div className="tool-grid">
          {tools.map(({ kind, title, icon: Icon, hint }) => (
            <button
              key={kind}
              className="tool-tile"
              onClick={() => setEditing({ kind })}
            >
              <span className="tool-icon">
                <Icon size={21} />
              </span>
              <strong>{title}</strong>
              <span>{hint}</span>
              <ArrowRight className="tile-arrow" size={15} />
            </button>
          ))}
        </div>
      )}
      <ReportingTools classroom={classroom} documents={all} />
      <Notice error={documents.error ?? jobs.error ?? action.error} />
      {jobs.data?.some(
        (j) => j.status !== "succeeded" && j.status !== "canceled",
      ) && (
        <details className="quiet-disclosure">
          <summary>
            Local drafts{" "}
            <span className="count">
              {
                jobs.data.filter(
                  (j) => !["succeeded", "canceled"].includes(j.status),
                ).length
              }
            </span>
          </summary>
          {jobs.data
            .filter((j) => !["succeeded", "canceled"].includes(j.status))
            .map((j) => (
              <div className="job-line" key={j.id}>
                <span>
                  <strong>{j.status}</strong> · {j.model}
                  <small>{j.error}</small>
                </span>
                {canEdit && (
                  <div className="button-group">
                    {j.status === "failed" && j.attempts < 3 && (
                      <button
                        className="button small-button"
                        disabled={action.isPending}
                        onClick={() =>
                          action.mutate({
                            path: `/v1/planning-jobs/${j.id}/retry`,
                          })
                        }
                      >
                        Retry
                      </button>
                    )}
                    <button
                      className="text-button"
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({
                          path: `/v1/planning-jobs/${j.id}/cancel`,
                        })
                      }
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            ))}
        </details>
      )}
      <div className="library-toolbar">
        <h3>
          Your library{" "}
          <span className="count">{all.filter((d) => d.latest).length}</span>
        </h3>
        <div className="library-filters">
          <label className="search-field">
            <Search size={16} />
            <input
              aria-label="Search planning library"
              placeholder="Find a topic or draft…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <select
            aria-label="Document type"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">All types</option>
            {tools.map((t) => (
              <option key={t.kind} value={t.kind}>
                {t.title}
              </option>
            ))}
            <option value="report">Reports</option>
          </select>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={history}
              onChange={(e) => setHistory(e.target.checked)}
            />
            History
          </label>
        </div>
      </div>
      {documents.isPending ? (
        <div className="studio-skeleton" role="status">
          Loading your library…
        </div>
      ) : !results.length ? (
        <div className="studio-empty">
          <span className="orbit-mark">
            <Sparkles size={28} />
          </span>
          <h3>
            {search ? "Nothing matched yet." : "Make space for a good idea."}
          </h3>
          <p className="muted">
            {search ? "Try another topic." : "Choose a tool above to begin."}
          </p>
        </div>
      ) : (
        <div className="document-grid">
          {results.map((d) => (
            <button
              className={`document-card ${d.id === selected ? "chosen" : ""}`}
              key={d.id}
              onClick={() => setSelected(d.id)}
            >
              <span className="document-kind">
                {d.kind.replaceAll("_", " ")} <small>v{d.version}</small>
              </span>
              <h3>{d.title}</h3>
              <span
                className={`document-status ${d.approved ? "approved" : ""}`}
              >
                {d.approved ? (
                  <Check size={13} />
                ) : (
                  <span className="draft-dot" />
                )}
                {d.approved
                  ? "Approved"
                  : d.issues.length
                    ? `${d.issues.length} checks to review`
                    : "Ready for review"}
              </span>
            </button>
          ))}
        </div>
      )}
      {current && (
        <Modal title={current.title} close={() => setSelected("")}>
          <div className="planning-preview">
            <div className="button-group">
              <span className="role-tag">
                v{current.version} · {current.approved ? "Approved" : "Draft"}
              </span>
              <InfoTip label="Approval scope">
                Approval records this version only. It does not publish to
                students or send messages. Source quotes support coverage, not
                question accuracy or variant equivalence.
              </InfoTip>
            </div>
            <DocumentBody document={current} />
            {["paper", "question_bank"].includes(current.kind) && (
              <BankPerformance document={current} classroom={classroom} />
            )}
            {current.sources.length > 0 && (
              <details>
                <summary>Sources</summary>
                {current.sources.map((s) => (
                  <p key={String(s.id)}>
                    {String(s.source_id)} · {String(s.title)} · v
                    {String(s.version)}
                  </p>
                ))}
              </details>
            )}
            {current.issues.length > 0 && (
              <div className="planning-checks" role="status">
                <h3>Review checks</h3>
                <ul>
                  {current.issues.map((v) => (
                    <li key={v}>{v}</li>
                  ))}
                </ul>
              </div>
            )}
            <Notice error={action.error} />
            <div className="planning-actions">
              {canEdit && current.latest && current.kind !== "report" && (
                <button
                  className="button"
                  onClick={() => {
                    setSelected("");
                    setEditing({ kind: current.kind, old: current });
                  }}
                >
                  Edit version
                </button>
              )}
              {canEdit && current.latest && !current.approved && (
                <button
                  className="button primary"
                  disabled={action.isPending || current.issues.length > 0}
                  onClick={() =>
                    action.mutate({
                      path: `/v1/planning/${current.id}/approve`,
                    })
                  }
                >
                  <Check size={16} />
                  Approve version
                </button>
              )}
              {canEdit &&
                current.approved &&
                current.latest &&
                current.kind === "report_template" && (
                  <button
                    className="button primary"
                    disabled={action.isPending}
                    onClick={() =>
                      action.mutate({
                        path: `/v1/planning/${current.id}/report`,
                      })
                    }
                  >
                    Build report
                  </button>
                )}
              {canEdit &&
                current.approved &&
                current.latest &&
                ["paper", "question_bank"].includes(current.kind) && (
                  <button
                    className="button"
                    onClick={() => {
                      setSelected("");
                      setEditing({
                        kind: "paper",
                        seed: current,
                        variant: current.kind === "paper",
                      });
                    }}
                  >
                    {current.kind === "paper"
                      ? "Create variant"
                      : "Use in paper"}
                  </button>
                )}
              <button
                className="button"
                disabled={action.isPending}
                onClick={() =>
                  action.mutate({
                    path: `/v1/planning/${current.id}/export`,
                    exportKey: false,
                  })
                }
              >
                <ArrowDownToLine size={15} />
                Student copy
              </button>
              <button
                className="text-button"
                disabled={action.isPending}
                onClick={() =>
                  action.mutate({
                    path: `/v1/planning/${current.id}/export`,
                    exportKey: true,
                  })
                }
              >
                Teacher copy
              </button>
            </div>
          </div>
        </Modal>
      )}
      {editing && (
        <PlanningEditor
          classroom={classroom}
          documents={all}
          {...editing}
          close={() => setEditing(null)}
          done={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}
    </div>
  );
}

function DocumentBody({ document: d }: { document: Doc }) {
  const c = d.content;
  return (
    <div className="document-body">
      {c.text && <p className="preserve-lines">{c.text}</p>}
      {c.topics?.map((t) => (
        <section key={t.name}>
          <h3>{t.name}</h3>
          <p className="preserve-lines">{t.text}</p>
        </section>
      ))}
      {c.total_marks && (
        <p className="role-tag">{String(c.total_marks)} marks</p>
      )}
      {!!c.allocations?.length && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Topic</th>
                <th>Questions</th>
                <th>Marks</th>
                <th>Intent</th>
              </tr>
            </thead>
            <tbody>
              {c.allocations.map((a, i) => (
                <tr key={i}>
                  <td>{a.topic}</td>
                  <td>
                    {a.count} × {String(a.marks)}
                  </td>
                  <td>{Number(a.marks) * a.count}</td>
                  <td>
                    {a.difficulty} · {a.question_type}
                    <small>{a.outcome}</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {c.questions?.map((q, i) => (
        <section className="preview-question" key={i}>
          <div className="section-heading">
            <h3>
              {i + 1}. {q.text}
            </h3>
            <span className="count">{String(q.marks)}</span>
          </div>
          <span className="muted small">{q.topic}</span>
          <details>
            <summary>Answer & marking guide</summary>
            <p className="preserve-lines">{q.solution}</p>
            <p className="preserve-lines muted">{q.rubric}</p>
            {q.references?.map((r, j) => (
              <blockquote key={j}>
                {r.source_id}: “{r.quote}”
              </blockquote>
            ))}
          </details>
        </section>
      ))}
      {!!c.actions?.length && (
        <ul className="meeting-actions">
          {c.actions.map((a, i) => (
            <li key={i}>
              <Check size={16} />
              <span>
                {a.action}
                <small>
                  {a.owner} · {a.deadline}
                </small>
              </span>
            </li>
          ))}
        </ul>
      )}
      {!!c.columns?.length && (
        <div className="source-pills">
          {c.columns.map((col) => (
            <span key={col}>{col.replaceAll("_", " ")}</span>
          ))}
        </div>
      )}
      {c.original && (
        <details>
          <summary>Original text</summary>
          <p className="preserve-lines">{c.original}</p>
        </details>
      )}
    </div>
  );
}

function PlanningEditor({
  classroom,
  documents,
  kind,
  old,
  seed,
  variant,
  close,
  done,
}: {
  classroom: Class;
  documents: Doc[];
  kind: Kind;
  old?: Doc;
  seed?: Doc;
  variant?: boolean;
  close: () => void;
  done: () => void;
}) {
  const [title, setTitle] = useState(
    old?.title ??
      (seed ? `${seed.title} · ${variant ? "Variant B" : "Paper"}` : ""),
  );
  const [content, setContent] = useState<Content>(
    () =>
      old?.content ??
      seed?.content ?? {
        ...empty(),
        export_columns:
          kind === "marks_template"
            ? [
                {
                  field: "registration_number",
                  heading: "Registration number",
                },
                { field: "name", heading: "Name" },
                { field: "status", heading: "Result status" },
                { field: "total", heading: "Total" },
                { field: "maximum", heading: "Maximum" },
              ]
            : [],
        topics: kind === "syllabus" ? [topic()] : [],
        allocations:
          kind === "blueprint"
            ? [
                {
                  topic: "",
                  outcome: "",
                  count: 1,
                  marks: "5",
                  question_type: "short",
                  difficulty: "standard",
                },
              ]
            : [],
        questions: ["paper", "question_bank"].includes(kind)
          ? [question()]
          : [],
      },
  );
  const [sourceIds, setSourceIds] = useState<string[]>(
    () =>
      old?.sources.map((s) => String(s.id)) ??
      (seed ? [...seed.sources.map((s) => String(s.id)), seed.id] : []),
  );
  const [ai, setAi] = useState(false),
    [model, setModel] = useState(""),
    [guidance, setGuidance] = useState("");
  const processing = useQuery({
    queryKey: ["processing-status"],
    queryFn: () => api<S["ProcessingStatus"]>("/v1/processing/status"),
    enabled: ai,
  });
  const sourceDocs = documents.filter(
    (d) => d.approved && d.latest && d.id !== old?.id,
  );
  const update = <K extends keyof Content>(key: K, value: Content[K]) =>
    setContent((c) => ({ ...c, [key]: value }));
  const mutation = useMutation({
    mutationFn: () =>
      ai
        ? api(`/v1/classrooms/${classroom.id}/planning-jobs`, {
            method: "POST",
            body: JSON.stringify({
              kind,
              title,
              source_ids: sourceIds,
              original: content.original,
              language: content.language,
              guidance,
              model,
              total_marks: content.total_marks,
            }),
          })
        : api(
            old
              ? `/v1/planning/${old.id}/versions`
              : `/v1/classrooms/${classroom.id}/planning`,
            {
              method: "POST",
              body: JSON.stringify({
                kind,
                title,
                content,
                source_ids: sourceIds,
                ...(old ? { base_version: old.version } : {}),
              }),
            },
          ),
    onSuccess: done,
  });
  return (
    <Modal
      title={`${old ? "Edit" : "New"} ${tools.find((t) => t.kind === kind)?.title.toLowerCase() ?? kind}`}
      close={close}
    >
      <form
        className="planning-form"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <label>
          Title
          <input
            required
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Give this draft a name"
          />
        </label>
        {!["syllabus", "report_template", "marks_template"].includes(kind) && (
          <details
            className="source-picker"
            open={["paper", "question_bank", "blueprint"].includes(kind)}
          >
            <summary>
              Approved sources <span className="count">{sourceIds.length}</span>
              <InfoTip label="Choosing sources">
                Select a syllabus first. Add a blueprint for mark allocation, a
                bank to reuse questions, or an approved paper for a variant.
                Quotes use source labels in selection order. Shorter selections
                work better with local models.
              </InfoTip>
            </summary>
            {!sourceDocs.length ? (
              <p className="muted small">
                Create and approve a syllabus to begin.
              </p>
            ) : (
              sourceDocs.map((d) => (
                <label key={d.id} className="source-option">
                  <input
                    type="checkbox"
                    checked={sourceIds.includes(d.id)}
                    onChange={(e) =>
                      setSourceIds((v) =>
                        e.target.checked
                          ? [...v, d.id]
                          : v.filter((id) => id !== d.id),
                      )
                    }
                  />
                  <span>
                    {d.title}
                    <small>
                      {d.kind.replaceAll("_", " ")} · v{d.version}
                      {sourceIds.includes(d.id)
                        ? ` · S${sourceIds.indexOf(d.id) + 1}`
                        : ""}
                    </small>
                  </span>
                </label>
              ))
            )}
          </details>
        )}
        {["paper", "question_bank", "meeting", "announcement"].includes(kind) &&
          !old && (
            <label className="ai-switch">
              <input
                type="checkbox"
                checked={ai}
                onChange={(e) => setAi(e.target.checked)}
              />
              <Sparkles size={17} />
              Draft with local AI{" "}
              <InfoTip label="About local drafts">
                Ollama runs locally. Outputs still need your review. One active
                job and 20 attempts per classroom per day. No automatic
                publication.
              </InfoTip>
            </label>
          )}
        {["paper", "blueprint"].includes(kind) && (
          <label>
            Total marks
            <input
              type="number"
              required
              min="0.01"
              max="1000"
              step="0.01"
              value={content.total_marks ?? ""}
              onChange={(e) => update("total_marks", e.target.value)}
            />
          </label>
        )}
        {["meeting", "announcement"].includes(kind) && (
          <>
            <label>
              {kind === "meeting" ? "Original notes" : "Original announcement"}
              <textarea
                required
                rows={5}
                maxLength={10000}
                value={content.original ?? ""}
                onChange={(e) => update("original", e.target.value)}
              />
            </label>
            {kind === "announcement" && (
              <label>
                Target language
                <input
                  required
                  value={content.language ?? "English"}
                  onChange={(e) => update("language", e.target.value)}
                />
              </label>
            )}
          </>
        )}
        {ai ? (
          <>
            <label>
              Local model
              <select
                required
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                <option value="">Choose installed model</option>
                {processing.data?.models.map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </label>
            <Notice error={processing.error} />
            <label>
              Direction <span className="muted small">optional</span>
              <textarea
                maxLength={1500}
                rows={2}
                value={guidance}
                onChange={(e) => setGuidance(e.target.value)}
                placeholder="What should this draft focus on?"
              />
            </label>
          </>
        ) : (
          <>
            {kind === "syllabus" && (
              <fieldset>
                <legend>
                  Topics{" "}
                  <InfoTip label="Syllabus help">
                    Paste approved syllabus text under each named topic.
                    Question drafts must quote this text. Source documents are
                    data; embedded instructions cannot authorize actions.
                  </InfoTip>
                </legend>
                {content.topics?.map((t, i) => (
                  <div className="editor-row" key={i}>
                    <label>
                      Topic {i + 1}
                      <input
                        required
                        value={t.name}
                        onChange={(e) =>
                          update(
                            "topics",
                            content.topics!.map((v, j) =>
                              j === i ? { ...v, name: e.target.value } : v,
                            ),
                          )
                        }
                      />
                    </label>
                    <label>
                      Coverage
                      <textarea
                        required
                        minLength={10}
                        rows={3}
                        value={t.text}
                        onChange={(e) =>
                          update(
                            "topics",
                            content.topics!.map((v, j) =>
                              j === i ? { ...v, text: e.target.value } : v,
                            ),
                          )
                        }
                      />
                    </label>
                    <button
                      type="button"
                      className="text-button"
                      onClick={() =>
                        update(
                          "topics",
                          content.topics!.filter((_, j) => j !== i),
                        )
                      }
                    >
                      <Trash2 size={14} />
                      Remove topic
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="button"
                  onClick={() =>
                    update("topics", [...(content.topics ?? []), topic()])
                  }
                >
                  <Plus size={15} />
                  Add topic
                </button>
              </fieldset>
            )}
            {kind === "blueprint" && (
              <fieldset>
                <legend>Paper balance</legend>
                {content.allocations?.map((a, i) => (
                  <div className="editor-row" key={i}>
                    <div className="form-grid">
                      <label>
                        Topic
                        <input
                          required
                          value={a.topic}
                          onChange={(e) =>
                            update(
                              "allocations",
                              content.allocations!.map((v, j) =>
                                j === i ? { ...v, topic: e.target.value } : v,
                              ),
                            )
                          }
                        />
                      </label>
                      <label>
                        Outcome
                        <input
                          required
                          value={a.outcome}
                          onChange={(e) =>
                            update(
                              "allocations",
                              content.allocations!.map((v, j) =>
                                j === i ? { ...v, outcome: e.target.value } : v,
                              ),
                            )
                          }
                        />
                      </label>
                      <label>
                        Questions
                        <input
                          required
                          type="number"
                          min={1}
                          max={40}
                          value={a.count}
                          onChange={(e) =>
                            update(
                              "allocations",
                              content.allocations!.map((v, j) =>
                                j === i
                                  ? { ...v, count: Number(e.target.value) }
                                  : v,
                              ),
                            )
                          }
                        />
                      </label>
                      <label>
                        Marks each
                        <input
                          required
                          type="number"
                          min="0.01"
                          step="0.01"
                          max="100"
                          value={a.marks}
                          onChange={(e) =>
                            update(
                              "allocations",
                              content.allocations!.map((v, j) =>
                                j === i ? { ...v, marks: e.target.value } : v,
                              ),
                            )
                          }
                        />
                      </label>
                      <label>
                        Type
                        <select
                          value={a.question_type}
                          onChange={(e) =>
                            update(
                              "allocations",
                              content.allocations!.map((v, j) =>
                                j === i
                                  ? {
                                      ...v,
                                      question_type: e.target
                                        .value as typeof a.question_type,
                                    }
                                  : v,
                              ),
                            )
                          }
                        >
                          {["short", "descriptive", "numerical", "mcq"].map(
                            (v) => (
                              <option key={v}>{v}</option>
                            ),
                          )}
                        </select>
                      </label>
                      <label>
                        Difficulty
                        <select
                          value={a.difficulty}
                          onChange={(e) =>
                            update(
                              "allocations",
                              content.allocations!.map((v, j) =>
                                j === i
                                  ? {
                                      ...v,
                                      difficulty: e.target
                                        .value as typeof a.difficulty,
                                    }
                                  : v,
                              ),
                            )
                          }
                        >
                          {["foundation", "standard", "stretch"].map((v) => (
                            <option key={v}>{v}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <button
                      type="button"
                      className="text-button"
                      onClick={() =>
                        update(
                          "allocations",
                          content.allocations!.filter((_, j) => j !== i),
                        )
                      }
                    >
                      Remove allocation
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="button"
                  onClick={() =>
                    update("allocations", [
                      ...(content.allocations ?? []),
                      {
                        topic: "",
                        outcome: "",
                        count: 1,
                        marks: "5",
                        question_type: "short",
                        difficulty: "standard",
                      },
                    ])
                  }
                >
                  <Plus size={15} />
                  Add allocation
                </button>
              </fieldset>
            )}
            {["paper", "question_bank"].includes(kind) && (
              <fieldset>
                <legend>
                  Questions{" "}
                  <InfoTip label="Question checks">
                    Use an exact syllabus topic and quote. Checks catch totals,
                    repeated wording and coverage. Review ambiguity, factual
                    accuracy and difficulty yourself. Variant equivalence has
                    not been measured.
                  </InfoTip>
                </legend>
                {content.questions?.map((q, i) => (
                  <QuestionEditor
                    key={i}
                    value={q}
                    index={i}
                    sourceDocs={sourceIds
                      .map((id) => documents.find((d) => d.id === id))
                      .filter((d): d is Doc => !!d)}
                    change={(value) =>
                      update(
                        "questions",
                        content.questions!.map((v, j) => (j === i ? value : v)),
                      )
                    }
                    remove={() =>
                      update(
                        "questions",
                        content.questions!.filter((_, j) => j !== i),
                      )
                    }
                  />
                ))}
                <button
                  type="button"
                  className="button"
                  onClick={() =>
                    update("questions", [
                      ...(content.questions ?? []),
                      question(),
                    ])
                  }
                >
                  <Plus size={15} />
                  Add question
                </button>
              </fieldset>
            )}
            {["meeting", "announcement"].includes(kind) && (
              <label>
                {kind === "meeting" ? "Decisions & summary" : "Translation"}
                <textarea
                  required
                  rows={5}
                  value={content.text ?? ""}
                  onChange={(e) => update("text", e.target.value)}
                />
              </label>
            )}
            {kind === "meeting" && (
              <fieldset>
                <legend>Actions</legend>
                {content.actions?.map((a, i) => (
                  <div className="editor-row" key={i}>
                    {(["action", "owner", "deadline"] as const).map((k) => (
                      <label key={k}>
                        {k}
                        <input
                          required
                          value={a[k]}
                          onChange={(e) =>
                            update(
                              "actions",
                              content.actions!.map((v, j) =>
                                j === i ? { ...v, [k]: e.target.value } : v,
                              ),
                            )
                          }
                        />
                      </label>
                    ))}
                  </div>
                ))}
                <button
                  type="button"
                  className="button"
                  onClick={() =>
                    update("actions", [
                      ...(content.actions ?? []),
                      {
                        action: "",
                        owner: "Unassigned",
                        deadline: "Not specified",
                      },
                    ])
                  }
                >
                  <Plus size={15} />
                  Add action
                </button>
              </fieldset>
            )}
            {kind === "marks_template" && (
              <MarksTemplateFields
                content={content}
                change={(patch) => setContent((c) => ({ ...c, ...patch }))}
              />
            )}
            {kind === "report_template" && (
              <fieldset>
                <legend>
                  Report columns{" "}
                  <InfoTip label="About reports">
                    Builds a dated snapshot from recorded activity and current
                    approved decisions. No student names or invented teaching
                    activity. Approve this template first, then build a report.
                  </InfoTip>
                </legend>
                {columns.map((col) => (
                  <label className="source-option" key={col}>
                    <input
                      type="checkbox"
                      checked={content.columns?.includes(col) ?? false}
                      onChange={(e) =>
                        update(
                          "columns",
                          e.target.checked
                            ? [...(content.columns ?? []), col]
                            : (content.columns ?? []).filter((v) => v !== col),
                        )
                      }
                    />
                    {col.replaceAll("_", " ")}
                  </label>
                ))}
              </fieldset>
            )}
          </>
        )}
        <Notice error={mutation.error} />
        <div className="dialog-actions">
          <button type="button" className="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={mutation.isPending}>
            {mutation.isPending
              ? "Saving…"
              : ai
                ? "Create local draft"
                : old
                  ? "Save new version"
                  : "Save draft"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function QuestionEditor({
  value: q,
  index,
  sourceDocs,
  change,
  remove,
}: {
  value: NonNullable<Content["questions"]>[number];
  index: number;
  sourceDocs: Doc[];
  change: (v: NonNullable<Content["questions"]>[number]) => void;
  remove: () => void;
}) {
  const ref = q.references?.[0] ?? { source_id: "", quote: "" };
  return (
    <div className="editor-row">
      <h3>Question {index + 1}</h3>
      <div className="form-grid">
        <label>
          Topic
          <input
            required
            value={q.topic}
            onChange={(e) => change({ ...q, topic: e.target.value })}
          />
        </label>
        <label>
          Marks
          <input
            required
            type="number"
            min="0.01"
            max={100}
            step="0.01"
            value={q.marks}
            onChange={(e) => change({ ...q, marks: e.target.value })}
          />
        </label>
      </div>
      <label>
        Question
        <textarea
          required
          minLength={8}
          rows={2}
          value={q.text}
          onChange={(e) => change({ ...q, text: e.target.value })}
        />
      </label>
      <label>
        Teacher answer
        <textarea
          required
          rows={2}
          value={q.solution}
          onChange={(e) => change({ ...q, solution: e.target.value })}
        />
      </label>
      <label>
        Marking guide
        <textarea
          required
          rows={2}
          value={q.rubric}
          onChange={(e) => change({ ...q, rubric: e.target.value })}
        />
      </label>
      <div className="form-grid">
        <label>
          Source
          <select
            aria-label="Source"
            required
            value={ref.source_id}
            onChange={(e) =>
              change({
                ...q,
                references: [{ ...ref, source_id: e.target.value }],
              })
            }
          >
            <option value="">Choose syllabus</option>
            {sourceDocs.map(
              (d, i) =>
                d.kind === "syllabus" && (
                  <option key={d.id} value={`S${i + 1}`}>
                    S{i + 1} · {d.title}
                  </option>
                ),
            )}
          </select>
        </label>
        <label>
          Exact quote
          <input
            required
            minLength={4}
            value={ref.quote}
            onChange={(e) =>
              change({ ...q, references: [{ ...ref, quote: e.target.value }] })
            }
          />
        </label>
      </div>
      <button type="button" className="text-button" onClick={remove}>
        <Trash2 size={14} />
        Remove question
      </button>
    </div>
  );
}
