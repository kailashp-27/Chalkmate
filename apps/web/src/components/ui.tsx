"use client";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { Info, X } from "lucide-react";

export function InfoTip({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const bubble = useRef<HTMLSpanElement>(null);
  const [position, setPosition] = useState({ left: 16, top: 16 });
  useLayoutEffect(() => {
    if (!open || !trigger.current || !bubble.current) return;
    const reposition = () => {
      if (!trigger.current || !bubble.current) return;
      const anchor = trigger.current.getBoundingClientRect();
      const bounds = bubble.current.getBoundingClientRect();
      setPosition({
        left: Math.max(
          16,
          Math.min(anchor.left, window.innerWidth - bounds.width - 16),
        ),
        top:
          anchor.top > bounds.height + 24
            ? anchor.top - bounds.height - 8
            : Math.min(
                anchor.bottom + 8,
                window.innerHeight - bounds.height - 16,
              ),
      });
    };
    reposition();
    const dismiss = () => setOpen(false);
    window.addEventListener("resize", dismiss);
    window.addEventListener("scroll", reposition, true);
    return () => {
      window.removeEventListener("resize", dismiss);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [open]);
  return (
    <span
      className="info-tip"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          e.preventDefault();
          setOpen(false);
        }
      }}
    >
      <button
        ref={trigger}
        type="button"
        className="info-trigger"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen(true)}
      >
        <Info size={15} />
      </button>
      {open && (
        <span
          ref={bubble}
          className="info-bubble"
          role="tooltip"
          id={id}
          style={{
            position: "fixed",
            left: position.left,
            top: position.top,
            bottom: "auto",
            right: "auto",
          }}
        >
          {children}
        </span>
      )}
    </span>
  );
}

export function Notice({
  error,
  children,
}: {
  error?: Error | null;
  children?: React.ReactNode;
}) {
  return error ? (
    <p className="notice error" role="alert">
      {error.message}
    </p>
  ) : children ? (
    <p className="notice" role="status">
      {children}
    </p>
  ) : null;
}

export function Modal({
  title,
  children,
  close,
}: {
  title: string;
  children: React.ReactNode;
  close: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  return (
    <dialog ref={dialog} onCancel={close} aria-labelledby={titleId}>
      <header>
        <h2 id={titleId}>{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={close}
        >
          <X size={20} />
        </button>
      </header>
      {children}
    </dialog>
  );
}
