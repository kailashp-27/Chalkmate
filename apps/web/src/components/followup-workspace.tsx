"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Mail, RefreshCw, Send } from "lucide-react";
import { api } from "../lib/api";
import type { components } from "../lib/api-schema";
import { InfoTip, Modal, Notice } from "./ui";
import { refreshFollowup } from "./assignments-workspace";

type S = components["schemas"];
type Preview = S["PreviewOutput"];
type Recipient = S["RecipientPreview"];
const value = (n: string | number | null) =>
  n === null
    ? "—"
    : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });

export function FollowupWorkspace({
  classroom,
}: {
  classroom: S["ClassroomOutput"];
}) {
  const query = useQueryClient();
  const editable = classroom.can_edit && !classroom.archived;
  const assessments = useQuery({
    queryKey: ["assessments", classroom.id],
    queryFn: () =>
      api<S["AssessmentOutput"][]>(
        `/v1/classrooms/${classroom.id}/assessments`,
      ),
  });
  const assignments = useQuery({
    queryKey: ["assignments", classroom.id],
    queryFn: () =>
      api<S["AssignmentOutput"][]>(
        `/v1/classrooms/${classroom.id}/assignments`,
      ),
  });
  const transport = useQuery({
    queryKey: ["mail-status"],
    queryFn: () => api<S["MailStatus"]>("/v1/mail/status"),
  });
  const campaigns = useQuery({
    queryKey: ["campaigns", classroom.id],
    queryFn: () =>
      api<S["CampaignOutput"][]>(`/v1/classrooms/${classroom.id}/campaigns`),
    refetchInterval: (q) =>
      q.state.data?.some(
        (c) => c.counts.queued || c.counts.sending || c.counts.accepted,
      )
        ? 5000
        : false,
  });
  const [assessmentId, setAssessmentId] = useState("");
  const [assignmentId, setAssignmentId] = useState("");
  const [operator, setOperator] = useState("lt");
  const [threshold, setThreshold] = useState("25");
  const [maximum, setMaximum] = useState("50");
  const [subject, setSubject] = useState("{assignment_title}: follow-up work");
  const [body, setBody] = useState(
    "Hello {student_name},\n\nPlease complete {assignment_title}.\n\n{assignment_link}\n\nYour teacher",
  );
  const [includeScore, setIncludeScore] = useState(false);
  const [skipSubmitted, setSkipSubmitted] = useState(false);
  const [excluded, setExcluded] = useState<string[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [dirty, setDirty] = useState(false);
  const [personalId, setPersonalId] = useState("");
  const [schedule, setSchedule] = useState("");
  const [approving, setApproving] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState("");
  const [contact, setContact] = useState<Recipient | null>(null);
  const makePreview = useMutation({
    mutationFn: () =>
      api<Preview>(`/v1/classrooms/${classroom.id}/campaign-previews`, {
        method: "POST",
        body: JSON.stringify({
          assignment_version_id: assignmentId,
          rule: { assessment_id: assessmentId, operator, threshold, maximum },
          subject,
          body,
          include_score: includeScore,
          skip_submitted: skipSubmitted,
          exclude_student_ids: excluded,
        }),
      }),
    onSuccess: (result) => {
      setPreview(result);
      setDirty(false);
      setPersonalId(
        result.snapshot.rows.find(
          (r) => r.eligible && !r.excluded && !r.blocked,
        )?.student_id ?? "",
      );
    },
  });
  const personal = useQuery({
    queryKey: ["personal-message", preview?.id, personalId],
    queryFn: () =>
      api<S["PersonalMessage"]>(
        `/v1/campaign-previews/${preview!.id}/recipients/${personalId}`,
      ),
    enabled: !!preview && !!personalId && !dirty,
  });
  const approve = useMutation({
    mutationFn: () =>
      api<S["CampaignOutput"]>(`/v1/classrooms/${classroom.id}/campaigns`, {
        method: "POST",
        body: JSON.stringify({
          preview_id: preview!.id,
          digest: preview!.digest,
          scheduled_at: schedule ? new Date(schedule).toISOString() : null,
        }),
      }),
    onSuccess: (result) => {
      setApproving(false);
      setPreview(null);
      setExcluded([]);
      setSelectedCampaign(result.id);
      refreshFollowup(query, classroom.id);
    },
  });
  return (
    <div className="tab-content followup-workspace">
      <div className="section-heading">
        <div>
          <span className="eyebrow">CLASSROOM FOLLOW-UP</span>
          <h3>
            Follow-up{" "}
            <InfoTip label="About follow-up">
              Filter approved scores, preview each private message, then approve
              a fixed recipient list. Sending requires your separate approval.
            </InfoTip>
          </h3>
        </div>
        <Mail size={24} />
      </div>
      <Notice
        error={
          assessments.error ??
          assignments.error ??
          transport.error ??
          campaigns.error
        }
      />
      {transport.data && (
        <div className="notice mail-transport-note">
          <strong>
            {transport.data.external ? "External email" : "Local email capture"}
          </strong>
          <p>{transport.data.detail}</p>
          {transport.data.inbox_url && (
            <a
              className="text-button"
              href={transport.data.inbox_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open local email inbox ↗
            </a>
          )}
        </div>
      )}
      {editable && (
        <section className="campaign-composer">
          <form
            onChange={() => {
              if (preview) setDirty(true);
            }}
            onSubmit={(e) => {
              e.preventDefault();
              makePreview.mutate();
            }}
          >
            <div className="followup-filter-grid">
              <label>
                Assessment for score filter
                <select
                  required
                  value={assessmentId}
                  onChange={(e) => {
                    setAssessmentId(e.target.value);
                    const item = assessments.data?.find(
                      (a) => a.id === e.target.value,
                    );
                    if (item?.rubric) setMaximum(item.rubric.maximum);
                  }}
                >
                  <option value="">Choose assessment</option>
                  {assessments.data
                    ?.filter((a) => a.status === "active")
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.title}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Published assignment
                <select
                  required
                  value={assignmentId}
                  onChange={(e) => setAssignmentId(e.target.value)}
                >
                  <option value="">Choose published assignment</option>
                  {assignments.data
                    ?.filter((a) => a.version.published_at && !a.closed)
                    .map((a) => (
                      <option key={a.id} value={a.version.id}>
                        {a.version.title} · v{a.version.version}
                      </option>
                    ))}
                </select>
              </label>
            </div>
            <div className="score-rule-inputs">
              <label>
                Score rule
                <select
                  value={operator}
                  onChange={(e) => setOperator(e.target.value)}
                >
                  <option value="lt">Below (&lt;)</option>
                  <option value="lte">At most (≤)</option>
                  <option value="eq">Exactly (=)</option>
                  <option value="gte">At least (≥)</option>
                  <option value="gt">Above (&gt;)</option>
                </select>
              </label>
              <label>
                Score threshold
                <input
                  type="number"
                  min={0}
                  max={10000}
                  step="0.01"
                  required
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value)}
                />
              </label>
              <label>
                Out of maximum
                <input
                  type="number"
                  min="0.01"
                  max={10000}
                  step="0.01"
                  required
                  value={maximum}
                  onChange={(e) => setMaximum(e.target.value)}
                />
              </label>
            </div>
            <p className="small muted">
              Below 25 means strictly less than 25. Missing, unapproved,
              withdrawn, and different-maximum records are shown separately.
            </p>
            <label>
              Message subject
              <input
                required
                maxLength={180}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />
            </label>
            <label>
              Message body
              <textarea
                aria-label="Message body"
                required
                rows={7}
                maxLength={12000}
                value={body}
                onChange={(e) => setBody(e.target.value)}
              />
            </label>
            <p className="small muted">
              Placeholders: {"{student_name}"}, {"{assignment_title}"},{" "}
              {"{assignment_link}"}. A protected assignment link is always
              included.
            </p>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={includeScore}
                onChange={(e) => setIncludeScore(e.target.checked)}
              />
              Include the student’s approved score in their email (requires
              released marks)
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={skipSubmitted}
                onChange={(e) => setSkipSubmitted(e.target.checked)}
              />
              Skip students who already submitted this assignment version
            </label>
            <Notice error={makePreview.error} />
            <button
              className="button primary"
              disabled={makePreview.isPending || !assessmentId || !assignmentId}
            >
              <RefreshCw size={15} />
              {preview ? "Refresh recipient preview" : "Preview recipients"}
            </button>
          </form>
        </section>
      )}
      {preview && (
        <section className="campaign-preview">
          <header>
            <div>
              <span className="eyebrow">REVIEW BEFORE APPROVAL</span>
              <h3>
                {preview.snapshot.selected_count} selected ·{" "}
                {preview.snapshot.blocked_count} unresolved
              </h3>
              <p className="small muted">
                Preview expires{" "}
                {new Date(preview.expires_at).toLocaleTimeString()}. This list
                is fixed by your approval.
              </p>
            </div>
            {dirty && <span className="status">Refresh needed</span>}
          </header>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>STUDENT</th>
                  <th>APPROVED SCORE</th>
                  <th>CONTACT / DISPOSITION</th>
                  <th>EXCLUDE</th>
                </tr>
              </thead>
              <tbody>
                {preview.snapshot.rows.map((row) => (
                  <tr key={row.student_id}>
                    <td>
                      <strong>{row.student_name}</strong>
                      <small className="block">{row.registration_number}</small>
                    </td>
                    <td>
                      {value(row.total)} / {value(row.maximum)}
                    </td>
                    <td>
                      <span
                        className={
                          row.blocked && !row.excluded
                            ? "warning-text"
                            : "muted"
                        }
                      >
                        {row.reason}
                      </span>
                      <small className="block">{row.email || "No email"}</small>
                      {row.eligible && (
                        <button
                          className="text-button"
                          onClick={() => setContact(row)}
                        >
                          Edit contact
                        </button>
                      )}
                    </td>
                    <td>
                      {row.eligible && (
                        <input
                          aria-label={`Exclude ${row.student_name}`}
                          type="checkbox"
                          checked={excluded.includes(row.student_id)}
                          onChange={(e) => {
                            setExcluded(
                              e.target.checked
                                ? [...excluded, row.student_id]
                                : excluded.filter(
                                    (id) => id !== row.student_id,
                                  ),
                            );
                            setDirty(true);
                          }}
                        />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {dirty ? (
            <p className="notice">
              The form or exclusions changed. Refresh the preview before
              approval.
            </p>
          ) : (
            <>
              <label>
                Preview a private message
                <select
                  value={personalId}
                  onChange={(e) => setPersonalId(e.target.value)}
                >
                  <option value="">Choose one recipient</option>
                  {preview.snapshot.rows
                    .filter((r) => r.eligible && !r.excluded && !r.blocked)
                    .map((r) => (
                      <option key={r.student_id} value={r.student_id}>
                        {r.student_name} · {r.email}
                      </option>
                    ))}
                </select>
              </label>
              <Notice error={personal.error} />
              {personal.data && (
                <article className="personal-message">
                  <small>To: {personal.data.to}</small>
                  <h4>{personal.data.subject}</h4>
                  <pre>{personal.data.text}</pre>
                </article>
              )}
              <label>
                Send time (optional)
                <input
                  type="datetime-local"
                  value={schedule}
                  onChange={(e) => setSchedule(e.target.value)}
                />
              </label>
              <p className="small muted">
                Leave blank to queue now. A future time schedules this approved
                reminder once. Eligibility and submission state are checked
                again before sending.
              </p>
              <button
                className="button primary"
                disabled={
                  !preview.snapshot.selected_count ||
                  !!preview.snapshot.blocked_count ||
                  !transport.data?.available
                }
                onClick={() => setApproving(true)}
              >
                {schedule ? <CalendarClock size={15} /> : <Send size={15} />}
                Review approval
              </button>
            </>
          )}
        </section>
      )}
      <section className="campaign-history">
        <span className="eyebrow">DELIVERY LEDGER</span>
        <h3>Approved follow-ups</h3>
        {campaigns.isPending ? (
          <p>Loading campaigns…</p>
        ) : campaigns.data?.length ? (
          campaigns.data.map((item) => (
            <button
              className={
                selectedCampaign === item.id
                  ? "campaign-row chosen"
                  : "campaign-row"
              }
              key={item.id}
              onClick={() => setSelectedCampaign(item.id)}
            >
              <div>
                <strong>{item.request.subject}</strong>
                <span>
                  {new Date(item.scheduled_at).toLocaleString()} ·{" "}
                  {item.provider === "mailpit"
                    ? "Local capture"
                    : "External email"}
                  {item.canceled ? " · Canceled" : ""}
                </span>
              </div>
              <span className="campaign-counts">
                {Object.entries(item.counts).map(([status, count]) => (
                  <span className="status" key={status}>
                    {count} {status}
                  </span>
                ))}
              </span>
            </button>
          ))
        ) : (
          <p className="empty-inline">
            No campaigns approved. A preview alone never queues mail.
          </p>
        )}
      </section>
      {selectedCampaign && (
        <DeliveryLedger campaignId={selectedCampaign} classroom={classroom} />
      )}
      {approving && preview && (
        <ApproveDialog
          preview={preview}
          schedule={schedule}
          transport={transport.data}
          pending={approve.isPending}
          error={approve.error}
          close={() => setApproving(false)}
          approve={() => approve.mutate()}
        />
      )}
      {contact && (
        <ContactEditor
          classroomId={classroom.id}
          row={contact}
          close={() => setContact(null)}
          changed={() => {
            setContact(null);
            setDirty(true);
          }}
        />
      )}
    </div>
  );
}

function ApproveDialog({
  preview,
  schedule,
  transport,
  pending,
  error,
  close,
  approve,
}: {
  preview: Preview;
  schedule: string;
  transport?: S["MailStatus"];
  pending: boolean;
  error: Error | null;
  close: () => void;
  approve: () => void;
}) {
  const [confirmed, setConfirmed] = useState(false);
  return (
    <Modal title="Approve this follow-up" close={close}>
      <p>
        Queue exactly{" "}
        <strong>{preview.snapshot.selected_count} individual messages</strong>{" "}
        for <strong>{preview.snapshot.assignment_title}</strong>, version{" "}
        {preview.snapshot.assignment_version}.
      </p>
      <p>
        {schedule
          ? `Scheduled for ${new Date(schedule).toLocaleString()}.`
          : "Ready to queue now."}{" "}
        Changed contacts, score versions, or instructions will be held for
        renewed review.
      </p>
      <p className="notice">{transport?.detail}</p>
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        I reviewed the intended recipients and private message content.
      </label>
      <Notice error={error} />
      <footer>
        <button className="button" onClick={close}>
          Keep preview
        </button>
        <button
          className="button primary"
          disabled={!confirmed || pending}
          onClick={approve}
        >
          Approve & queue {transport?.external ? "emails" : "local test emails"}
        </button>
      </footer>
    </Modal>
  );
}

function ContactEditor({
  classroomId,
  row,
  close,
  changed,
}: {
  classroomId: string;
  row: Recipient;
  close: () => void;
  changed: () => void;
}) {
  const [email, setEmail] = useState(row.email ?? "");
  const action = useMutation({
    mutationFn: () =>
      api(`/v1/classrooms/${classroomId}/students/${row.student_id}/contact`, {
        method: "PATCH",
        body: JSON.stringify({ email: email || null }),
      }),
    onSuccess: changed,
  });
  return (
    <Modal title={`Contact for ${row.student_name}`} close={close}>
      <p className="muted">
        Email must match the student’s verified linked portal account. Unlinked
        students can be invited from People; unresolved records can be
        explicitly excluded.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          action.mutate();
        }}
      >
        <label>
          Student contact email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <Notice error={action.error} />
        <footer>
          <button type="button" className="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={action.isPending}>
            Save contact
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function DeliveryLedger({
  campaignId,
  classroom,
}: {
  campaignId: string;
  classroom: S["ClassroomOutput"];
}) {
  const query = useQueryClient();
  const [attemptId, setAttemptId] = useState("");
  const deliveries = useQuery({
    queryKey: ["deliveries", campaignId],
    queryFn: () =>
      api<S["DeliveryOutput"][]>(`/v1/campaigns/${campaignId}/deliveries`),
    refetchInterval: (q) =>
      q.state.data?.some((d) =>
        ["queued", "sending", "accepted"].includes(d.status),
      )
        ? 5000
        : false,
  });
  const action = useMutation({
    mutationFn: ({ id, kind }: { id: string; kind: string }) =>
      api(`/v1/deliveries/${id}/${kind}`, { method: "POST" }),
    onSuccess: () => refreshFollowup(query, classroom.id),
  });
  const cancel = useMutation({
    mutationFn: () =>
      api(`/v1/campaigns/${campaignId}/cancel`, { method: "POST" }),
    onSuccess: () => refreshFollowup(query, classroom.id),
  });
  const editable = classroom.can_edit && !classroom.archived;
  return (
    <section className="delivery-ledger">
      <div className="section-heading">
        <h3>Recipient outcomes</h3>
        {editable &&
          deliveries.data?.some((d) =>
            ["queued", "failed", "held"].includes(d.status),
          ) && (
            <button
              className="button"
              disabled={cancel.isPending}
              onClick={() => cancel.mutate()}
            >
              Cancel pending messages
            </button>
          )}
      </div>
      <Notice error={deliveries.error ?? action.error ?? cancel.error} />
      <p className="small muted">
        Captured means stored in the local test inbox. Accepted means the
        provider accepted the request; delivery is confirmed separately.
        Uncertain items require reconciliation, not a blind resend.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>STUDENT</th>
              <th>OUTCOME</th>
              <th>DETAIL</th>
              <th>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {deliveries.data?.map((d) => (
              <tr key={d.id}>
                <td>
                  <strong>{d.student_name}</strong>
                  <small className="block">{d.email}</small>
                </td>
                <td>
                  <span className="status">
                    {d.status === "captured" ? "Captured locally" : d.status}
                  </span>
                  <small className="block">
                    {d.attempts} attempt{d.attempts === 1 ? "" : "s"}
                  </small>
                </td>
                <td>{d.detail}</td>
                <td>
                  <div className="ledger-actions">
                    <button
                      className="text-button"
                      onClick={() => setAttemptId(d.id)}
                    >
                      Attempt history
                    </button>
                    {editable &&
                      ["queued", "failed", "held"].includes(d.status) && (
                        <button
                          className="text-button"
                          disabled={action.isPending}
                          onClick={() =>
                            action.mutate({ id: d.id, kind: "cancel" })
                          }
                        >
                          Cancel recipient
                        </button>
                      )}
                    {editable && d.status === "failed" && d.attempts < 3 && (
                      <button
                        className="text-button"
                        disabled={action.isPending}
                        onClick={() =>
                          action.mutate({ id: d.id, kind: "retry" })
                        }
                      >
                        Retry confirmed failure
                      </button>
                    )}
                    {editable &&
                      ["uncertain", "accepted"].includes(d.status) && (
                        <button
                          className="text-button"
                          disabled={action.isPending}
                          onClick={() =>
                            action.mutate({ id: d.id, kind: "reconcile" })
                          }
                        >
                          Reconcile outcome
                        </button>
                      )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {attemptId && (
        <AttemptHistory deliveryId={attemptId} close={() => setAttemptId("")} />
      )}
    </section>
  );
}

function AttemptHistory({
  deliveryId,
  close,
}: {
  deliveryId: string;
  close: () => void;
}) {
  const data = useQuery({
    queryKey: ["delivery-attempts", deliveryId],
    queryFn: () =>
      api<S["AttemptOutput"][]>(`/v1/deliveries/${deliveryId}/attempts`),
  });
  return (
    <Modal title="Delivery attempt history" close={close}>
      <Notice error={data.error} />
      {data.isPending ? (
        <p>Loading attempt history…</p>
      ) : data.data?.length ? (
        data.data.map((a) => (
          <article className="history-event" key={a.id}>
            <strong>
              {a.outcome} · {new Date(a.created_at).toLocaleString()}
            </strong>
            <p>{a.detail}</p>
            {a.provider_id && (
              <small className="muted">Provider receipt: {a.provider_id}</small>
            )}
          </article>
        ))
      ) : (
        <p>
          No send attempt yet. Scheduled messages remain in the durable queue
          until their approved time.
        </p>
      )}
    </Modal>
  );
}
