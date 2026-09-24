import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ThinkingBubble from "./ThinkingBubble";

describe("ThinkingBubble", () => {
  it("renders the EY Logo outside the legacy circular avatar shell", () => {
    const { container } = render(<ThinkingBubble startedAt={Date.now()} />);
    const logo = container.querySelector('img[src="/artemis-logo.webp"]');

    expect(logo?.parentElement?.className).not.toContain("botAvatar");
  });
});
