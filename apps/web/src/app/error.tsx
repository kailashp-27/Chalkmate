"use client";

import Link from "next/link";

export default function ErrorPage({
  retry,
}: {
  error: unknown;
  retry: () => void;
}) {
  return (
    <main className="recovery-page">
      <section className="panel">
        <span className="eyebrow">LET’S GET YOU BACK</span>
        <h1>This view couldn’t load.</h1>
        <p className="muted">Try again, or return to your workspace.</p>
        <div className="button-group">
          <button className="button primary" onClick={retry}>
            Try again
          </button>
          <Link className="button" href="/">
            Open workspace
          </Link>
        </div>
      </section>
    </main>
  );
}
