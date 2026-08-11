import assert from "node:assert/strict";
import test from "node:test";

import { isSameOriginRequest } from "./same-origin";

test("same-origin check accepts the dashboard and rejects missing or foreign origins", () => {
  assert.equal(
    isSameOriginRequest(
      new Request("http://localhost:3000/api/x", {
        headers: { host: "localhost:3000", origin: "http://localhost:3000" },
      }),
    ),
    true,
  );
  assert.equal(
    isSameOriginRequest(new Request("http://localhost:3000/api/x")),
    false,
  );
  assert.equal(
    isSameOriginRequest(
      new Request("http://localhost:3000/api/x", {
        headers: { host: "localhost:3000", origin: "https://evil.example" },
      }),
    ),
    false,
  );
});

test("same-origin check honors reverse-proxy host and protocol", () => {
  const request = new Request("http://dashboard:3000/api/x", {
    headers: {
      origin: "https://signal.example",
      "x-forwarded-host": "signal.example",
      "x-forwarded-proto": "https",
    },
  });
  assert.equal(isSameOriginRequest(request), true);
});
