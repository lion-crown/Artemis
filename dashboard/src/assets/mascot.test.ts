import { describe, expect, it } from "vitest";
import { ARTEMIS_LOGO_SRC, ARTEMIS_EMPTY_MASCOT_SRC } from "./mascot";

describe("mascot source", () => {
  it("uses ARTEMIS_LOGO_SRC as the active Artemis mascot source", () => {
    expect(ARTEMIS_LOGO_SRC).toBe("/artemis-logo.webp");
    expect(ARTEMIS_EMPTY_MASCOT_SRC).toBe(ARTEMIS_LOGO_SRC);
  });
});
