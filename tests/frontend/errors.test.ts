import { describe, expect, it } from "vitest";

import { getErrorMessage, parseApiErrorBody } from "../../frontend/src/utils/errors";

describe("getErrorMessage", () => {
  it("reads Error.message", () => {
    expect(getErrorMessage(new Error("boom"), "fallback")).toBe("boom");
  });

  it("uses fallback for non-errors", () => {
    expect(getErrorMessage(null, "fallback")).toBe("fallback");
  });
});

describe("parseApiErrorBody", () => {
  it("parses standardized API errors", () => {
    const parsed = parseApiErrorBody(
      JSON.stringify({ error: { code: "VALIDATION_ERROR", message: "topic required" } })
    );
    expect(parsed?.error.code).toBe("VALIDATION_ERROR");
  });

  it("returns null for non-json", () => {
    expect(parseApiErrorBody("plain text")).toBeNull();
  });
});
