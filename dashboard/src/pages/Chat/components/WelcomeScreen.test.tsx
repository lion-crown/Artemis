import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import WelcomeScreen from "./WelcomeScreen";

describe("WelcomeScreen", () => {
  it("uses the Artemis Logo as the replayable welcome animation", () => {
    render(<WelcomeScreen onPromptClick={() => undefined} quickCards={[]} />);

    expect(
      screen.getByRole("button", { name: "Artemis logo" }),
    ).toHaveAttribute("src", "/artemis-logo.webp");
  });
});
