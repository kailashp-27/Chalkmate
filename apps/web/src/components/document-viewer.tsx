"use client";
import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from "lucide-react";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export default function DocumentViewer({
  url,
  contentType,
  pageCount,
}: {
  url: string;
  contentType: string;
  pageCount: number;
}) {
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState("");
  return (
    <div className="document-viewer">
      <div className="viewer-toolbar">
        <div>
          <button
            className="icon-button"
            aria-label="Previous page"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            <ChevronLeft size={16} />
          </button>
          <span>
            Page {page} / {pageCount}
          </span>
          <button
            className="icon-button"
            aria-label="Next page"
            disabled={page === pageCount}
            onClick={() => setPage(page + 1)}
          >
            <ChevronRight size={16} />
          </button>
        </div>
        <div>
          <button
            className="icon-button"
            aria-label="Zoom out"
            disabled={zoom <= 0.6}
            onClick={() => setZoom(zoom - 0.2)}
          >
            <ZoomOut size={16} />
          </button>
          <span>{Math.round(zoom * 100)}%</span>
          <button
            className="icon-button"
            aria-label="Zoom in"
            disabled={zoom >= 2}
            onClick={() => setZoom(zoom + 0.2)}
          >
            <ZoomIn size={16} />
          </button>
        </div>
      </div>
      <div className="document-canvas">
        {contentType === "application/pdf" ? (
          <Document
            file={url}
            onLoadError={() =>
              setError(
                "This PDF could not be displayed. Refresh the authorized link or open the original.",
              )
            }
            loading={<p>Loading original paper…</p>}
          >
            <Page
              pageNumber={page}
              width={Math.round(470 * zoom)}
              renderTextLayer={false}
              renderAnnotationLayer={false}
            />
          </Document>
        ) : (
          <img
            src={url}
            alt="Original student answer sheet"
            style={{ width: `${Math.round(zoom * 100)}%`, maxWidth: "none" }}
          />
        )}
        {error && <p role="alert">{error}</p>}
      </div>
      <a
        className="text-button"
        href={url}
        target="_blank"
        rel="noopener noreferrer"
      >
        Open original in a new tab
      </a>
    </div>
  );
}
