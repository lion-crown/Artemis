import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../../api/modules/skillHubSkillsets", () => ({
  skillHubSkillsetsApi: {
    list: vi.fn(),
  },
}));

vi.mock("../../api/modules/skillPackages", () => ({
  skillPackagesApi: {
    fromSkillHub: vi.fn(),
  },
}));

import { skillHubSkillsetsApi } from "../../api/modules/skillHubSkillsets";
import { skillPackagesApi } from "../../api/modules/skillPackages";
import { SkillsetFromHubDrawer } from "./SkillsetFromHubDrawer";

const createdPackage = {
  id: "pkg-1",
  name: "Writing",
  description: "Writing skills",
  created_by: "1",
  skill_count: 2,
  created_at: "2026-07-30T00:00:00Z",
  updated_at: "2026-07-30T00:00:00Z",
  skills: [],
};

const skillsetsApi = vi.mocked(skillHubSkillsetsApi, true);
const packagesApi = vi.mocked(skillPackagesApi, true);
const getComputedStyle = window.getComputedStyle;

beforeAll(() => {
  vi.spyOn(window, "getComputedStyle").mockImplementation((element) =>
    getComputedStyle(element),
  );
});

afterAll(() => {
  vi.restoreAllMocks();
});

describe("<SkillsetFromHubDrawer />", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    skillsetsApi.list.mockResolvedValue({
      items: [
        {
          slug: "writing",
          display_name: "写作",
          display_name_en: "Writing",
          summary: "写作技能",
          summary_en: "Writing skills",
          skill_count: 2,
        },
      ],
      scenes: [],
    });
  });

  it("loads market skillsets and imports a selected one", async () => {
    const user = userEvent.setup();
    const onCreated = vi.fn();
    packagesApi.fromSkillHub.mockResolvedValue(createdPackage);

    render(
      <SkillsetFromHubDrawer open onClose={vi.fn()} onCreated={onCreated} />,
    );

    expect(skillsetsApi.list).toHaveBeenCalledWith();
    await screen.findByText("写作");

    const importButton = screen.getByRole("button", {
      name: "skillPackages.addAsPackage",
    });
    expect(importButton).toBeEnabled();
    await user.click(importButton);

    await waitFor(() => {
      expect(packagesApi.fromSkillHub).toHaveBeenCalledWith({
        slug: "writing",
      });
      expect(onCreated).toHaveBeenCalledWith(createdPackage);
    });
  });
});
