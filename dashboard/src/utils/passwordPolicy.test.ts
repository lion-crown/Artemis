import { describe, expect, it } from "vitest";

import { passwordPolicyIssue } from "./passwordPolicy";

describe("passwordPolicyIssue", () => {
  it("rejects the Artemis-branded common password", () => {
    expect(passwordPolicyIssue("Artemis123")).toBe("too_common");
  });
});
