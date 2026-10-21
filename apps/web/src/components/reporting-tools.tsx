"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  Download,
  Link2,
  Plus,
  Trash2,
} from "lucide-react";
import { api, downloadApi } from "../lib/api";
import type { components } from "../lib/api-schema";
import { InfoTip, Modal, Notice } from "./ui";

type S = components["schemas"];
type Content = S["PlanningContent-Input"];
type Doc = S["PlanningOutput"];
type Class = S["ClassroomOutput"];
const fields = [
  "registration_number",
  "name",
  "enrollment",
  "status",
  "total",
  "maximum",
  "percentage",
  "feedback",
] as const;

export function MarksTemplateFields({
  content,
  change,
}: {
  content: Content;
  change: (patch: Partial<Content>) => void;
}) {
  const columns = content.export_columns ?? [];
  function move(index: number, step: number) {
    const next = [...columns];
    [next[index], next[index + step]] = [next[index + step], next[index]];
    change({ export_columns: next });
  }
  return (
    <fieldset>
      <legend>
        Export layout{" "}
        <InfoTip label="About marks templates">
          Name and order the columns your department needs. Registration number
          and result status are required. Choose released results or current
          approved results; missing scores stay blank.
        </InfoTip>
      </legend>
      <label>
        Score basis
        <select
          aria-label="Score basis"
          value={content.score_basis ?? "released"}
          onChange={(e) =>
            change({ score_basis: e.target.value as Content["score_basis"] })
          }
        >
          <option value="released">Released results</option>
          <option value="approved">Current approved results</option>
        </select>
      </label>
      <label className="source-option">
        <input
          type="checkbox"
          checked={content.include_withdrawn ?? false}
          onChange={(e) => change({ include_withdrawn: e.target.checked })}
        />
        Include withdrawn students with blank scores
      </label>
      {columns.map((col, i) => (
        <div className="export-column-row" key={i}>
          <label>
            Column {i + 1}
            <select
              aria-label={`Field for column ${i + 1}`}
              value={col.field}
              onChange={(e) =>
                change({
                  export_columns: columns.map((v, j) =>
                    j === i
                      ? { ...v, field: e.target.value as typeof col.field }
                      : v,
                  ),
                })
              }
            >
              {fields.map((v) => (
                <option key={v} value={v}>
                  {v.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          <label>
            Heading
            <input
              required
              maxLength={80}
              aria-label={`Heading for column ${i + 1}`}
              value={col.heading}
              onChange={(e) =>
                change({
                  export_columns: columns.map((v, j) =>
                    j === i ? { ...v, heading: e.target.value } : v,
                  ),
                })
              }
            />
          </label>
          <div className="button-group">
            <button
              type="button"
              className="icon-button"
              aria-label={`Move column ${i + 1} up`}
              disabled={i === 0}
              onClick={() => move(i, -1)}
            >
              <ArrowUp size={15} />
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Move column ${i + 1} down`}
              disabled={i === columns.length - 1}
              onClick={() => move(i, 1)}
            >
              <ArrowDown size={15} />
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Remove column ${i + 1}`}
              onClick={() =>
                change({ export_columns: columns.filter((_, j) => i !== j) })
              }
            >
              <Trash2 size={15} />
            </button>
          </div>
        </div>
      ))}
      <button
        type="button"
        className="button"
        disabled={columns.length >= 8}
        onClick={() =>
          change({
            export_columns: [
              ...columns,
              {
                field:
                  fields.find((f) => !columns.some((c) => c.field === f)) ??
                  "name",
                heading: "New column",
              },
            ],
          })
        }
      >
        <Plus size={15} />
        Add column
      </button>
    </fieldset>
  );
}

export function ReportingTools({
  classroom,
  documents,
}: {
  classroom: Class;
  documents: Doc[];
}) {
  const query = useQueryClient();
  const [exam, setExam] = useState(""),
    [template, setTemplate] = useState(""),
    [selected, setSelected] = useState("");
  const assessments = useQuery({
    queryKey: ["assessments", classroom.id],
    queryFn: () =>
      api<S["AssessmentOutput"][]>(
        `/v1/classrooms/${classroom.id}/assessments`,
      ),
  });
  const exports = useQuery({
    queryKey: ["marks-exports", classroom.id],
    queryFn: () =>
      api<S["ExportOutput"][]>(`/v1/classrooms/${classroom.id}/marks-exports`),
  });
  const prepare = useMutation({
    mutationFn: () =>
      api<S["ExportOutput"]>(`/v1/assessments/${exam}/marks-exports`, {
        method: "POST",
        body: JSON.stringify({ template_id: template }),
      }),
    onSuccess: (r) => {
      query.setQueryData<S["ExportOutput"][]>(
        ["marks-exports", classroom.id],
        (v) => [r, ...(v ?? [])],
      );
      setSelected(r.id);
    },
  });
  const download = useMutation({
    mutationFn: ({ id, format }: { id: string; format: string }) =>
      downloadApi(
        `/v1/marks-exports/${id}/download?format=${format}`,
        `marks-snapshot.${format}`,
      ),
  });
  const templates = documents.filter(
    (d) =>
      d.kind === "marks_template" && d.latest && d.approved && !d.issues.length,
  );
  const current = exports.data?.find((e) => e.id === selected);
  return (
    <section className="reporting-panel">
      <div className="section-heading">
        <h3>
          Marks exports{" "}
          <InfoTip label="About export snapshots">
            Approve a marks template, choose an assessment and prepare a
            preview. CSV and Excel downloads use those exact saved values even
            if marks change later. Prepare another snapshot for updated results.
          </InfoTip>
        </h3>
        <Download size={19} />
      </div>
      {classroom.can_edit && !classroom.archived && (
        <div className="export-controls">
          <label>
            Assessment
            <select
              aria-label="Assessment"
              value={exam}
              onChange={(e) => setExam(e.target.value)}
            >
              <option value="">Choose assessment</option>
              {assessments.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Export template
            <select
              aria-label="Export template"
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
            >
              <option value="">Choose approved template</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title} · v{t.version}
                </option>
              ))}
            </select>
          </label>
          <button
            className="button"
            disabled={!exam || !template || prepare.isPending}
            onClick={() => prepare.mutate()}
          >
            Prepare preview
          </button>
        </div>
      )}
      <Notice
        error={
          assessments.error ?? exports.error ?? prepare.error ?? download.error
        }
      />
      <details className="quiet-disclosure">
        <summary>
          Saved previews{" "}
          <span className="count">{exports.data?.length ?? 0}</span>
        </summary>
        {exports.data?.map((e) => (
          <button
            key={e.id}
            className="saved-export-row"
            onClick={() => setSelected(e.id)}
          >
            <span>
              {e.snapshot.assessment_title}
              <small>
                {e.snapshot.template_title} · v{e.snapshot.template_version} ·{" "}
                {new Date(e.created_at).toLocaleString()}
              </small>
            </span>
            <span>{e.snapshot.rows.length} students</span>
          </button>
        ))}
      </details>
      {current && (
        <Modal title="Review marks export" close={() => setSelected("")}>
          <p>
            {current.snapshot.assessment_title}{" "}
            <span className="role-tag">{current.snapshot.score_basis}</span>
          </p>
          <p className="quiet">
            {current.snapshot.template_title} · v
            {current.snapshot.template_version} ·{" "}
            {new Date(current.created_at).toLocaleString()}
          </p>
          <div className="table-scroll export-preview">
            <table>
              <thead>
                <tr>
                  {current.snapshot.columns.map((c) => (
                    <th key={c.field}>{c.heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {current.snapshot.rows.map((r, i) => (
                  <tr key={i}>
                    {current.snapshot.columns.map((c) => (
                      <td key={c.field}>{r[c.field] ?? "—"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Notice error={download.error} />
          <p className="quiet">
            Blank scores are not zero. “Released previous” preserves a result
            awaiting replacement.
          </p>
          <div className="dialog-actions">
            <button
              className="button"
              disabled={download.isPending}
              onClick={() => download.mutate({ id: current.id, format: "csv" })}
            >
              Download CSV
            </button>
            <button
              className="button primary"
              disabled={download.isPending}
              onClick={() =>
                download.mutate({ id: current.id, format: "xlsx" })
              }
            >
              Download Excel
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}

export function BankPerformance({
  document: doc,
  classroom,
}: {
  document: Doc;
  classroom: Class;
}) {
  const query = useQueryClient();
  const [index, setIndex] = useState("0"),
    [examId, setExamId] = useState(""),
    [questionId, setQuestionId] = useState(""),
    [reason, setReason] = useState("");
  const data = useQuery({
    queryKey: ["question-performance", doc.id],
    queryFn: () =>
      api<S["PerformanceOutput"]>(
        `/v1/planning/${doc.id}/question-performance`,
      ),
  });
  const exams = useQuery({
    queryKey: ["assessments", classroom.id],
    queryFn: () =>
      api<S["AssessmentOutput"][]>(
        `/v1/classrooms/${classroom.id}/assessments`,
      ),
  });
  const exam = exams.data?.find((e) => e.id === examId);
  const link = useMutation({
    mutationFn: (body: S["LinkInput"]) =>
      api<S["PerformanceOutput"]>(`/v1/planning/${doc.id}/question-links`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (r) => {
      query.setQueryData(["question-performance", doc.id], r);
      setReason("");
    },
  });
  const editable = classroom.can_edit && !classroom.archived;
  return (
    <section className="bank-performance">
      <h3>
        Question history{" "}
        <InfoTip label="About linked performance">
          Link a bank question to a graded rubric question yourself. Figures use
          current approved, reviewed answers only. Stale or revoked links
          contribute no statistics. Different maxima are shown separately; a
          link does not establish question equivalence.
        </InfoTip>
      </h3>
      <Notice error={data.error ?? exams.error ?? link.error} />
      {data.data?.links.map((r) => (
        <div className="performance-row" key={r.id}>
          <div>
            <strong>
              Question {r.question_index + 1} · {r.assessment_title}
            </strong>
            <small>
              {r.stale
                ? "Source version changed — link needs review"
                : `${r.reviewed} reviewed · average ${r.average ?? "—"} / ${r.maximum ?? "—"}`}
            </small>
            {!r.stale && r.reviewed > 0 && (
              <small>
                {r.full_credit} full · {r.partial_credit} partial ·{" "}
                {r.zero_credit} zero
              </small>
            )}
          </div>
          {editable && (
            <button
              className="text-button"
              disabled={reason.trim().length < 3 || link.isPending}
              onClick={() =>
                link.mutate({
                  question_index: r.question_index,
                  assessment_id: r.assessment_id,
                  rubric_id: r.rubric_id,
                  question_id: r.question_id,
                  base_link_id: r.id,
                  disposition: "revoked",
                  reason,
                })
              }
            >
              Remove link
            </button>
          )}
        </div>
      ))}
      {editable && (
        <details className="quiet-disclosure">
          <summary>
            <Link2 size={14} /> Review a question link
          </summary>
          <div className="link-controls">
            <label>
              Bank question
              <select
                aria-label="Bank question"
                value={index}
                onChange={(e) => setIndex(e.target.value)}
              >
                {doc.content.questions?.map((q, i) => (
                  <option key={i} value={String(i)}>
                    Question {i + 1} · {q.topic}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Linked assessment
              <select
                aria-label="Linked assessment"
                value={examId}
                onChange={(e) => {
                  setExamId(e.target.value);
                  setQuestionId("");
                }}
              >
                <option value="">Choose assessment</option>
                {exams.data
                  ?.filter((a) => a.status === "active" && a.rubric)
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.title}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Graded question
              <select
                aria-label="Graded question"
                value={questionId}
                onChange={(e) => setQuestionId(e.target.value)}
              >
                <option value="">Choose rubric question</option>
                {exam?.rubric?.questions.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.label} · {q.prompt}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Review note
              <input
                required
                minLength={3}
                maxLength={1000}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Why does this link apply?"
              />
            </label>
            <button
              className="button"
              disabled={
                !doc.latest ||
                !doc.approved ||
                !!doc.issues.length ||
                !exam?.rubric ||
                !questionId ||
                reason.trim().length < 3 ||
                link.isPending
              }
              onClick={() => {
                const previous = data.data?.history.find(
                  (r) =>
                    r.question_index === Number(index) &&
                    r.assessment_id === examId &&
                    r.rubric_id === exam!.rubric!.id &&
                    r.question_id === questionId,
                );
                link.mutate({
                  question_index: Number(index),
                  assessment_id: examId,
                  rubric_id: exam!.rubric!.id,
                  question_id: questionId,
                  base_link_id: previous?.id ?? null,
                  disposition: "linked",
                  reason,
                });
              }}
            >
              Save reviewed link
            </button>
          </div>
        </details>
      )}
      {!!data.data?.history.length && (
        <details>
          <summary>Link history · {data.data.history.length}</summary>
          {data.data.history.map((r) => (
            <p className="quiet" key={r.id}>
              Question {r.question_index + 1} · {r.assessment_title} ·{" "}
              {r.disposition}
              <br />
              {r.reason}
            </p>
          ))}
        </details>
      )}
      {!!data.data?.reused_by.length && (
        <details>
          <summary>Document reuse · {data.data.reused_by.length}</summary>
          {data.data.reused_by.map((d) => (
            <p className="quiet" key={d.id}>
              {d.title} · v{d.version} · {d.approved ? "approved" : "draft"}
            </p>
          ))}
        </details>
      )}
    </section>
  );
}
