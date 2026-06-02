import { describe, expect, it } from "vitest";

import {
  STAGES,
  STAGE_DONE,
  STAGE_NONE,
  resolveStageIndex,
} from "@/lib/indexing-stages";

describe("resolveStageIndex", () => {
  it("returns STAGE_NONE while queued with no stage", () => {
    expect(resolveStageIndex("queued", null)).toBe(STAGE_NONE);
  });

  it("returns STAGE_NONE for the initial connecting state", () => {
    expect(resolveStageIndex(null, null)).toBe(STAGE_NONE);
  });

  it("maps the first stage to index 0", () => {
    expect(resolveStageIndex("running", "cloning")).toBe(0);
  });

  it("maps each known stage to its position", () => {
    STAGES.forEach((stage, index) => {
      expect(resolveStageIndex("running", stage.key)).toBe(index);
    });
  });

  it("maps the final pipeline stage", () => {
    expect(resolveStageIndex("running", "building_graph")).toBe(
      STAGES.length - 1,
    );
  });

  it("returns STAGE_DONE when completed", () => {
    expect(resolveStageIndex("completed", null)).toBe(STAGE_DONE);
    expect(STAGE_DONE).toBe(STAGES.length);
  });

  it("holds the last known index for an unknown stage while running", () => {
    expect(resolveStageIndex("running", "mystery_stage", 2)).toBe(2);
  });

  it("holds the last known index when running with no stage", () => {
    expect(resolveStageIndex("running", null, 3)).toBe(3);
  });
});
