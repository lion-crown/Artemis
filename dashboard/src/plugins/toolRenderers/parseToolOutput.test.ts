import { describe, expect, it } from "vitest";
import {
  mergePatchedToolOutput,
  parseArtemisToolOutput,
} from "./parseToolOutput";
import {
  clearToolRenderers,
  getToolRendererVersion,
  registerToolRenderer,
  resolveToolRenderer,
} from "./registry";
import type { ToolRenderProps } from "./types";

function Dummy(_: ToolRenderProps) {
  return null;
}

describe("parseArtemisToolOutput", () => {
  it("parses artemis_ui envelope", () => {
    const raw = JSON.stringify({
      artemis_ui: { renderer: "demo_card", version: 1 },
      data: { count: 2 },
      text: "hi",
    });
    const parsed = parseArtemisToolOutput(raw);
    expect(parsed.isJson).toBe(true);
    expect(parsed.artemisUi).toEqual({ renderer: "demo_card", version: 1 });
    expect(parsed.data).toEqual({ count: 2 });
    expect(parsed.text).toBe("hi");
  });

  it("keeps plain text", () => {
    const parsed = parseArtemisToolOutput("hello");
    expect(parsed.isJson).toBe(false);
    expect(parsed.text).toBe("hello");
  });
});

describe("mergePatchedToolOutput", () => {
  it("merges data into existing envelope", () => {
    const prev = JSON.stringify({
      artemis_ui: { renderer: "demo_card" },
      data: { count: 1 },
      text: "x",
    });
    const next = mergePatchedToolOutput(prev, { count: 3 });
    expect(JSON.parse(next)).toEqual({
      artemis_ui: { renderer: "demo_card" },
      data: { count: 3 },
      text: "x",
    });
  });
});

describe("resolveToolRenderer", () => {
  it("matches by artemis_ui.renderer then tool name", () => {
    clearToolRenderers();
    registerToolRenderer({
      id: "demo_card",
      pluginId: "demo-ui-card",
      tools: ["demo_ui_card"],
      component: Dummy,
    });
    const byHint = resolveToolRenderer({
      toolName: "other",
      pluginId: "demo-ui-card",
      parsed: parseArtemisToolOutput(
        JSON.stringify({ artemis_ui: { renderer: "demo_card" }, data: {} }),
      ),
    });
    expect(byHint?.id).toBe("demo_card");
    const byTool = resolveToolRenderer({
      toolName: "demo_ui_card",
      parsed: parseArtemisToolOutput("plain"),
    });
    expect(byTool?.id).toBe("demo_card");
    clearToolRenderers();
  });

  it("bumps version on register so subscribers can refresh", () => {
    clearToolRenderers();
    const before = getToolRendererVersion();
    registerToolRenderer({
      id: "x",
      pluginId: "p",
      component: Dummy,
    });
    expect(getToolRendererVersion()).toBeGreaterThan(before);
    clearToolRenderers();
  });
});
