import assert from "node:assert/strict";
import { access, readFile, stat } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the RangeLab EV portfolio experience", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>RangeLab EV \| Bolt telemetry, explained<\/title>/i);
  assert.match(html, /Every kilowatt-hour/);
  assert.match(html, /Four-trip UI fixture/);
  assert.match(html, /Read-only by design/);
  assert.match(html, /Trip intelligence/);
  assert.match(html, /Scenario planner/);
  assert.match(html, /synthetic/i);
  assert.match(
    html,
    /property="og:image" content="http:\/\/localhost(?::3000)?\/og\.png"/i,
  );
  assert.doesNotMatch(html, /Your site is taking shape|Building your site|react-loading-skeleton/i);
  assert.doesNotMatch(html, /fonts\.googleapis\.com/i);
});

test("ships project-owned source and social metadata without starter artifacts", async () => {
  const [page, layout, packageJson, socialCard] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    stat(new URL("../public/og.png", import.meta.url)),
  ]);

  assert.match(page, /RangeLabDashboard/);
  assert.match(layout, /summary_large_image/);
  assert.match(layout, /\/og\.png/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton|drizzle-orm/);
  assert.ok(socialCard.size > 100_000, "social card should be a real generated image");

  await assert.rejects(
    access(new URL("../app/_sites-preview/SkeletonPreview.tsx", import.meta.url)),
  );
  await assert.rejects(
    access(new URL("../app/_sites-preview/preview.css", import.meta.url)),
  );
});
