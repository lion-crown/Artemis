import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const logoPath = resolve(process.cwd(), "public/artemis-logo.webp");

describe("Artemis brand logo", () => {
  it("ships the supplied WebP logo as the public brand asset", () => {
    expect(existsSync(logoPath)).toBe(true);

    const logo = readFileSync(logoPath);
    expect(logo.subarray(0, 4).toString()).toBe("RIFF");
    expect(logo.subarray(8, 12).toString()).toBe("WEBP");
  });
});
