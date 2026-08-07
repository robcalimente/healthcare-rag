// Snapshot of backend/eval/summary.json as of the last eval run against the
// deployed backend. Not fetched live -- the eval is run offline and this file
// is updated by hand when a new run produces different numbers, same pattern as
// the pre-built vector index.
export const evalSummary = {
  total_questions: 40,
  graded_questions: 40,
  answer_accuracy: 0.675,
  router_accuracy: 1.0,
  by_mode: {
    patient: { n: 20, answer_accuracy: 0.35 },
    population: { n: 20, answer_accuracy: 1.0 },
  },
  eval_date: "2026-08-07",
};
