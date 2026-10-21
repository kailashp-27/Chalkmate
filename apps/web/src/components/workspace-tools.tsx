"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CircleCheck,
  Command,
  Gauge,
  Sparkles,
} from "lucide-react";
import { api } from "../lib/api";
import type { components } from "../lib/api-schema";
import { InfoTip, Modal, Notice } from "./ui";

type S = components["schemas"];
export function CommandBox({
  classId,
  navigate,
}: {
  classId: string;
  navigate: (name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const preview = useMutation({
    mutationFn: (value: string) =>
      api<S["CommandOutput"]>(`/v1/classrooms/${classId}/command-preview`, {
        method: "POST",
        body: JSON.stringify({ text: value }),
      }),
  });
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  const close = () => {
    setOpen(false);
    preview.reset();
    setText("");
  };
  return (
    <>
      <button className="command-trigger" onClick={() => setOpen(true)}>
        <Command size={16} />
        <span>Find a tool</span>
        <kbd>⌘ / Ctrl K</kbd>
      </button>
      {open && (
        <Modal title="What’s next?" close={close}>
          <form
            className="command-form"
            onSubmit={(e) => {
              e.preventDefault();
              preview.mutate(text);
            }}
          >
            <label className="sr-only" htmlFor="workspace-command">
              Find a workflow
            </label>
            <input
              id="workspace-command"
              autoFocus
              required
              maxLength={300}
              placeholder="Open planning, show roster…"
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                preview.reset();
              }}
            />
            <button className="button primary" disabled={preview.isPending}>
              Find <ArrowRight size={15} />
            </button>
          </form>
          <div className="command-suggestions">
            {["Open planning", "Show roster", "Pilot readiness"].map((t) => (
              <button
                key={t}
                className="button small-button"
                onClick={() => {
                  setText(t);
                  preview.mutate(t);
                }}
              >
                {t}
              </button>
            ))}
          </div>
          <Notice error={preview.error} />
          {preview.data && (
            <div className="command-result">
              <strong>{preview.data.label}</strong>
              <p className="muted small">{preview.data.explanation}</p>
              {preview.data.destination && (
                <button
                  className="button primary"
                  onClick={() => {
                    navigate(preview.data!.destination!);
                    close();
                  }}
                >
                  Open <ArrowRight size={15} />
                </button>
              )}
            </div>
          )}
          <p className="quiet command-note">
            Commands open tools. Changes stay yours to review.
          </p>
        </Modal>
      )}
    </>
  );
}

export function ReadinessWorkspace({ classId }: { classId: string }) {
  const status = useQuery({
    queryKey: ["readiness", classId],
    queryFn: () =>
      api<S["ReadinessOutput"]>(`/v1/classrooms/${classId}/readiness`),
    refetchInterval: 15000,
  });
  const r = status.data;
  return (
    <div className="tab-content readiness-workspace">
      <div className="studio-heading">
        <div>
          <span className="eyebrow">A CLEARER PICTURE</span>
          <h2>
            Ready for the classroom?{" "}
            <InfoTip label="About readiness">
              These are live dependency, worker and planning usage checks for
              this classroom. They do not certify grading accuracy. A real pilot
              requires consented samples, held-out evaluation and measured
              teacher review time.
            </InfoTip>
          </h2>
        </div>
        <Gauge size={30} />
      </div>
      <Notice error={status.error} />
      {r ? (
        <>
          <div className="service-grid">
            {r.services?.map((service) => (
              <div className="service-card" key={service.name}>
                <span className={`service-light ${service.state}`} />
                <strong>{service.name}</strong>
                <span>
                  {service.state === "ready"
                    ? "Ready"
                    : service.state === "optional"
                      ? "Optional"
                      : "Needs attention"}
                </span>
                <InfoTip label={`${service.name} status`}>
                  {service.detail}
                </InfoTip>
              </div>
            ))}
          </div>
          <p className="quiet">
            {r.recovery?.verified
              ? `Local recovery verified · ${new Date(r.recovery.verified_at!).toLocaleString()}`
              : "Full local recovery has not been verified yet."}
          </p>
          <div className="readiness-grid">
            {[
              { label: "In progress", value: r.queued },
              { label: "Need attention", value: r.failed + r.expired },
              {
                label: "Daily attempts",
                value: `${r.attempts_today} / ${r.daily_limit}`,
              },
              { label: "Local output tokens", value: r.generated_tokens },
            ].map((v) => (
              <div className="readiness-stat" key={v.label}>
                <span>{v.label}</span>
                <strong>{v.value}</strong>
              </div>
            ))}
          </div>
          <div className="readiness-story">
            <span className="orbit-mark">
              <Sparkles size={25} />
            </span>
            <div>
              <h3>Tools ready. Teacher insight comes next.</h3>
              <p className="muted">{r.pilot_status}.</p>
              <details>
                <summary>Pilot checklist</summary>
                <ul>
                  <li>Collect consented, anonymized samples.</li>
                  <li>Keep calibration and held-out answers separate.</li>
                  <li>Compare marks, severe errors and review time.</li>
                  <li>Investigate errors before expanding use.</li>
                </ul>
                <p className="small muted">
                  The project’s evaluation guide includes the benchmark format
                  and recovery drill. No pilot target is claimed from synthetic
                  tests.
                </p>
              </details>
            </div>
          </div>
          <p className="quiet">
            <CircleCheck size={14} /> Planning drafts never change marks,
            publish or send automatically.
          </p>
        </>
      ) : (
        <p role="status">Checking classroom…</p>
      )}
    </div>
  );
}
