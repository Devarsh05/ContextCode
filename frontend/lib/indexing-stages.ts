/**
 * Maps the backend indexing pipeline's `current_stage` / `status` values
 * (emitted by app/workers/tasks.py over SSE) to an ordered, human-readable
 * stepper. Pure module — safe to unit test in isolation.
 */

export interface IndexingStage {
  /** Raw `current_stage` value emitted by the backend. */
  key: string;
  /** Human-readable label shown in the stepper. */
  label: string;
}

/** Ordered pipeline stages, matching the backend's progression. */
export const STAGES: IndexingStage[] = [
  { key: "cloning", label: "Cloning repository" },
  { key: "walking", label: "Scanning files" },
  { key: "parsing", label: "Parsing code (AST)" },
  { key: "persisting", label: "Saving chunks" },
  { key: "embedding", label: "Generating embeddings" },
  { key: "storing", label: "Building vector index" },
  { key: "building_graph", label: "Mapping dependencies" },
];

/** Sentinel returned before any stage has started (queued / connecting). */
export const STAGE_NONE = -1;
/** Index meaning every stage is complete. */
export const STAGE_DONE = STAGES.length;

/**
 * Resolve the index of the currently-active stage from the job status and
 * current stage. `prevIndex` is returned when the stage is unknown/missing
 * while still running, so the stepper holds its last known position rather
 * than snapping backwards.
 */
export function resolveStageIndex(
  status: string | null,
  currentStage: string | null,
  prevIndex: number = STAGE_NONE,
): number {
  if (status === "completed") return STAGE_DONE;

  if (currentStage) {
    const idx = STAGES.findIndex((stage) => stage.key === currentStage);
    if (idx !== STAGE_NONE) return idx;
  }

  // queued, not yet started, or an unknown stage: hold the last known position.
  return prevIndex;
}
