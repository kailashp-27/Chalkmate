"use client";

import { useEffect, useState, useRef } from "react";
import { Monitor, Moon, Settings2, Sun, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { components } from "../lib/api-schema";

type Preference = "light" | "dark" | "system";
const KEY = "chalkmate.appearance.v1";

export function AppearanceSettings({
  authenticated = true,
}: {
  authenticated?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const [preference, setPreference] = useState<Preference>(() => {
    if (typeof window === "undefined") return "dark";
    try {
      const saved = localStorage.getItem(KEY);
      return saved === "light" || saved === "dark"
        ? saved
        : saved === "system"
          ? "system"
          : "dark";
    } catch {
      return "dark";
    }
  });
  useEffect(() => {
    if (open) dialog.current?.showModal();
  }, [open]);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      document.documentElement.dataset.theme =
        preference === "system"
          ? media.matches
            ? "dark"
            : "light"
          : preference;
    };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [preference]);
  const status = useQuery({
    queryKey: ["processing-status"],
    queryFn: () =>
      api<components["schemas"]["ProcessingStatus"]>("/v1/processing/status"),
    enabled: open && authenticated,
  });
  return (
    <>
      <button
        className="settings-trigger"
        aria-label="Settings"
        onClick={() => setOpen(true)}
      >
        <Settings2 size={17} />
        <span>Settings</span>
      </button>
      {open && (
        <dialog
          ref={dialog}
          onCancel={() => setOpen(false)}
          className="settings-dialog"
          aria-labelledby="settings-title"
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
          }}
        >
          <header>
            <h2 id="settings-title">Make it yours.</h2>
            <button
              className="icon-button"
              aria-label="Close settings"
              onClick={() => setOpen(false)}
            >
              <X size={20} />
            </button>
          </header>
          <h3>Appearance</h3>
          <p className="muted">
            Charcoal surfaces. Blue accents. Your preferred light.
          </p>
          <fieldset className="theme-options">
            <legend className="sr-only">Color mode</legend>
            {[
              { value: "light", label: "Light", icon: Sun },
              { value: "dark", label: "Dark", icon: Moon },
              { value: "system", label: "System", icon: Monitor },
            ].map(({ value, label, icon: Icon }) => (
              <label
                key={value}
                className={
                  preference === value ? "theme-option chosen" : "theme-option"
                }
              >
                <input
                  type="radio"
                  name="theme"
                  value={value}
                  checked={preference === value}
                  onChange={() => {
                    setPreference(value as Preference);
                    localStorage.setItem(KEY, value);
                  }}
                />
                <Icon size={23} />
                <strong>{label}</strong>
                <span className={`theme-swatch ${value}`} />
              </label>
            ))}
          </fieldset>
          <p className="small muted">
            Saved on this browser. System follows your device’s color
            preference.
          </p>
          {authenticated && (
            <div className="processing-settings">
              <h3>Local processing</h3>
              <p className="muted">
                {status.data?.detail ?? "Checking Ollama…"}
              </p>
              {status.data?.models.length ? (
                <ul>
                  {status.data.models.map((model) => (
                    <li key={model}>{model}</li>
                  ))}
                </ul>
              ) : (
                <p className="small muted">
                  Run a local Ollama model to enable AI suggestions. Manual
                  review remains available.
                </p>
              )}
              <p className="small muted">
                The model is selected for each processing run and recorded with
                its suggestions. No cloud API key is needed.
              </p>
            </div>
          )}
          <button className="button primary" onClick={() => setOpen(false)}>
            Done
          </button>
        </dialog>
      )}
    </>
  );
}
