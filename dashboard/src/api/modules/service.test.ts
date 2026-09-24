import { beforeEach, describe, expect, it, vi } from "vitest";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));

vi.mock("../request", () => ({ request }));

import { serviceApi } from "./service";

describe("serviceApi", () => {
  beforeEach(() => {
    request.mockReset();
  });

  it("uses service-control endpoints rather than update endpoints", () => {
    void serviceApi.getStatus();
    void serviceApi.restart();

    expect(request).toHaveBeenNthCalledWith(1, "/admin/service/status");
    expect(request).toHaveBeenNthCalledWith(2, "/admin/service/restart", {
      method: "POST",
    });
  });
});
