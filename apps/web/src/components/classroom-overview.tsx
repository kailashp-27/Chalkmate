"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, LayoutDashboard, MessageCircle } from "lucide-react";
import { api } from "../lib/api";
import type { components } from "../lib/api-schema";
import { InfoTip, Modal, Notice } from "./ui";

type S = components["schemas"];
type Request = S["ReviewRequestOutput"];

export function ReviewRequests({
  classId,
  canEdit = false,
  student = false,
}: {
  classId: string;
  canEdit?: boolean;
  student?: boolean;
}) {
  const query = useQueryClient();
  const [selected, setSelected] = useState<Request | null>(null);
  const [response, setResponse] = useState("");
  const requests = useQuery({
    queryKey: ["review-requests", classId],
    queryFn: () => api<Request[]>(`/v1/classrooms/${classId}/review-requests`),
    refetchInterval: 15000,
  });
  const reply = useMutation({
    mutationFn: () =>
      api(`/v1/review-requests/${selected!.id}/resolve`, {
        method: "POST",
        body: JSON.stringify({ response }),
      }),
    onSuccess: () => {
      setSelected(null);
      setResponse("");
      query.invalidateQueries({ queryKey: ["review-requests", classId] });
      query.invalidateQueries({ queryKey: ["overview", classId] });
    },
  });
  return (
    <section className="review-request-list" aria-label="Review requests">
      <div className="section-heading">
        <h3>
          <MessageCircle size={18} />{" "}
          {student ? "Your review requests" : "Student review requests"}
        </h3>
        <InfoTip label="About review requests">
          Requests refer to a specific released question. A response records the
          teacher’s explanation. Marks change only through the separate review
          and release workflow.
        </InfoTip>
      </div>
      <Notice error={requests.error} />
      {requests.isPending ? (
        <p className="quiet">Loading requests…</p>
      ) : requests.data?.length ? (
        requests.data.map((item) => (
          <article className="request-card" key={item.id}>
            <div className="section-heading">
              <strong>
                {item.assessment_title} · {item.question_label}
              </strong>
              <span className="status">
                {item.resolved_at ? "Responded" : "Awaiting teacher"}
              </span>
            </div>
            {!student && <p className="quiet">{item.student_label}</p>}
            <p className="request-copy">{item.reason}</p>
            {item.response ? (
              <blockquote className="request-copy">{item.response}</blockquote>
            ) : canEdit ? (
              <button
                className="button small-button"
                onClick={() => {
                  setSelected(item);
                  setResponse("");
                  reply.reset();
                }}
              >
                Respond
              </button>
            ) : null}
            <small className="quiet">
              {new Date(item.created_at).toLocaleDateString()}
              {item.resolved_at
                ? ` · Responded ${new Date(item.resolved_at).toLocaleDateString()}`
                : ""}
            </small>
          </article>
        ))
      ) : (
        <p className="quiet">No review requests yet.</p>
      )}
      {selected && (
        <Modal
          title="Respond to review request"
          close={() => setSelected(null)}
        >
          <p>
            {selected.student_label} · {selected.question_label}
          </p>
          <p className="request-copy">{selected.reason}</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              reply.mutate();
            }}
          >
            <label>
              Teacher response
              <textarea
                required
                minLength={10}
                maxLength={2000}
                rows={4}
                value={response}
                onChange={(e) => setResponse(e.target.value)}
              />
            </label>
            <p className="quiet">
              Explain your decision or completed review. This response does not
              change or release marks.
            </p>
            <Notice error={reply.error} />
            <button className="button primary" disabled={reply.isPending}>
              Save response
            </button>
          </form>
        </Modal>
      )}
    </section>
  );
}

export function ClassroomOverview({
  classId,
  canEdit,
  navigate,
}: {
  classId: string;
  canEdit: boolean;
  navigate: (name: string) => void;
}) {
  const overview = useQuery({
    queryKey: ["overview", classId],
    queryFn: () =>
      api<S["OverviewOutput"]>(`/v1/classrooms/${classId}/overview`),
    refetchInterval: 15000,
  });
  return (
    <div className="tab-content classroom-overview">
      <div className="studio-heading">
        <div>
          <span className="eyebrow">ONE CLEAR NEXT STEP</span>
          <h2>Your classroom, at a glance</h2>
        </div>
        <LayoutDashboard size={28} />
      </div>
      <Notice error={overview.error} />
      <div className="overview-grid">
        {overview.data?.tasks.map((task) => (
          <div className="overview-task" key={task.label}>
            <div>
              <span>{task.label}</span>
              <InfoTip label={`About ${task.label.toLowerCase()}`}>
                {task.detail}
              </InfoTip>
            </div>
            <strong>{task.count}</strong>
            {task.destination !== "Overview" && (
              <button
                className="text-button"
                onClick={() => navigate(task.destination)}
              >
                Open {task.destination.toLowerCase()} <ArrowRight size={14} />
              </button>
            )}
          </div>
        ))}
      </div>
      {overview.isPending && <p className="quiet">Checking classroom tasks…</p>}
      <ReviewRequests classId={classId} canEdit={canEdit} />
    </div>
  );
}

export function RequestQuestionReview({
  result,
  classId,
}: {
  result: S["ReleasedResult"];
  classId: string;
}) {
  const query = useQueryClient();
  const [open, setOpen] = useState(false);
  const [questionId, setQuestionId] = useState(result.questions[0]?.id ?? "");
  const [reason, setReason] = useState("");
  const create = useMutation({
    mutationFn: () =>
      api(`/v1/classrooms/${classId}/review-requests`, {
        method: "POST",
        body: JSON.stringify({
          submission_id: result.submission_id,
          question_id: questionId,
          released_at: result.released_at,
          reason,
        }),
      }),
    onSuccess: () => {
      setOpen(false);
      setReason("");
      query.invalidateQueries({ queryKey: ["review-requests", classId] });
    },
  });
  return (
    <>
      <button
        className="button small-button"
        onClick={() => {
          setOpen(true);
          create.reset();
        }}
      >
        Request a review
      </button>
      {open && (
        <Modal title="Request a question review" close={() => setOpen(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <label>
              Question
              <select
                aria-label="Question to review"
                value={questionId}
                onChange={(e) => setQuestionId(e.target.value)}
                required
              >
                {result.questions.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.label} · {q.prompt}
                  </option>
                ))}
              </select>
            </label>
            <label>
              What should your teacher review?
              <textarea
                required
                minLength={10}
                maxLength={2000}
                rows={4}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <p className="quiet">
              Your current released result stays visible while your teacher
              reviews this request.
            </p>
            <Notice error={create.error} />
            <button className="button primary" disabled={create.isPending}>
              Send review request
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}
