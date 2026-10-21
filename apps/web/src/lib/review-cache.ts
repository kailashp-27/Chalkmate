import type { QueryClient } from "@tanstack/react-query";

// Refresh the review graph without re-fetching auth, rosters, or model discovery.
export function refreshAssessment(query: QueryClient, assessmentId: string) {
  for (const queryKey of [
    ["assessment", assessmentId],
    ["assessments"],
    ["submissions", assessmentId],
    ["review-queue", assessmentId],
    ["rubric-versions", assessmentId],
    ["calibrations", assessmentId],
    ["rubric-diff", assessmentId],
    ["topic-summary", assessmentId],
    ["intelligence-runs", assessmentId],
    ["intelligence-run"],
    ["teaching-materials"],
  ])
    void query.invalidateQueries({ queryKey });
}

export function refreshPaper(
  query: QueryClient,
  paper: { id: string; assessment_id: string },
) {
  refreshAssessment(query, paper.assessment_id);
  void query.invalidateQueries({ queryKey: ["submission", paper.id] });
  void query.invalidateQueries({ queryKey: ["review-history", paper.id] });
}
