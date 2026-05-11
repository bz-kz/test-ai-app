import { describe, it, expect } from "vitest";
import {
  LLM_MODEL,
  LATENCY_SPINNER_MS,
  LATENCY_SKELETON_MS,
  LATENCY_HINT_MS,
  LATENCY_CANCEL_MS,
} from "../constants";

describe("constants", () => {
  it("LLM_MODEL は gemma4:e4b に固定されている", () => {
    expect(LLM_MODEL).toBe("gemma4:e4b");
  });

  it("レイテンシ閾値が SPEC の順序に従っている", () => {
    expect(LATENCY_SPINNER_MS).toBeLessThan(LATENCY_SKELETON_MS);
    expect(LATENCY_SKELETON_MS).toBeLessThan(LATENCY_HINT_MS);
    expect(LATENCY_HINT_MS).toBeLessThan(LATENCY_CANCEL_MS);
  });
});
