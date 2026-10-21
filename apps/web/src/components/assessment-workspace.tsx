"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ClipboardCheck,
  FileText,
  Plus,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { api, downloadApi } from "../lib/api";
import { refreshAssessment, refreshPaper } from "../lib/review-cache";
import type { components } from "../lib/api-schema";
import { InfoTip, Modal, Notice } from "./ui";
import { RequestQuestionReview, ReviewRequests } from "./classroom-overview";
import {
  ReviewDesk,
  PaperReviewTools,
  QuestionDraft,
  FeedbackCards,
} from "./review-tools";

type S = components["schemas"];
type Assessment = S["AssessmentOutput"];
type Question = S["QuestionOutput"];
type Submission = S["SubmissionOutput"];
type Student = S["StudentOutput"];
type Classroom = S["ClassroomOutput"];
const Viewer = dynamic(() => import("./document-viewer"), {
  ssr: false,
  loading: () => <p>Opening paper viewer…</p>,
});
const markText = (value: string | number) =>
  Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });

function blankQuestion(index: number): Question {
  return {
    id: crypto.randomUUID(),
    label: `Q${index}`,
    prompt: "",
    model_answer: "",
    maximum: "10",
    criteria: [
      {
        id: crypto.randomUUID(),
        label: "Key concepts",
        guidance: "",
        maximum: "5",
      },
      {
        id: crypto.randomUUID(),
        label: "Explanation and supporting example",
        guidance: "",
        maximum: "5",
      },
    ],
  };
}

export function AssessmentWorkspace({
  classroom,
  students,
}: {
  classroom: Classroom;
  students: Student[];
}) {
  const [selectedId, setSelectedId] = useState("");
  const [creating, setCreating] = useState(false);
  const [paperId, setPaperId] = useState("");
  const query = useQuery({
    queryKey: ["assessments", classroom.id],
    queryFn: () =>
      api<Assessment[]>(`/v1/classrooms/${classroom.id}/assessments`),
  });
  const selected = query.data?.find((item) => item.id === selectedId);
  if (selected)
    return (
      <AssessmentDetail
        key={selected.id}
        classroom={classroom}
        students={students}
        assessment={selected}
        paperId={paperId}
        setPaperId={setPaperId}
        back={() => {
          setSelectedId("");
          setPaperId("");
        }}
      />
    );
  return (
    <div className="tab-content">
      <div className="section-heading">
        <div>
          <span className="eyebrow">FROM PAPER TO PROGRESS</span>
          <h3>
            Assessments{" "}
            <InfoTip label="About assessments">
              Create a rubric, review each paper, then approve marks. Students
              see results only after you release them.
            </InfoTip>
          </h3>
        </div>
        {classroom.can_edit && !classroom.archived && (
          <button className="button primary" onClick={() => setCreating(true)}>
            <Plus size={16} />
            New assessment
          </button>
        )}
      </div>
      <Notice error={query.error} />
      {query.isPending ? (
        <p role="status">Loading assessments…</p>
      ) : query.data?.length ? (
        <div className="assessment-list">
          {query.data.map((item) => (
            <button
              className="assessment-row"
              key={item.id}
              onClick={() => setSelectedId(item.id)}
            >
              <span className="assessment-icon">
                <ClipboardCheck size={23} />
              </span>
              <div>
                <strong>{item.title}</strong>
                <span>
                  {item.rubric
                    ? `${markText(item.rubric.maximum)} marks · ${item.rubric.questions.length} questions`
                    : "Rubric not yet added"}{" "}
                  · {item.submission_count} papers
                </span>
              </div>
              <span className={`status ${item.status}`}>{item.status}</span>
              <ArrowRight size={17} />
            </button>
          ))}
        </div>
      ) : (
        <div className="assessment-empty">
          <span className="illustration">
            <ClipboardCheck size={32} />
          </span>
          <h2>Good assessment starts with clarity.</h2>
          <p>Start with an assessment and a rubric.</p>
          {classroom.can_edit && !classroom.archived && (
            <button className="button" onClick={() => setCreating(true)}>
              <Plus size={16} />
              Create an assessment
            </button>
          )}
        </div>
      )}
      {creating && (
        <CreateAssessment
          classroomId={classroom.id}
          close={() => setCreating(false)}
          created={(id) => {
            setCreating(false);
            setSelectedId(id);
          }}
        />
      )}
    </div>
  );
}

function CreateAssessment({
  classroomId,
  close,
  created,
}: {
  classroomId: string;
  close: () => void;
  created: (id: string) => void;
}) {
  const query = useQueryClient();
  const action = useMutation({
    mutationFn: (body: Record<string, FormDataEntryValue>) =>
      api<Assessment>(`/v1/classrooms/${classroomId}/assessments`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (result) => {
      query.invalidateQueries({ queryKey: ["assessments", classroomId] });
      created(result.id);
    },
  });
  return (
    <Modal title="Start with an assessment." close={close}>
      <p className="muted">
        You’ll add the questions and marking criteria next.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          action.mutate(Object.fromEntries(new FormData(event.currentTarget)));
        }}
      >
        <label>
          Assessment title
          <input
            name="title"
            required
            maxLength={140}
            placeholder="e.g. CAT 1 · Data Structures"
          />
        </label>
        <label>
          Teacher notes
          <textarea
            name="instructions"
            rows={3}
            maxLength={4000}
            placeholder="Context or instructions for this assessment"
          />
        </label>
        <Notice error={action.error} />
        <footer>
          <button className="button" type="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={action.isPending}>
            Create assessment
            <ArrowRight size={16} />
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function AssessmentDetail({
  classroom,
  students,
  assessment: initial,
  paperId,
  setPaperId,
  back,
}: {
  classroom: Classroom;
  students: Student[];
  assessment: Assessment;
  paperId: string;
  setPaperId: (id: string) => void;
  back: () => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [editing, setEditing] = useState(false);
  const query = useQueryClient();
  const assessment = useQuery({
    queryKey: ["assessment", initial.id],
    queryFn: () => api<Assessment>(`/v1/assessments/${initial.id}`),
    initialData: initial,
  });
  const papers = useQuery({
    queryKey: ["submissions", initial.id],
    queryFn: () =>
      api<Submission[]>(`/v1/assessments/${initial.id}/submissions`),
    refetchInterval: (q) =>
      q.state.data?.some((paper) =>
        paper.jobs.some((job) => ["queued", "running"].includes(job.status)),
      )
        ? 2500
        : false,
  });
  const item = assessment.data;
  const canEdit = classroom.can_edit && !classroom.archived;
  const activate = useMutation({
    mutationFn: () =>
      api(`/v1/assessments/${item.id}/activate`, { method: "POST" }),
    onSuccess: () => {
      refreshAssessment(query, item.id);
    },
  });
  const exported = useMutation({
    mutationFn: (format: string) =>
      downloadApi(
        `/v1/assessments/${item.id}/export?format=${format}`,
        `marks.${format}`,
      ),
  });
  const paper = papers.data?.find((entry) => entry.id === paperId);
  if (paper && item.rubric)
    return (
      <ReviewPaper
        key={paper.id}
        classroom={classroom}
        assessment={item}
        paper={paper}
        back={() => setPaperId("")}
      />
    );
  return (
    <div className="tab-content assessment-detail">
      <button className="text-button back-button" onClick={back}>
        <ArrowLeft size={15} />
        All assessments
      </button>
      <div className="assessment-heading">
        <div>
          <span className="eyebrow">ASSESSMENT WORKSPACE</span>
          <h2>{item.title}</h2>
          <p className="muted">
            {item.instructions ||
              "Build a traceable path from each answer to its approved result."}
          </p>
        </div>
        <span className={`status ${item.status}`}>
          {item.status === "draft" ? "Draft assessment" : "Ready for papers"}
        </span>
      </div>
      <div className="assessment-stats">
        <div>
          <span>Total marks</span>
          <strong>{item.rubric ? markText(item.rubric.maximum) : "—"}</strong>
        </div>
        <div>
          <span>Questions</span>
          <strong>{item.rubric?.questions.length ?? "—"}</strong>
        </div>
        <div>
          <span>Papers uploaded</span>
          <strong>
            {papers.data?.length ?? 0}
            <small>
              {" "}
              /{" "}
              {
                students.filter((student) => student.status === "active").length
              }{" "}
              students
            </small>
          </strong>
        </div>
        <div>
          <span>Results released</span>
          <strong>
            {papers.data?.filter((entry) => entry.status === "released")
              .length ?? 0}
          </strong>
        </div>
      </div>
      <Notice
        error={
          assessment.error ?? papers.error ?? activate.error ?? exported.error
        }
      />
      <section className="rubric-summary">
        <div>
          <span className="rubric-icon">
            <ShieldCheck size={23} />
          </span>
          <div>
            <strong>
              {item.rubric
                ? `Rubric · version ${item.rubric.version}`
                : "Define your marking rubric"}
            </strong>
            <p>
              {item.status === "active"
                ? "Approved. Existing papers keep their pinned rubric until re-evaluation."
                : "All questions are required. Criterion marks determine each question’s maximum."}
            </p>
          </div>
        </div>
        <div className="inline-actions">
          {canEdit && item.status === "draft" && (
            <>
              <button className="button" onClick={() => setEditing(true)}>
                {item.rubric ? "Edit rubric" : "Build rubric"}
              </button>
              {item.rubric && (
                <button
                  className="button primary"
                  disabled={activate.isPending}
                  onClick={() => activate.mutate()}
                >
                  Approve rubric & activate
                </button>
              )}
            </>
          )}
          {item.status === "active" && canEdit && (
            <button className="button" onClick={() => setEditing(true)}>
              {item.draft_rubric ? "Edit draft revision" : "Revise rubric"}
            </button>
          )}
          {item.status === "active" && (
            <details>
              <summary>View rubric</summary>
              <div className="rubric-readonly">
                {item.rubric?.questions.map((question) => (
                  <div key={question.id}>
                    <strong>
                      {question.label} · {question.maximum} marks
                    </strong>
                    <p>{question.prompt}</p>
                    <ul>
                      {question.criteria.map((criterion) => (
                        <li key={criterion.id}>
                          {criterion.label} · {criterion.maximum}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </section>
      <div className="section-heading">
        <div>
          <h3>Answer papers</h3>
          <p className="small muted">
            Match each file to a student, then review extraction and marks.
          </p>
        </div>
        <div className="inline-actions">
          {item.status === "active" && canEdit && (
            <button
              className="button primary"
              onClick={() => setUploading(true)}
            >
              <Upload size={16} />
              Upload papers
            </button>
          )}
          {papers.data?.length ? (
            <details className="export-menu">
              <summary className="button">Export marks</summary>
              <button
                className="text-button"
                disabled={exported.isPending}
                onClick={() => exported.mutate("csv")}
              >
                Download CSV
              </button>
              <button
                className="text-button"
                disabled={exported.isPending}
                onClick={() => exported.mutate("xlsx")}
              >
                Download Excel
              </button>
            </details>
          ) : null}
        </div>
      </div>
      <ReviewDesk
        assessment={item}
        papers={papers.data ?? []}
        canEdit={canEdit}
        openPaper={setPaperId}
        editRubric={() => setEditing(true)}
      />
      {editing && (
        <RubricEditor assessment={item} close={() => setEditing(false)} />
      )}
      {uploading && (
        <UploadPapers
          assessment={item}
          classroomId={classroom.id}
          students={students.filter(
            (student) =>
              student.status === "active" &&
              !papers.data?.some((entry) => entry.student_id === student.id),
          )}
          close={() => setUploading(false)}
        />
      )}
    </div>
  );
}

function RubricEditor({
  assessment,
  close,
}: {
  assessment: Assessment;
  close: () => void;
}) {
  const [questions, setQuestions] = useState<Question[]>(() =>
    structuredClone(
      (assessment.draft_rubric ?? assessment.rubric)?.questions ?? [
        blankQuestion(1),
      ],
    ),
  );
  const [reason, setReason] = useState(assessment.draft_rubric?.reason ?? "");
  const baseVersion =
    (assessment.draft_rubric ?? assessment.rubric)?.version ?? 0;
  const query = useQueryClient();
  const action = useMutation({
    mutationFn: () =>
      api<S["RubricOutput"]>(`/v1/assessments/${assessment.id}/rubrics`, {
        method: "POST",
        body: JSON.stringify({
          base_version: baseVersion,
          reason,
          questions: questions.map((question) => ({
            ...question,
            accepted_alternatives:
              question.accepted_alternatives
                ?.map((a) => a.trim())
                .filter(Boolean) ?? [],
            maximum: question.criteria
              .reduce((sum, criterion) => sum + Number(criterion.maximum), 0)
              .toFixed(2),
          })),
        }),
      }),
    onSuccess: (created) => {
      query.setQueryData<S["RubricOutput"][]>(
        ["rubric-versions", assessment.id],
        (previous) => [
          created,
          ...(previous ?? []).filter((r) => r.id !== created.id),
        ],
      );
      refreshAssessment(query, assessment.id);
      close();
    },
  });
  function update(index: number, changed: Partial<Question>) {
    setQuestions((previous) =>
      previous.map((question, i) =>
        i === index ? { ...question, ...changed } : question,
      ),
    );
  }
  return (
    <Modal title="A clear rubric, criterion by criterion." close={close}>
      <p className="muted">
        Define each question and the evidence that earns credit. Totals are
        validated when saved.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          action.mutate();
        }}
      >
        {assessment.status === "active" && (
          <label>
            Reason for rubric revision
            <textarea
              required
              minLength={3}
              maxLength={2000}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Explain what changed and why"
            />
          </label>
        )}
        <div className="rubric-editor">
          {questions.map((question, index) => (
            <section className="question-editor" key={question.id}>
              <header>
                <strong>Question {index + 1}</strong>
                <span>
                  {markText(
                    question.criteria.reduce(
                      (sum, criterion) => sum + Number(criterion.maximum),
                      0,
                    ),
                  )}{" "}
                  marks
                </span>
                {questions.length > 1 && (
                  <button
                    className="icon-button"
                    type="button"
                    aria-label={`Remove question ${index + 1}`}
                    onClick={() =>
                      setQuestions(questions.filter((_, i) => i !== index))
                    }
                  >
                    <X size={15} />
                  </button>
                )}
              </header>
              <label>
                Question label
                <input
                  required
                  maxLength={30}
                  value={question.label}
                  onChange={(event) =>
                    update(index, { label: event.target.value })
                  }
                />
              </label>
              <label>
                Question text
                <textarea
                  required
                  rows={3}
                  maxLength={6000}
                  value={question.prompt}
                  onChange={(event) =>
                    update(index, { prompt: event.target.value })
                  }
                />
              </label>
              <label>
                Model answer / accepted alternatives
                <textarea
                  rows={3}
                  maxLength={8000}
                  value={question.model_answer}
                  onChange={(event) =>
                    update(index, { model_answer: event.target.value })
                  }
                />
              </label>
              <label>
                Accepted alternatives (one per line)
                <textarea
                  rows={2}
                  value={question.accepted_alternatives?.join("\n") ?? ""}
                  onChange={(event) =>
                    update(index, {
                      accepted_alternatives: event.target.value.split("\n"),
                    })
                  }
                />
              </label>
              <span className="eyebrow">MARKING CRITERIA</span>
              {question.criteria.map((criterion, criterionIndex) => (
                <div className="criterion-input" key={criterion.id}>
                  <label>
                    Criterion {criterionIndex + 1}
                    <input
                      required
                      maxLength={500}
                      value={criterion.label}
                      onChange={(event) =>
                        update(index, {
                          criteria: question.criteria.map((entry, i) =>
                            i === criterionIndex
                              ? { ...entry, label: event.target.value }
                              : entry,
                          ),
                        })
                      }
                    />
                  </label>
                  <label>
                    Marks
                    <input
                      type="number"
                      required
                      min={0}
                      max={10000}
                      step="0.01"
                      value={criterion.maximum}
                      onChange={(event) =>
                        update(index, {
                          criteria: question.criteria.map((entry, i) =>
                            i === criterionIndex
                              ? { ...entry, maximum: event.target.value }
                              : entry,
                          ),
                        })
                      }
                    />
                  </label>
                  <label className="criterion-guidance">
                    Criterion guidance
                    <textarea
                      rows={2}
                      maxLength={2000}
                      value={criterion.guidance ?? ""}
                      onChange={(event) =>
                        update(index, {
                          criteria: question.criteria.map((entry, i) =>
                            i === criterionIndex
                              ? { ...entry, guidance: event.target.value }
                              : entry,
                          ),
                        })
                      }
                      placeholder="Evidence, partial credit, or common mistakes"
                    />
                  </label>
                  {question.criteria.length > 1 && (
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={`Remove criterion ${criterionIndex + 1}`}
                      onClick={() =>
                        update(index, {
                          criteria: question.criteria.filter(
                            (_, i) => i !== criterionIndex,
                          ),
                        })
                      }
                    >
                      <X size={15} />
                    </button>
                  )}
                </div>
              ))}
              {question.criteria.length < 20 && (
                <button
                  type="button"
                  className="text-button"
                  onClick={() =>
                    update(index, {
                      criteria: [
                        ...question.criteria,
                        {
                          id: crypto.randomUUID(),
                          label: "",
                          guidance: "",
                          maximum: "1",
                        },
                      ],
                    })
                  }
                >
                  <Plus size={14} />
                  Add criterion
                </button>
              )}
            </section>
          ))}
        </div>
        <button
          type="button"
          className="button"
          disabled={questions.length >= 50}
          onClick={() =>
            setQuestions([...questions, blankQuestion(questions.length + 1)])
          }
        >
          <Plus size={15} />
          Add question
        </button>
        <Notice error={action.error} />
        <footer>
          <button type="button" className="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={action.isPending}>
            {action.isPending ? "Saving…" : "Save rubric version"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function UploadPapers({
  assessment,
  classroomId,
  students,
  close,
}: {
  assessment: Assessment;
  classroomId: string;
  students: Student[];
  close: () => void;
}) {
  const [rows, setRows] = useState<
    {
      file: File;
      studentId: string;
      status: string;
      error: string;
      fileId?: string;
    }[]
  >([]);
  const [confirmed, setConfirmed] = useState(false);
  const query = useQueryClient();
  const upload = useMutation({
    mutationFn: async () => {
      for (let index = 0; index < rows.length; index++) {
        const row = rows[index];
        if (row.status === "done") continue;
        setRows((previous) =>
          previous.map((item, i) =>
            i === index ? { ...item, status: "uploading", error: "" } : item,
          ),
        );
        try {
          let fileId = row.fileId;
          if (!fileId) {
            const body = new FormData();
            body.set("file", row.file);
            const file = await api<S["FileOutput"]>(
              `/v1/classrooms/${classroomId}/files`,
              { method: "POST", body },
            );
            fileId = file.id;
            setRows((previous) =>
              previous.map((item, i) =>
                i === index ? { ...item, fileId } : item,
              ),
            );
          }
          await api(`/v1/assessments/${assessment.id}/submissions`, {
            method: "POST",
            body: JSON.stringify({
              file_id: fileId,
              student_id: row.studentId,
              identity_confirmed: true,
            }),
          });
          setRows((previous) =>
            previous.map((item, i) =>
              i === index ? { ...item, status: "done" } : item,
            ),
          );
        } catch (error) {
          setRows((previous) =>
            previous.map((item, i) =>
              i === index
                ? {
                    ...item,
                    status: "failed",
                    error:
                      error instanceof Error ? error.message : "Upload failed",
                  }
                : item,
            ),
          );
        }
      }
      refreshAssessment(query, assessment.id);
      void query.invalidateQueries({ queryKey: ["files", classroomId] });
    },
  });
  const selectedIds = rows.map((row) => row.studentId);
  const valid =
    rows.length > 0 &&
    rows.every((row) => row.studentId) &&
    new Set(selectedIds).size === selectedIds.length &&
    confirmed;
  return (
    <Modal title="Every paper, matched with care." close={close}>
      <p className="muted">
        Choose up to 20 separate papers and confirm the student for each. Names
        are never matched automatically.
      </p>
      <label className="file-picker">
        Answer papers
        <input
          aria-label="Answer papers"
          type="file"
          multiple
          accept=".pdf,.png,.jpeg,.jpg"
          disabled={
            upload.isPending || rows.some((row) => row.status === "done")
          }
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            setRows(
              files.slice(0, 20).map((file) => ({
                file,
                studentId: "",
                status: file.size > 10 * 1024 * 1024 ? "failed" : "ready",
                error: file.size > 10 * 1024 * 1024 ? "File exceeds 10 MB" : "",
              })),
            );
            setConfirmed(false);
          }}
        />
        <span className="small muted">
          PDF: 1–30 pages · images: JPEG/PNG · 10 MB per paper
        </span>
      </label>
      <div className="upload-mapping">
        {rows.map((row, index) => (
          <div key={index}>
            <strong>{row.file.name}</strong>
            <label>
              Student for {row.file.name}
              <select
                required
                value={row.studentId}
                disabled={upload.isPending || row.status === "done"}
                onChange={(event) => {
                  setConfirmed(false);
                  setRows(
                    rows.map((item, i) =>
                      i === index
                        ? { ...item, studentId: event.target.value }
                        : item,
                    ),
                  );
                }}
              >
                <option value="">Choose student</option>
                {students.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.registration_number} · {student.name}
                  </option>
                ))}
              </select>
            </label>
            {row.status === "done" ? (
              <span className="status active">Matched and saved</span>
            ) : (
              <p className={row.error ? "field-error" : "small muted"}>
                {row.error ||
                  (row.status === "uploading"
                    ? "Uploading…"
                    : "Awaiting your confirmation")}
              </p>
            )}
          </div>
        ))}
      </div>
      {rows.length > 0 && (
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={confirmed}
            disabled={upload.isPending}
            onChange={(event) => setConfirmed(event.target.checked)}
          />
          I have checked the student identity for every paper.
        </label>
      )}
      <Notice error={upload.error} />
      <footer>
        <button className="button" disabled={upload.isPending} onClick={close}>
          {rows.length && rows.every((row) => row.status === "done")
            ? "Done"
            : "Close"}
        </button>
        <button
          className="button primary"
          disabled={
            !valid ||
            upload.isPending ||
            rows.every((row) => row.status === "done") ||
            rows.some((row) => row.file.size > 10 * 1024 * 1024)
          }
          onClick={() => upload.mutate()}
        >
          {upload.isPending ? "Saving papers…" : "Confirm matches & upload"}
        </button>
      </footer>
    </Modal>
  );
}

function ReviewPaper({
  classroom,
  assessment,
  paper: initial,
  back,
}: {
  classroom: Classroom;
  assessment: Assessment;
  paper: Submission;
  back: () => void;
}) {
  const [gradingModel, setGradingModel] = useState("");
  const [calibrationIds, setCalibrationIds] = useState<string[]>([]);
  const [anonymous, setAnonymous] = useState(false);
  const [visionModel, setVisionModel] = useState<string | null>(null);
  const query = useQueryClient();
  const detail = useQuery({
    queryKey: ["submission", initial.id],
    queryFn: () => api<Submission>(`/v1/submissions/${initial.id}`),
    initialData: initial,
    refetchInterval: (q) =>
      q.state.data?.jobs.some((job) =>
        ["queued", "running"].includes(job.status),
      )
        ? 2500
        : false,
  });
  const paper = detail.data;
  const status = useQuery({
    queryKey: ["processing-status"],
    queryFn: () => api<S["ProcessingStatus"]>("/v1/processing/status"),
  });
  const calibrations = useQuery({
    queryKey: ["calibrations", assessment.id],
    queryFn: () =>
      api<S["CalibrationOutput"][]>(
        `/v1/assessments/${assessment.id}/calibrations`,
      ),
  });
  const file = useQuery({
    queryKey: ["paper-download", paper.file_id],
    queryFn: () =>
      api<{ url: string }>(
        `/v1/classrooms/${classroom.id}/files/${paper.file_id}/download`,
      ),
    refetchInterval: 45_000,
  });
  const job = useMutation({
    mutationFn: (kind: "extract" | "grade") =>
      api(`/v1/submissions/${paper.id}/jobs`, {
        method: "POST",
        body: JSON.stringify({
          kind,
          calibration_ids: kind === "grade" ? calibrationIds : [],
          model:
            kind === "grade"
              ? gradingModel || status.data?.grading_model || ""
              : (visionModel ?? status.data?.vision_model ?? ""),
        }),
      }),
    onSuccess: () => {
      refreshPaper(query, paper);
    },
  });
  const jobAction = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      api(`/v1/jobs/${id}/${action}`, { method: "POST" }),
    onSuccess: () => {
      refreshPaper(query, paper);
    },
  });
  const editable =
    classroom.can_edit && !classroom.archived && paper.status !== "released";
  const working = paper.jobs.some((item) =>
    ["queued", "running"].includes(item.status),
  );
  return (
    <div className="tab-content review-workspace">
      <button className="text-button back-button" onClick={back}>
        <ArrowLeft size={15} />
        All papers
      </button>
      <div className="assessment-heading">
        <div>
          <span className="eyebrow">{assessment.title}</span>
          <h2>{anonymous ? "Anonymous paper" : paper.student_name}</h2>
          <p className="muted">
            {anonymous
              ? "Identity hidden in this marking view"
              : `${paper.registration_number} · ${paper.filename}`}{" "}
            · {paper.page_count} page{paper.page_count === 1 ? "" : "s"}
          </p>
        </div>
        <span className={`status ${paper.status}`}>
          {paper.status.replaceAll("_", " ")}
        </span>
      </div>
      <label className="checkbox-label anonymous-review">
        <input
          type="checkbox"
          checked={anonymous}
          onChange={(event) => setAnonymous(event.target.checked)}
        />
        Hide student identity while marking
      </label>
      <PaperReviewTools
        paper={paper}
        assessment={assessment}
        canEdit={classroom.can_edit && !classroom.archived}
      />
      <div className="review-steps">
        <span className="complete">
          <Check size={14} />
          Identity confirmed
        </span>
        <span className={paper.extraction?.reviewed_by ? "complete" : ""}>
          1. Review extraction
        </span>
        <span
          className={
            paper.decision?.extraction_id === paper.extraction?.id &&
            ["approved", "released"].includes(paper.status)
              ? "complete"
              : ""
          }
        >
          2. Approve marks
        </span>
        <span className={paper.status === "released" ? "complete" : ""}>
          3. Release result
        </span>
      </div>
      <Notice
        error={detail.error ?? file.error ?? job.error ?? jobAction.error}
      />
      {paper.jobs
        .filter((item) => item.status !== "succeeded")
        .map((item) => (
          <div className="job-notice" key={item.id}>
            <span>
              <strong>
                {item.kind === "extract"
                  ? "Text extraction"
                  : "Grading suggestions"}{" "}
                · {item.status}
              </strong>
              <small>
                {item.error ||
                  (item.status === "queued" || item.status === "running"
                    ? "This work continues if you close the browser."
                    : "No marks have been released.")}
              </small>
            </span>
            {editable && item.status === "failed" && item.attempts < 3 && (
              <button
                className="text-button"
                disabled={jobAction.isPending}
                onClick={() =>
                  jobAction.mutate({ id: item.id, action: "retry" })
                }
              >
                Retry
              </button>
            )}
            {editable && ["queued", "running"].includes(item.status) && (
              <button
                className="text-button"
                onClick={() =>
                  jobAction.mutate({ id: item.id, action: "cancel" })
                }
              >
                Cancel
              </button>
            )}
          </div>
        ))}
      <div className="review-columns">
        <section className="scan-panel">
          <header>
            <span className="eyebrow">ORIGINAL ANSWER SHEET</span>
            <ShieldCheck size={15} />
          </header>
          {file.data ? (
            <Viewer
              url={file.data.url}
              contentType={paper.content_type}
              pageCount={paper.page_count}
            />
          ) : (
            <p>Loading authorized original…</p>
          )}
          {paper.extraction?.pages.length ? (
            <details className="raw-extraction">
              <summary>Extracted page text · {paper.extraction.source}</summary>
              {paper.extraction.pages.map((page) => (
                <div key={page.page}>
                  <strong>Page {page.page}</strong>
                  <pre>{page.text || "No readable text extracted"}</pre>
                </div>
              ))}
            </details>
          ) : null}
        </section>
        <section className="review-editor">
          <div className="section-heading">
            <div>
              <h3>Read first. Then review.</h3>
              <p className="small muted">
                Confirm the text and page mapping for every question.
              </p>
            </div>
          </div>
          {editable && !paper.extraction && (
            <div className="local-processing">
              <label>
                Vision model (for scans)
                <select
                  value={visionModel ?? status.data?.vision_model ?? ""}
                  onChange={(event) => setVisionModel(event.target.value)}
                >
                  <option value="">PDF embedded text only</option>
                  {status.data?.models.map((model) => (
                    <option key={model}>{model}</option>
                  ))}
                </select>
              </label>
              <button
                className="button"
                disabled={working || job.isPending}
                onClick={() => job.mutate("extract")}
              >
                <Sparkles size={15} />
                Extract answer text
              </button>
              <p className="small muted">
                Typed PDFs can be read locally. Scans need a vision model. You
                can also enter the text below.
              </p>
            </div>
          )}
          <ExtractionEditor
            key={`${paper.id}:${paper.extraction?.version ?? 0}`}
            paper={paper}
            questions={paper.rubric.questions}
            editable={editable}
          />
          {paper.extraction?.reviewed_by && (
            <>
              <div className="grading-divider">
                <ShieldCheck size={18} />
                <span>
                  Extraction reviewed · version {paper.extraction.version}
                </span>
              </div>
              {editable && (
                <div className="local-processing">
                  <label>
                    Local grading model
                    <select
                      value={gradingModel || status.data?.grading_model || ""}
                      onChange={(event) => setGradingModel(event.target.value)}
                    >
                      <option value="">Choose a model</option>
                      {status.data?.models.map((model) => (
                        <option key={model}>{model}</option>
                      ))}
                    </select>
                  </label>
                  <details className="calibration-picker">
                    <summary>
                      Teacher reference examples ({calibrationIds.length}{" "}
                      selected)
                    </summary>
                    <p className="small muted">
                      Select up to 10 examples from other papers using this
                      exact rubric. Their answer text and teacher reference
                      marks will accompany this run.
                    </p>
                    <Notice error={calibrations.error} />
                    {calibrations.data
                      ?.filter(
                        (example) =>
                          example.rubric_id === paper.rubric.id &&
                          example.submission_id !== paper.id,
                      )
                      .map((example) => (
                        <label className="checkbox-label" key={example.id}>
                          <input
                            type="checkbox"
                            checked={calibrationIds.includes(example.id)}
                            disabled={
                              !calibrationIds.includes(example.id) &&
                              calibrationIds.length >= 10
                            }
                            onChange={(event) =>
                              setCalibrationIds(
                                event.target.checked
                                  ? [...calibrationIds, example.id]
                                  : calibrationIds.filter(
                                      (id) => id !== example.id,
                                    ),
                              )
                            }
                          />
                          {example.band} · {example.note}
                        </label>
                      ))}
                    {!calibrations.data?.some(
                      (example) =>
                        example.rubric_id === paper.rubric.id &&
                        example.submission_id !== paper.id,
                    ) && (
                      <p className="small muted">
                        Capture a reference from another reviewed paper to use
                        calibration. Grading without examples remains available.
                      </p>
                    )}
                  </details>
                  <button
                    className="button"
                    disabled={
                      working ||
                      job.isPending ||
                      !status.data?.available ||
                      (!!paper.proposal &&
                        paper.proposal.extraction_id === paper.extraction.id &&
                        paper.proposal.model ===
                          (gradingModel || status.data?.grading_model || "") &&
                        [...paper.proposal.calibration_ids].sort().join() ===
                          [...calibrationIds].sort().join())
                    }
                    onClick={() => job.mutate("grade")}
                  >
                    <Sparkles size={15} />
                    Suggest marks locally
                  </button>
                  <p className="small muted">
                    Suggestions are a starting point. Review every criterion
                    before approval.
                  </p>
                </div>
              )}
              {editable && (
                <details className="question-review-panel">
                  <summary>Save question-by-question review</summary>
                  <p className="small muted">
                    Saved question marks seed your complete-paper approval
                    below. Saving a question does not release a result.
                  </p>
                  {paper.rubric.questions.map((question) => (
                    <section className="question-lane-card" key={question.id}>
                      <h4>{question.label}</h4>
                      <QuestionDraft
                        key={`${question.id}:${paper.question_reviews.find((r) => r.question_id === question.id)?.id}`}
                        paper={paper}
                        question={question}
                        editable={editable}
                      />
                    </section>
                  ))}
                </details>
              )}
              <MarkingEditor
                key={`${paper.extraction.id}:${paper.proposal?.id}:${paper.decision?.id}:${paper.question_reviews.map((r) => r.id).join()}`}
                paper={paper}
                questions={paper.rubric.questions}
                editable={editable}
              />
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function ExtractionEditor({
  paper,
  questions,
  editable,
}: {
  paper: Submission;
  questions: Question[];
  editable: boolean;
}) {
  const [answers, setAnswers] = useState<S["AnswerMap"][]>(() =>
    questions.map(
      (question) =>
        paper.extraction?.answers.find(
          (answer) => answer.question_id === question.id,
        ) ?? {
          question_id: question.id,
          text:
            questions.length === 1
              ? (paper.extraction?.pages
                  .map((page) => page.text)
                  .join("\n\n") ?? "")
              : "",
          page_from: 1,
          page_to: paper.page_count,
          readable: false,
        },
    ),
  );
  const [confirmed, setConfirmed] = useState(false);
  const query = useQueryClient();
  const save = useMutation({
    mutationFn: () =>
      api(`/v1/submissions/${paper.id}/extractions`, {
        method: "POST",
        body: JSON.stringify({
          base_version: paper.extraction?.version ?? 0,
          pages_complete: true,
          identity_confirmed: true,
          answers,
        }),
      }),
    onSuccess: () => {
      refreshPaper(query, paper);
    },
  });
  function change(index: number, value: Partial<S["AnswerMap"]>) {
    setConfirmed(false);
    setAnswers(
      answers.map((answer, i) =>
        i === index ? { ...answer, ...value } : answer,
      ),
    );
  }
  return (
    <form
      className="extraction-form"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      {questions.map((question, index) => (
        <div className="answer-extraction" key={question.id}>
          <h4>
            {question.label}
            <span>{question.maximum} marks</span>
          </h4>
          <p className="question-prompt">{question.prompt}</p>
          <label>
            Reviewed answer for {question.label}
            <textarea
              rows={7}
              maxLength={20000}
              value={answers[index].text}
              disabled={!editable}
              onChange={(event) => change(index, { text: event.target.value })}
              placeholder="Transcribe or correct the student’s answer. Leave a genuinely blank answer empty."
            />
          </label>
          <div className="page-mapping">
            <label>
              From page
              <input
                type="number"
                min={1}
                max={paper.page_count}
                value={answers[index].page_from}
                disabled={!editable}
                onChange={(event) =>
                  change(index, { page_from: Number(event.target.value) })
                }
              />
            </label>
            <label>
              To page
              <input
                type="number"
                min={answers[index].page_from}
                max={paper.page_count}
                value={answers[index].page_to}
                disabled={!editable}
                onChange={(event) =>
                  change(index, { page_to: Number(event.target.value) })
                }
              />
            </label>
          </div>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={answers[index].readable}
              disabled={!editable}
              onChange={(event) =>
                change(index, { readable: event.target.checked })
              }
            />
            This answer is readable (or visibly blank).
          </label>
          {!answers[index].readable && (
            <p className="notice">
              Unreadable work remains in extraction review and cannot be
              approved as zero.
            </p>
          )}
        </div>
      ))}
      {editable && (
        <>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            I checked the student identity, page completeness/order, and every
            question mapping.
          </label>
          <Notice error={save.error} />
          <button
            className="button primary"
            disabled={!confirmed || save.isPending}
          >
            {save.isPending ? "Saving review…" : "Save extraction review"}
            <Check size={15} />
          </button>
        </>
      )}
    </form>
  );
}

function MarkingEditor({
  paper,
  questions,
  editable,
}: {
  paper: Submission;
  questions: Question[];
  editable: boolean;
}) {
  const proposal =
    paper.proposal?.extraction_id === paper.extraction?.id
      ? paper.proposal
      : null;
  const decision =
    paper.decision?.extraction_id === paper.extraction?.id
      ? paper.decision
      : null;
  const [marks, setMarks] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      questions.flatMap((question) =>
        question.criteria.map((criterion) => [
          criterion.id,
          decision?.marks.find((mark) => mark.criterion_id === criterion.id)
            ?.mark ??
            paper.question_reviews
              .flatMap((r) => r.marks)
              .find((mark) => mark.criterion_id === criterion.id)?.mark ??
            proposal?.output.criteria.find(
              (mark) => mark.criterion_id === criterion.id,
            )?.mark ??
            "",
        ]),
      ),
    ),
  );
  const [feedback, setFeedback] = useState(
    decision?.feedback ??
      (paper.question_reviews.length
        ? paper.question_reviews
            .map(
              (r) =>
                `${questions.find((q) => q.id === r.question_id)?.label}: ${r.feedback}`,
            )
            .join("\n\n")
        : (proposal?.output.feedback ?? "")),
  );
  const [reason, setReason] = useState(decision?.reason ?? "");
  const [confirmed, setConfirmed] = useState(false);
  const [releaseConfirm, setReleaseConfirm] = useState(false);
  const query = useQueryClient();
  const approve = useMutation({
    mutationFn: () =>
      api(`/v1/submissions/${paper.id}/decisions`, {
        method: "POST",
        body: JSON.stringify({
          extraction_id: paper.extraction!.id,
          question_review_ids: paper.question_reviews.map(
            (review) => review.id,
          ),
          proposal_id: proposal?.id ?? null,
          marks: Object.entries(marks).map(([criterion_id, mark]) => ({
            criterion_id,
            mark,
          })),
          feedback,
          reason,
        }),
      }),
    onSuccess: () => {
      refreshPaper(query, paper);
    },
  });
  const release = useMutation({
    mutationFn: () =>
      api(`/v1/submissions/${paper.id}/release`, {
        method: "POST",
        body: JSON.stringify({ decision_id: paper.decision!.id }),
      }),
    onSuccess: () => {
      setReleaseConfirm(false);
      refreshPaper(query, paper);
    },
  });
  const total = Object.values(marks).reduce(
    (sum, value) => sum + Number(value || 0),
    0,
  );
  return (
    <div className="marking-editor">
      <span className="eyebrow">CRITERION REVIEW</span>
      <h3>Make every mark traceable.</h3>
      {proposal && (
        <div className="proposal-label">
          <Sparkles size={15} />
          <span>
            {proposal.model} · {proposal.prompt_version}
            <small>
              {proposal.calibration_ids.length} teacher reference examples used
            </small>
            <small>Model digest {proposal.model_digest.slice(0, 12)}</small>
          </span>
        </div>
      )}
      {proposal?.output.review_reasons?.map((reason, index) => (
        <p className="notice" key={index}>
          {reason}
        </p>
      ))}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          approve.mutate();
        }}
      >
        {questions.map((question) => (
          <section className="mark-question" key={question.id}>
            <h4>
              {question.label} · {question.maximum} marks
            </h4>
            {question.criteria.map((criterion) => {
              const suggestion = proposal?.output.criteria.find(
                (mark) => mark.criterion_id === criterion.id,
              );
              return (
                <div className="mark-criterion" key={criterion.id}>
                  <div>
                    <strong>{criterion.label}</strong>
                    {suggestion && (
                      <>
                        <p>{suggestion.explanation}</p>
                        {suggestion.evidence_quote && (
                          <blockquote>
                            “{suggestion.evidence_quote}”
                            <small>Page {suggestion.evidence_page}</small>
                          </blockquote>
                        )}
                        <span className="small muted">
                          Suggested: {markText(suggestion.mark)} /{" "}
                          {markText(criterion.maximum)}
                        </span>
                      </>
                    )}
                  </div>
                  <label>
                    Mark
                    <input
                      aria-label={`Mark for ${criterion.label}`}
                      type="number"
                      min={0}
                      max={criterion.maximum}
                      step="0.01"
                      required
                      value={marks[criterion.id]}
                      disabled={!editable}
                      onChange={(event) => {
                        setConfirmed(false);
                        setMarks({
                          ...marks,
                          [criterion.id]: event.target.value,
                        });
                      }}
                    />
                    <span>/ {criterion.maximum}</span>
                  </label>
                </div>
              );
            })}
          </section>
        ))}
        <div className="mark-total">
          <span>Provisional total</span>
          <strong>
            {markText(total)}
            <small>
              {" "}
              /{" "}
              {markText(
                questions.reduce(
                  (sum, question) => sum + Number(question.maximum),
                  0,
                ),
              )}
            </small>
          </strong>
        </div>
        <p className="small muted">
          The server validates every criterion and calculates the approved
          total.
        </p>
        <label>
          Feedback for the student
          <textarea
            aria-label="Feedback for the student"
            required
            rows={4}
            maxLength={8000}
            disabled={!editable}
            value={feedback}
            onChange={(event) => {
              setConfirmed(false);
              setFeedback(event.target.value);
            }}
          />
        </label>
        <label>
          {proposal
            ? "Reason for changes to suggested marks"
            : "Manual grading reason"}
          <textarea
            aria-label={
              proposal
                ? "Reason for changes to suggested marks"
                : "Manual grading reason"
            }
            rows={2}
            maxLength={2000}
            required={!proposal}
            disabled={!editable}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={
              proposal
                ? "Required if you override a suggested mark"
                : "Explain the basis for your manual decision"
            }
          />
        </label>
        <Notice error={approve.error ?? release.error} />
        {editable && (
          <>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              I reviewed every criterion and the student feedback.
            </label>
            <button
              className="button primary"
              disabled={
                !confirmed ||
                approve.isPending ||
                paper.jobs.some((job) =>
                  ["queued", "running"].includes(job.status),
                )
              }
            >
              Approve result
              <ShieldCheck size={15} />
            </button>
          </>
        )}
      </form>
      {editable && paper.status === "approved" && decision && (
        <div className="release-panel">
          <strong>Approved. Ready for your final release.</strong>
          <p>
            The approved result is {markText(decision.total)} /{" "}
            {markText(decision.maximum)}. The student cannot see it yet.
          </p>
          {!releaseConfirm ? (
            <button
              className="button primary"
              onClick={() => setReleaseConfirm(true)}
            >
              Release to student
              <ArrowRight size={15} />
            </button>
          ) : (
            <>
              <p>
                Release this approved result? It will become visible to this
                student. Future corrections require re-evaluation and a new
                release.
              </p>
              <div className="inline-actions">
                <button
                  className="button"
                  onClick={() => setReleaseConfirm(false)}
                >
                  Keep private
                </button>
                <button
                  className="button primary"
                  disabled={release.isPending}
                  onClick={() => release.mutate()}
                >
                  Confirm release
                </button>
              </div>
            </>
          )}
        </div>
      )}
      {decision && (
        <details className="feedback-preview">
          <summary>Preview approved feedback cards</summary>
          <FeedbackCards
            questions={questions}
            marks={decision.marks}
            feedback={decision.question_feedback}
          />
        </details>
      )}
      {paper.status === "released" && (
        <p className="notice">
          <Check size={15} className="inline-icon" />
          Released. This approved result is visible only to the linked student.
        </p>
      )}
    </div>
  );
}

export function StudentResults({
  classroomId,
  canRequest = true,
}: {
  classroomId: string;
  canRequest?: boolean;
}) {
  const results = useQuery({
    queryKey: ["my-results", classroomId],
    queryFn: () =>
      api<S["ReleasedResult"][]>(`/v1/classrooms/${classroomId}/my-results`),
  });
  return (
    <div className="tab-content">
      <span className="eyebrow">YOUR LEARNING</span>
      <h3>Results & feedback</h3>
      <Notice error={results.error} />
      {results.isPending ? (
        <p>Loading released results…</p>
      ) : results.data?.length ? (
        results.data.map((result) => (
          <article className="student-result" key={result.submission_id}>
            <div>
              <h2>{result.assessment_title}</h2>
              <span className="status active">
                Released {new Date(result.released_at).toLocaleDateString()}
              </span>
            </div>
            <strong className="result-total">
              {markText(result.total)}
              <small> / {markText(result.maximum)}</small>
            </strong>
            <p className="student-feedback">{result.feedback}</p>
            <FeedbackCards
              questions={result.questions}
              marks={result.marks}
              feedback={result.question_feedback}
            />
            {canRequest && (
              <RequestQuestionReview result={result} classId={classroomId} />
            )}
          </article>
        ))
      ) : (
        <div className="empty-inline">
          <ShieldCheck size={30} />
          <h3>Your results will appear here.</h3>
          <p>
            Only results reviewed and released by your teacher are visible to
            you.
          </p>
        </div>
      )}
      <ReviewRequests classId={classroomId} student />
    </div>
  );
}
