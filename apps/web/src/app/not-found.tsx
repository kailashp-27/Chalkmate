import Link from "next/link";

export default function NotFound() {
  return (
    <main className="recovery-page">
      <section className="panel">
        <span className="eyebrow">A FRESH START</span>
        <h1>That page isn’t here.</h1>
        <p className="muted">Open your workspace to find your classroom.</p>
        <Link className="button primary" href="/">
          Open workspace
        </Link>
      </section>
    </main>
  );
}
