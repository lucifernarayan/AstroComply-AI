import { expect, test } from "@playwright/test";

const apiBase = process.env.ASTROCOMPLY_E2E_API ?? "http://127.0.0.1:8000";
const tle = `1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991\n2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482\n`;

function kvn(id: string, distance = 840) {
  return `CCSDS_CDM_VERS = 1.0\nCREATION_DATE = 2026-11-27T00:00:00Z\nORIGINATOR = E2E\nMESSAGE_ID = ${id}\nTCA = 2026-12-01T12:00:00Z\nMISS_DISTANCE = ${distance}\nRELATIVE_SPEED = 12000\nOBJECT = OBJECT1\nOBJECT_DESIGNATOR = 25544\nOBJECT = OBJECT2\nOBJECT_DESIGNATOR = 901\n`;
}

function xml(id: string) {
  return `<?xml version="1.0"?><cdm version="1.0"><header><CREATION_DATE>2026-11-27T00:00:00Z</CREATION_DATE><ORIGINATOR>E2E</ORIGINATOR><MESSAGE_ID>${id}</MESSAGE_ID></header><body><relativeMetadataData><TCA>2026-12-01T12:00:00Z</TCA><MISS_DISTANCE units="m">730</MISS_DISTANCE><RELATIVE_SPEED units="m/s">12000</RELATIVE_SPEED></relativeMetadataData><segment><metadata><OBJECT>OBJECT1</OBJECT><OBJECT_DESIGNATOR>25544</OBJECT_DESIGNATOR></metadata><data><covarianceMatrix><CR_R>1.5</CR_R></covarianceMatrix></data></segment><segment><metadata><OBJECT>OBJECT2</OBJECT><OBJECT_DESIGNATOR>902</OBJECT_DESIGNATOR></metadata><data><covarianceMatrix><CR_R>2.5</CR_R></covarianceMatrix></data></segment></body></cdm>`;
}

test("operator journey, source versions, reports and tenant isolation", async ({ page, request }) => {
  const marker = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const email = `e2e-${marker}@example.com`;
  const password = `E2E-test-password-${marker}`;
  const eventId = `KVN-${marker}`;
  const xmlId = `XML-${marker}`;
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Create account" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("astrocomply_session"));
  expect(token).toBeTruthy();
  const auth = { Authorization: `Bearer ${token}` };
  const orgs = await (await request.get(`${apiBase}/organizations`, { headers: auth })).json();
  let orgId: number = orgs[0]?.id;
  if (!orgId) {
    await page.getByLabel("New organization").fill(`E2E ${marker}`);
    await page.getByRole("button", { name: "Create organization" }).click();
    await expect(page.getByRole("heading", { name: "Fleet assets" })).toBeVisible();
    const created = await (await request.get(`${apiBase}/organizations`, { headers: auth })).json();
    orgId = created[0].id;
  }
  await expect(page.getByRole("heading", { name: "Fleet assets" })).toBeVisible();
  await page.getByLabel("Asset name").fill(`ISS ${marker}`);
  await page.getByRole("button", { name: "Add asset" }).click();
  await expect(page.getByText(`ISS ${marker}`).first()).toBeVisible();
  await page.getByText("No current uploaded TLEs to plot.").waitFor();
  await page.getByLabel("Element source").fill("E2E fixture");
  await page.getByLabel("TLE file").setInputFiles({ name: "iss.tle", mimeType: "text/plain", buffer: Buffer.from(tle) });
  await page.getByLabel("Position time (local)").fill("2019-12-09T22:08");
  await page.getByRole("button", { name: "Refresh positions" }).click();
  await expect(page.getByText(/ISS .* · propagated/)).toBeVisible();
  await expect(page.getByText(/E2E fixture · epoch/)).toBeVisible();
  const positions = await (await request.get(`${apiBase}/organizations/${orgId}/orbital/positions?at=2019-12-09T16:38:00Z`, { headers: auth })).json();
  expect(positions.positions.some((item: { status: string; source: string }) => item.status === "propagated" && item.source === "E2E fixture")).toBeTruthy();
  await page.getByLabel("Position time (local)").fill("2026-11-27T12:00");
  await page.getByRole("button", { name: "Refresh positions" }).click();
  await expect(page.getByText(/ISS .* · stale/)).toBeVisible();
  await page.getByLabel("TLE file").setInputFiles({ name: "invalid.tle", mimeType: "text/plain", buffer: Buffer.from("not a TLE") });
  await expect(page.getByText("Expected a two-line element set")).toBeVisible();

  const cdmInput = page.getByLabel("Upload a CCSDS CDM KVN or XML file");
  await cdmInput.setInputFiles({ name: "invalid.kvn", mimeType: "text/plain", buffer: Buffer.from("BAD = 1\n") });
  await expect(page.getByText(/Missing required CCSDS_CDM_VERS/)).toBeVisible();
  await cdmInput.setInputFiles({ name: "event.kvn", mimeType: "text/plain", buffer: Buffer.from(kvn(eventId)) });
  await expect(page.getByText(eventId).first()).toBeVisible();
  await cdmInput.setInputFiles({ name: "event.kvn", mimeType: "text/plain", buffer: Buffer.from(kvn(eventId)) });
  await expect(page.getByText("CDM already imported")).toBeVisible();
  await cdmInput.setInputFiles({ name: "event-update.kvn", mimeType: "text/plain", buffer: Buffer.from(kvn(eventId, 750)) });
  await cdmInput.setInputFiles({ name: "event.xml", mimeType: "application/xml", buffer: Buffer.from(xml(xmlId)) });
  await expect(page.getByText(xmlId).first()).toBeVisible();
  const row = page.locator("li").filter({ hasText: eventId }).first();
  await row.getByRole("button", { name: "View details" }).click();
  await expect(page.getByRole("heading", { name: `Event evidence · ${eventId}` })).toBeVisible();
  await expect(page.getByText("Version 2", { exact: false })).toBeVisible();
  const sourceDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download original CDM" }).first().click();
  expect((await sourceDownload).suggestedFilename()).toContain("cdm-");
  await row.getByRole("button", { name: "Investigate" }).click();
  const refresh = page.getByRole("button", { name: "Refresh status" });
  await expect(refresh).toBeVisible();
  for (let attempt = 0; attempt < 30; attempt++) {
    await refresh.click();
    if (await page.getByText("succeeded", { exact: true }).count()) break;
    await page.waitForTimeout(500);
  }
  await expect(page.getByText("succeeded", { exact: true })).toBeVisible();
  await expect(page.getByText(/"source": "E2E"/)).toBeVisible();
  for (const button of ["Fleet PDF", "Event PDF", "Export fleet CSV", "Export events CSV"]) {
    const download = page.waitForEvent("download");
    await (button === "Event PDF" ? row.getByRole("button", { name: button }) : page.getByRole("button", { name: button })).click();
    expect((await download).suggestedFilename()).toMatch(/\.(pdf|csv)$/);
  }
  await page.getByLabel("Question").fill("Check fleet element freshness");
  await page.getByRole("button", { name: "Queue workflow" }).click();
  await page.getByRole("button", { name: /Check fleet element freshness ·/ }).click();
  await expect(refresh).toBeVisible();
  for (let attempt = 0; attempt < 30; attempt++) {
    await refresh.click();
    if (await page.getByText(/Fleet has .* asset/).count()) break;
    await page.waitForTimeout(500);
  }
  await expect(page.getByText(/Fleet has .* asset/)).toBeVisible();
  const other = await request.post(`${apiBase}/organizations`, { headers: auth, data: { name: `Other ${marker}` } });
  expect(other.status()).toBe(201);
  const otherOrg = (await other.json()).id;
  const events = await (await request.get(`${apiBase}/organizations/${orgId}/events`, { headers: auth })).json();
  const primary = events.find((item: { external_id: string }) => item.external_id === eventId);
  expect((await request.get(`${apiBase}/organizations/${otherOrg}/events/${primary.id}`, { headers: auth })).status()).toBe(404);
  expect((await request.get(`${apiBase}/organizations/${otherOrg}/reports/events/${primary.id}.pdf`, { headers: auth })).status()).toBe(404);
  await page.evaluate(() => sessionStorage.setItem("astrocomply_session", "expired.invalid.token"));
  await page.reload();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Fleet assets" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
});
