// ADR-0006 FE-015: scrub 関数の synthetic-PHI fixture テスト。
// 実 PHI は repo に入れない (local-llm-and-phi.md §3)。
//
// init 系の datadogRum.* 呼び出し全体はテストしない (SDK は副作用しかなく、
// applicationId/clientToken 未設定で no-op が返る挙動は init() のロジックに inline)。
// scrub catalog の retain / drop 振る舞いが正しいことを担保する。

import { describe, it, expect } from "vitest";

import { scrubUrl, scrubErrorMessage } from "../datadog-rum";

describe("scrubUrl", () => {
  it("strips patient UUID from path", () => {
    expect(scrubUrl("http://localhost:3000/patients/00000000-0000-0000-0000-000000000001")).toBe(
      "http://localhost:3000/patients/:patientId"
    );
  });

  it("strips numeric MRN-like path segment", () => {
    expect(scrubUrl("http://localhost:3000/patients/12345")).toBe(
      "http://localhost:3000/patients/:patientId"
    );
  });

  it("strips encounter UUID and combines with patient", () => {
    expect(scrubUrl("http://localhost:3000/patients/abc-123/encounters/def-456")).toBe(
      "http://localhost:3000/patients/:patientId/encounters/:encounterId"
    );
  });

  it("strips draft and final identifiers", () => {
    expect(scrubUrl("http://localhost:3000/drafts/xyz789")).toBe(
      "http://localhost:3000/drafts/:draftId"
    );
    expect(scrubUrl("http://localhost:3000/finals/uuid-abc")).toBe(
      "http://localhost:3000/finals/:finalId"
    );
  });

  it("strips query string entirely", () => {
    expect(scrubUrl("http://localhost:3000/patients/12345?q=foo&token=abc")).toBe(
      "http://localhost:3000/patients/:patientId"
    );
  });

  it("strips encounter draft sub-route", () => {
    expect(scrubUrl("http://localhost:3000/encounters/abc-123/draft")).toBe(
      "http://localhost:3000/encounters/:encounterId/draft"
    );
  });

  it("returns non-PHI URL unchanged", () => {
    expect(scrubUrl("http://localhost:3000/patients")).toBe("http://localhost:3000/patients");
    expect(scrubUrl("http://localhost:3000/")).toBe("http://localhost:3000/");
  });
});

describe("scrubErrorMessage", () => {
  it("replaces 4+ digit sequences with ?", () => {
    expect(scrubErrorMessage("Failed to fetch patient 12345")).toBe("Failed to fetch patient ?");
  });

  it("leaves 3-digit numbers (status codes etc.) intact", () => {
    expect(scrubErrorMessage("HTTP 404 not found")).toBe("HTTP 404 not found");
  });

  it("masks multiple numeric segments", () => {
    expect(scrubErrorMessage("encounter 9876 patient 1234")).toBe("encounter ? patient ?");
  });

  it("leaves non-digit text unchanged", () => {
    expect(scrubErrorMessage("Unable to connect to server")).toBe("Unable to connect to server");
  });
});
