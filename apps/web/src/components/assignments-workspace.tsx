"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  FileText,
  Plus,
  Upload,
} from "lucide-react";
import { api } from "../lib/api";
import type { components } from "../lib/api-schema";
import { InfoTip, Modal, Notice } from "./ui";

type S = components["schemas"];
type Assignment = S["AssignmentOutput"];
type Version = S["AssignmentVersionOutput"];

export function refreshFollowup(query: QueryClient, classroomId: string) {
  for (const queryKey of [
    ["assignments", classroomId],
    ["assignment-version"],
    ["assignment-history"],
    ["assignment-responses"],
    ["campaigns", classroomId],
    ["deliveries"],
    ["delivery-attempts"],
  ])
    void query.invalidateQueries({ queryKey });
}
const localDateInput = (value: string | null) =>
  value
    ? new Date(
        new Date(value).getTime() - new Date(value).getTimezoneOffset() * 60000,
      )
        .toISOString()
        .slice(0, 16)
    : "";
const dateText = (value: string | null) =>
  value ? new Date(value).toLocaleString() : "No due date";

export function AssignmentsWorkspace({
  classroom,
}: {
  classroom: S["ClassroomOutput"];
}) {
  const [selected, setSelected] = useState("");
  const [creating, setCreating] = useState(false);
  const query = useQuery({
    queryKey: ["assignments", classroom.id],
    queryFn: () =>
      api<Assignment[]>(`/v1/classrooms/${classroom.id}/assignments`),
  });
  if (selected)
    return (
      <AssignmentDetail
        key={selected}
        versionId={selected}
        back={() => setSelected("")}
        openVersion={setSelected}
      />
    );
  return (
    <div className="tab-content assignment-workspace">
      <div className="section-heading">
        <div>
          <span className="eyebrow">FROM FEEDBACK TO PRACTICE</span>
          <h3>
            Assignments{" "}
            <InfoTip label="About assignments">
              Draft instructions, review the student copy, and choose an
              audience before publishing. Responses stay private.
            </InfoTip>
          </h3>
        </div>
        {classroom.can_edit && !classroom.archived && (
          <button className="button primary" onClick={() => setCreating(true)}>
            <Plus size={16} />
            New assignment
          </button>
        )}
      </div>
      <Notice error={query.error} />
      {query.isPending ? (
        <p role="status">Loading assignments…</p>
      ) : query.data?.length ? (
        <div className="assignment-list">
          {query.data.map((item) => (
            <button
              className="assignment-row"
              key={item.id}
              onClick={() =>
                setSelected(
                  (classroom.can_edit && item.draft ? item.draft : item.version)
                    .id,
                )
              }
            >
              <span className="assessment-icon">
                <BookOpen size={22} />
              </span>
              <div>
                <strong>{item.version.title}</strong>
                <span>
                  {item.version.published_at
                    ? `Published v${item.version.version}`
                    : "Draft"}
                  {item.closed ? " · Closed" : ""} ·{" "}
                  {dateText(item.version.due_at)}
                </span>
                <small>
                  {classroom.role === "student"
                    ? item.own_response_version
                      ? `Your response v${item.own_response_version}`
                      : "Awaiting your response"
                    : `${item.response_count} responses · ${item.audience_count} assigned`}
                </small>
              </div>
              {item.draft && (
                <span className="status">Draft v{item.draft.version}</span>
              )}
              <ArrowRight size={16} />
            </button>
          ))}
        </div>
      ) : (
        <div className="paper-empty">
          <BookOpen size={30} />
          <h3>
            {classroom.can_edit
              ? "A next step for your students."
              : "Your assignments will appear here."}
          </h3>
          <p>
            {classroom.can_edit
              ? "Create instructions, choose an audience, then explicitly publish the version students should use."
              : "Only published work assigned to you is shown."}
          </p>
        </div>
      )}
      {creating && (
        <AssignmentEditor
          classroomId={classroom.id}
          close={() => setCreating(false)}
          saved={(item) => {
            setCreating(false);
            setSelected((item.draft ?? item.version).id);
          }}
        />
      )}
    </div>
  );
}

function AssignmentEditor({
  classroomId,
  current,
  close,
  saved,
}: {
  classroomId: string;
  current?: Assignment;
  close: () => void;
  saved: (item: Assignment) => void;
}) {
  const version = current?.draft ?? current?.version;
  const [title, setTitle] = useState(version?.title ?? "");
  const [instructions, setInstructions] = useState(version?.instructions ?? "");
  const [due, setDue] = useState(localDateInput(version?.due_at ?? null));
  const [reason, setReason] = useState("");
  const query = useQueryClient();
  const action = useMutation({
    mutationFn: () =>
      api<Assignment>(
        current
          ? `/v1/assignments/${current.id}/versions`
          : `/v1/classrooms/${classroomId}/assignments`,
        {
          method: "POST",
          body: JSON.stringify({
            base_version: version?.version ?? 0,
            title,
            instructions,
            due_at: due ? new Date(due).toISOString() : null,
            reason,
          }),
        },
      ),
    onSuccess: (item) => {
      refreshFollowup(query, classroomId);
      saved(item);
    },
  });
  return (
    <Modal
      title={
        current ? "Revise assignment instructions" : "Create an assignment"
      }
      close={close}
    >
      <p className="muted">
        Each save creates a preserved version. Students see it only after you
        publish it.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          action.mutate();
        }}
      >
        <label>
          Assignment title
          <input
            required
            maxLength={160}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label>
          Assignment instructions
          <textarea
            aria-label="Assignment instructions"
            required
            rows={8}
            maxLength={20000}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="Describe the work, what to submit, and any useful next steps."
          />
        </label>
        <label>
          Due date (optional)
          <input
            type="datetime-local"
            value={due}
            onChange={(e) => setDue(e.target.value)}
          />
        </label>
        {current && (
          <label>
            Reason for assignment revision
            <textarea
              required
              minLength={3}
              maxLength={2000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
        )}
        <Notice error={action.error} />
        <footer>
          <button type="button" className="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={action.isPending}>
            {current ? "Save new assignment version" : "Save assignment draft"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function PublishDialog({
  assignment,
  close,
}: {
  assignment: Assignment;
  close: () => void;
}) {
  const [all, setAll] = useState(true);
  const [ids, setIds] = useState<string[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const query = useQueryClient();
  const roster = useQuery({
    queryKey: ["assignment-roster", assignment.classroom_id],
    queryFn: () =>
      api<S["StudentOutput"][]>(
        `/v1/classrooms/${assignment.classroom_id}/students`,
      ),
  });
  const version = assignment.draft ?? assignment.version;
  const action = useMutation({
    mutationFn: () =>
      api(`/v1/assignment-versions/${version.id}/publish`, {
        method: "POST",
        body: JSON.stringify({ student_ids: all ? null : ids }),
      }),
    onSuccess: () => {
      refreshFollowup(query, assignment.classroom_id);
      close();
    },
  });
  return (
    <Modal title="Publish this assignment version" close={close}>
      <p>
        Publish <strong>{version.title}</strong>, version {version.version}.
        This pins the instructions and the student audience. It does not send an
        email.
      </p>
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={all}
          onChange={(e) => {
            setAll(e.target.checked);
            setConfirmed(false);
          }}
        />
        Assign to all currently active students
      </label>
      {!all && (
        <div className="audience-picker">
          {roster.data
            ?.filter((s) => s.status === "active")
            .map((student) => (
              <label className="checkbox-label" key={student.id}>
                <input
                  type="checkbox"
                  checked={ids.includes(student.id)}
                  onChange={(e) => {
                    setIds(
                      e.target.checked
                        ? [...ids, student.id]
                        : ids.filter((id) => id !== student.id),
                    );
                    setConfirmed(false);
                  }}
                />
                {student.name} · {student.registration_number}
              </label>
            ))}
        </div>
      )}
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        I reviewed the instructions, due date, and intended audience.
      </label>
      <Notice error={roster.error ?? action.error} />
      <footer>
        <button className="button" onClick={close}>
          Keep draft
        </button>
        <button
          className="button primary"
          disabled={!confirmed || action.isPending || (!all && !ids.length)}
          onClick={() => action.mutate()}
        >
          Publish assignment
        </button>
      </footer>
    </Modal>
  );
}

export function AssignmentDetail({
  versionId,
  back,
  openVersion,
}: {
  versionId: string;
  back: () => void;
  openVersion?: (id: string) => void;
}) {
  const query = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [history, setHistory] = useState(false);
  const data = useQuery({
    queryKey: ["assignment-version", versionId],
    queryFn: () => api<Assignment>(`/v1/assignment-versions/${versionId}`),
  });
  const versions = useQuery({
    queryKey: ["assignment-history", data.data?.id],
    queryFn: () => api<Version[]>(`/v1/assignments/${data.data!.id}/versions`),
    enabled: !!data.data?.is_staff,
  });
  const responses = useQuery({
    queryKey: ["assignment-responses", versionId],
    queryFn: () =>
      api<S["ResponseOutput"][]>(
        `/v1/assignment-versions/${versionId}/responses`,
      ),
    enabled: !!data.data?.version.published_at,
  });
  const close = useMutation({
    mutationFn: () =>
      api(`/v1/assignments/${data.data!.id}`, {
        method: "PATCH",
        body: JSON.stringify({ closed: !data.data!.closed }),
      }),
    onSuccess: () => refreshFollowup(query, data.data!.classroom_id),
  });
  const download = useMutation({
    mutationFn: async (id: string) => {
      const r = await api<{ url: string }>(
        `/v1/assignment-responses/${id}/download`,
      );
      window.open(r.url, "_blank", "noopener,noreferrer");
    },
  });
  if (data.isPending)
    return (
      <p className="tab-content" role="status">
        Opening assignment…
      </p>
    );
  if (!data.data)
    return (
      <div className="tab-content">
        <Notice error={data.error} />
        <button className="button" onClick={back}>
          Back to workspace
        </button>
      </div>
    );
  const item = data.data;
  const version = item.version;
  const latest = new Map<string, S["ResponseOutput"]>();
  for (const response of responses.data ?? [])
    if (!latest.has(response.student_id))
      latest.set(response.student_id, response);
  const visible = history ? (responses.data ?? []) : [...latest.values()];
  return (
    <div className="tab-content assignment-detail">
      <button className="text-button back-button" onClick={back}>
        <ArrowLeft size={15} />
        All assignments
      </button>
      <div className="assessment-heading">
        <div>
          <span className="eyebrow">
            ASSIGNMENT · VERSION {version.version}
          </span>
          <h2>{version.title}</h2>
          <p className="muted">{dateText(version.due_at)}</p>
        </div>
        <span className="status">
          {item.closed
            ? "Closed"
            : version.published_at
              ? "Published"
              : "Draft"}
        </span>
      </div>
      <Notice error={data.error ?? close.error ?? download.error} />
      <article className="assignment-instructions">
        <span className="eyebrow">YOUR NEXT STEP</span>
        <div>{version.instructions}</div>
      </article>
      {item.can_edit && (
        <>
          <div className="inline-actions assignment-actions">
            <button className="button" onClick={() => setEditing(true)}>
              Revise instructions
            </button>
            {!version.published_at && !item.closed && (
              <button
                className="button primary"
                onClick={() => setPublishing(true)}
              >
                Review & publish
              </button>
            )}
            <button
              className="button"
              disabled={close.isPending}
              onClick={() => close.mutate()}
            >
              {item.closed ? "Reopen assignment" : "Close assignment"}
            </button>
            {version.published_at && (
              <span className="small muted">
                {item.audience_count} assigned · {item.response_count} responded
              </span>
            )}
          </div>
          {versions.data && versions.data.length > 1 && (
            <label>
              Assignment version
              <select
                value={version.id}
                onChange={(e) =>
                  openVersion
                    ? openVersion(e.target.value)
                    : window.location.assign(`/assignments/${e.target.value}`)
                }
              >
                {versions.data.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version} · {v.published_at ? "Published" : "Draft"} ·{" "}
                    {v.title}
                  </option>
                ))}
              </select>
            </label>
          )}
        </>
      )}
      {item.can_submit && (
        <StudentResponseForm
          key={`${versionId}:${item.own_response_version}`}
          assignment={item}
          latest={responses.data?.[0]}
        />
      )}
      {!item.is_staff && !item.can_submit && (
        <p className="notice">
          This version is available to read but does not accept new responses.
          Check the workspace for the current assignment.
        </p>
      )}
      {version.published_at && (
        <section className="assignment-responses">
          <div className="section-heading">
            <div>
              <h3>
                {item.is_staff ? "Student responses" : "Your response history"}
              </h3>
              <p className="small muted">
                Earlier responses are retained. Late work is clearly marked.
              </p>
            </div>
            {item.is_staff && (
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={history}
                  onChange={(e) => setHistory(e.target.checked)}
                />
                Show response history
              </label>
            )}
          </div>
          <Notice error={responses.error} />
          {responses.isPending ? (
            <p>Loading responses…</p>
          ) : visible.length ? (
            visible.map((response) => (
              <article className="assignment-response" key={response.id}>
                <header>
                  <strong>{response.student_name}</strong>
                  <span className="status">
                    Response v{response.version}
                    {response.late ? " · Late" : ""}
                  </span>
                </header>
                <small className="muted">
                  {new Date(response.created_at).toLocaleString()}
                </small>
                <p>{response.text}</p>
                {response.filename && (
                  <button
                    className="text-button"
                    onClick={() => download.mutate(response.id)}
                  >
                    <FileText size={15} />
                    {response.filename}
                  </button>
                )}
              </article>
            ))
          ) : (
            <p className="empty-inline">No response submitted yet.</p>
          )}
        </section>
      )}
      {editing && (
        <AssignmentEditor
          classroomId={item.classroom_id}
          current={item}
          close={() => setEditing(false)}
          saved={(result) => {
            setEditing(false);
            const id = (result.draft ?? result.version).id;
            if (openVersion) openVersion(id);
            else window.location.assign(`/assignments/${id}`);
          }}
        />
      )}
      {publishing && (
        <PublishDialog assignment={item} close={() => setPublishing(false)} />
      )}
    </div>
  );
}

function StudentResponseForm({
  assignment,
  latest,
}: {
  assignment: Assignment;
  latest?: S["ResponseOutput"];
}) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const query = useQueryClient();
  const action = useMutation({
    mutationFn: () => {
      const body = new FormData();
      body.set("base_version", String(assignment.own_response_version));
      body.set("text", text);
      if (file) body.set("file", file);
      return api(`/v1/assignment-versions/${assignment.version.id}/responses`, {
        method: "POST",
        body,
      });
    },
    onSuccess: () => {
      setText("");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      refreshFollowup(query, assignment.classroom_id);
    },
  });
  return (
    <section className="student-response-form">
      <p className="small muted">
        {assignment.own_response_version
          ? `Your response v${assignment.own_response_version} has been submitted.`
          : ""}
      </p>
      <h3>
        {assignment.own_response_version
          ? "Submit an updated response"
          : "Your response"}
      </h3>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          action.mutate();
        }}
      >
        <label>
          Your assignment response
          <textarea
            aria-label="Your assignment response"
            rows={6}
            maxLength={20000}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        {latest && (
          <button
            type="button"
            className="text-button"
            onClick={() => setText(latest.text)}
          >
            Use your latest response as a starting point
          </button>
        )}
        <label>
          Attach a PDF or image
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <p className="small muted">
          Text or a private PDF/JPEG/PNG up to 10 MB. Only you and your
          classroom’s teaching team can read your work.
        </p>
        <Notice error={action.error} />
        {action.isSuccess && (
          <p className="notice">
            <Check size={15} />
            Response submitted.
          </p>
        )}
        <button
          className="button primary"
          disabled={action.isPending || (!text.trim() && !file)}
        >
          <Upload size={15} />
          {assignment.own_response_version
            ? "Submit updated response"
            : "Submit response"}
        </button>
      </form>
    </section>
  );
}

export function AssignmentLink({ versionId }: { versionId: string }) {
  return (
    <main className="assignment-link-page">
      <header>
        <a className="brand" href="/">
          chalkmate<span className="brand-dot">.</span>
        </a>
        <a className="button" href="/">
          Back to workspace
        </a>
      </header>
      <AssignmentDetail
        versionId={versionId}
        back={() => window.location.assign("/")}
        openVersion={(id) => window.location.assign(`/assignments/${id}`)}
      />
    </main>
  );
}
