import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import en from "./en.json";
import zh from "./zh.json";
import { describe, expect, it } from "vitest";

describe("application brand title", () => {
  it("uses Artemis in every supported locale", () => {
    expect(zh.app.pageTitle).toBe("Artemis - 循月而行，智见无界");
    expect(en.app.pageTitle).toBe(
      "Artemis - Guided by moonlight, insight without bounds",
    );
  });

  it("uses Artemis in the browser shell and PWA manifest", () => {
    const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
    const html = readFileSync(join(root, "index.html"), "utf8");
    const manifest = readFileSync(join(root, "public/manifest.json"), "utf8");

    expect(html).toContain("<title>Artemis</title>");
    expect(html).toContain('href="/artemis-icon.png"');
    expect(html).not.toContain("/logo.svg");
    expect(html).not.toContain("logo_name.png");
    expect(html).not.toContain("logo_name_dark.png");
    expect(manifest).toContain('"name": "Artemis"');
    expect(manifest).toContain('"short_name": "Artemis"');
  });

  it("uses the Artemis logo in every expanded brand surface", () => {
    const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
    const html = readFileSync(join(root, "index.html"), "utf8");
    const header = readFileSync(join(root, "src/layouts/Header.tsx"), "utf8");
    const sidebar = readFileSync(join(root, "src/layouts/Sidebar.tsx"), "utf8");

    expect(html).toContain('src="/artemis-logo.webp"');
    expect(header).toContain('src="/artemis-logo.webp"');
    expect(sidebar).toContain('src="/artemis-logo.webp"');
  });
});
