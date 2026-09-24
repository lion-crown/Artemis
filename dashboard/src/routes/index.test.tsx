import { describe, expect, it } from "vitest";
import { routeConfigs } from "./index";

describe("plugin routes", () => {
  it("redirects direct plugin page visits to the experts page", () => {
    for (const path of ["/admin/plugins", "/plugins"]) {
      const route = routeConfigs.find((candidate) => candidate.path === path);
      expect(route).toBeDefined();
      expect((route?.element as React.ReactElement).props).toMatchObject({
        to: "/experts",
      });
    }
  });
});
