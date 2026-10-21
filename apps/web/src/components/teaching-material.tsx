"use client";
import { useState } from "react";
import { Modal, Notice } from "./ui";
import type { Material } from "./intelligence-workspace";
const emptyItem = () => ({ question: "", hint: "", answer: "", rationale: "" });
export function MaterialEditor({
  current,
  kind,
  pending,
  error,
  close,
  save,
}: {
  current?: Material;
  kind: "remedial" | "revision";
  pending: boolean;
  error: Error | null;
  close: () => void;
  save: (content: Material, reason: string) => void;
}) {
  const [title, setTitle] = useState(current?.title ?? "");
  const [intro, setIntro] = useState(current?.introduction ?? "");
  const [objectives, setObjectives] = useState(
    current?.objectives.join("\n") ?? "",
  );
  const [notes, setNotes] = useState(current?.revision_notes.join("\n") ?? "");
  const [items, setItems] = useState(current?.items ?? [emptyItem()]);
  const [reason, setReason] = useState("");
  const lines = (v: string) =>
    v
      .split("\n")
      .map((v) => v.trim())
      .filter(Boolean);
  function update(
    index: number,
    key: keyof Material["items"][number],
    value: string,
  ) {
    setItems((old) =>
      old.map((item, i) => (i === index ? { ...item, [key]: value } : item)),
    );
  }
  return (
    <Modal
      title={current ? "Revise teaching material" : "Write teaching material"}
      close={close}
    >
      <p className="muted">
        Student practice and the private answer key are separate. Each save
        retains a material version.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save(
            {
              title,
              introduction: intro,
              objectives: lines(objectives),
              revision_notes: lines(notes),
              items,
            },
            reason || "Initial teacher-authored material",
          );
        }}
      >
        <label>
          Practice title
          <input
            required
            minLength={3}
            maxLength={160}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label>
          Student introduction
          <textarea
            required
            maxLength={3000}
            value={intro}
            onChange={(e) => setIntro(e.target.value)}
          />
        </label>
        <label>
          Learning objectives (one per line, up to 6)
          <textarea
            required
            maxLength={2400}
            rows={3}
            value={objectives}
            onChange={(e) => setObjectives(e.target.value)}
          />
        </label>
        <label>
          Revision notes (one per line, up to 8)
          <textarea
            required={kind === "revision"}
            maxLength={16000}
            rows={4}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </label>
        {items.map((item, i) => (
          <fieldset className="material-question-editor" key={i}>
            <legend>Practice question {i + 1}</legend>
            <label>
              Question {i + 1}
              <textarea
                required
                maxLength={3000}
                value={item.question}
                onChange={(e) => update(i, "question", e.target.value)}
              />
            </label>
            <label>
              Hint {i + 1} (student-visible)
              <textarea
                maxLength={1000}
                value={item.hint}
                onChange={(e) => update(i, "hint", e.target.value)}
              />
            </label>
            <label>
              Teacher answer {i + 1}
              <textarea
                required
                maxLength={3000}
                value={item.answer}
                onChange={(e) => update(i, "answer", e.target.value)}
              />
            </label>
            <label>
              Teacher rationale {i + 1}
              <textarea
                required
                maxLength={2000}
                value={item.rationale}
                onChange={(e) => update(i, "rationale", e.target.value)}
              />
            </label>
            {items.length > 1 && (
              <button
                type="button"
                className="text-button"
                onClick={() => setItems((old) => old.filter((_, j) => i !== j))}
              >
                Remove question {i + 1}
              </button>
            )}
          </fieldset>
        ))}
        {items.length < 8 && (
          <button
            type="button"
            className="button"
            onClick={() => setItems((old) => [...old, emptyItem()])}
          >
            Add practice question
          </button>
        )}
        {current && (
          <label>
            Reason for material revision
            <textarea
              required
              minLength={3}
              maxLength={2000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
        )}
        <Notice error={error} />
        <footer>
          <button type="button" className="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={pending}>
            {current
              ? "Save new material version"
              : "Save teacher-authored material"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}
export function MaterialPreview({ content }: { content: Material }) {
  return (
    <>
      <article className="material-student-preview">
        <span className="eyebrow">STUDENT PRACTICE PREVIEW</span>
        <p className="preserve-text">{content.introduction}</p>
        <h4>Learning goals</h4>
        <ul>
          {content.objectives.map((o, i) => (
            <li key={i}>{o}</li>
          ))}
        </ul>
        {content.revision_notes.length > 0 && (
          <>
            <h4>Revision notes</h4>
            {content.revision_notes.map((note, i) => (
              <p className="preserve-text" key={i}>
                {note}
              </p>
            ))}
          </>
        )}
        <ol className="material-questions">
          {content.items.map((item, i) => (
            <li key={i}>
              <p className="preserve-text">{item.question}</p>
              {item.hint && (
                <p className="small muted preserve-text">Hint: {item.hint}</p>
              )}
            </li>
          ))}
        </ol>
      </article>
      <details className="material-teacher-key">
        <summary>Private teacher answer key</summary>
        <p className="small muted">
          Excluded from student exports and assignment drafts.
        </p>
        {content.items.map((item, i) => (
          <article key={i}>
            <h4>Answer {i + 1}</h4>
            <p className="preserve-text">{item.answer}</p>
            <p className="small muted preserve-text">
              Teaching rationale: {item.rationale}
            </p>
          </article>
        ))}
      </details>
    </>
  );
}
