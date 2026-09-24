import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(import.meta.dirname, "../..");
const dashboardOutput = resolve(repositoryRoot, "src/artemis/dashboard");

function textFilesUnder(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) return textFilesUnder(path);
    return /\.(?:css|html|js|json|mjs)$/.test(entry.name)
      ? [readFileSync(path, "utf8")]
      : [];
  });
}

describe("Artemis browser contracts", () => {
  it("uses Artemis storage and plugin envelope names in source and built assets", () => {
    const customMcpSource = readFileSync(
      resolve(import.meta.dirname, "pages/Agent/Connectors/customMcpUtils.ts"),
      "utf8",
    );
    const toolOutputSource = readFileSync(
      resolve(import.meta.dirname, "plugins/toolRenderers/parseToolOutput.ts"),
      "utf8",
    );
    const builtOutput = textFilesUnder(dashboardOutput).join("\n");

    expect(customMcpSource).toContain("artemis.customMcp.probeOnSave");
    expect(toolOutputSource).toContain("artemis_ui");
    expect(builtOutput).toContain("artemis_ui");
    expect(builtOutput).toContain("artemis.customMcp.probeOnSave");
    expect(builtOutput).not.toMatch(/\boctop(?:_|:|bot|[./-])/i);
  });
});
