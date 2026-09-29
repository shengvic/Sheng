import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const running = !!process.env.E2E_TOKEN;
const shots = process.env.E2E_SCREENSHOTS;

async function shot(page: Page, name: string) {
  if (shots) await page.screenshot({ path: path.join(shots, `${name}.png`) });
}

function watchCsp(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error" && /Content Security Policy|Refused to/.test(m.text())) errors.push(m.text());
  });
  return errors;
}

async function sso(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Work email").fill(email);
  await page.getByRole("button", { name: "Continue with single sign-on" }).click();
  await expect(page).toHaveURL(/\/matters$/);
}

test.beforeEach(() => test.skip(!running, "run via scripts/e2e.sh"));

test("pages carry a nonce-based CSP and unknown domains get a clear error", async ({ page }) => {
  const res = await page.goto("/login");
  const csp = res?.headers()["content-security-policy"] ?? "";
  expect(csp).toMatch(/script-src 'self' 'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
  expect(csp).toContain("frame-ancestors 'none'");
  await page.getByLabel("Work email").fill("someone@unknown-firm.test");
  await page.getByRole("button", { name: "Continue with single sign-on" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "not set up for this email domain" })).toBeVisible();
  await shot(page, "10-login");
  // Unauthenticated API calls are refused by the BFF.
  expect((await page.request.get("/api/v1/me")).status()).toBe(401);
});

test("admin signs in with SSO and manages policy, keys, spend, audit and sessions", async ({ page }) => {
  const cspErrors = watchCsp(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await sso(page, "admin@lionpartners.test");
  await page.getByRole("link", { name: "Admin" }).click();
  await expect(page.getByRole("heading", { name: "Admin" })).toBeVisible();

  // Model policy: deny OpenAI firm-wide, then test it.
  const editor = page.getByLabel("Model policy YAML");
  await expect(editor).toHaveValue(/deny: \[\]/);
  await editor.fill((await editor.inputValue()).replace("deny: []", "deny: [openai]"));
  await page.getByRole("button", { name: "Save as new version" }).click();
  await expect(page.getByText("Firm policy v1")).toBeVisible();
  await page.getByLabel("Task").selectOption("law_check");
  await page.getByLabel("Escalated (needs a stronger model)").check();
  await page.getByRole("button", { name: "Run test" }).click();
  const result = page.getByTestId("dry-run-result");
  await expect(result).toContainText("openai-byo-frontier");
  await expect(result).toContainText("tenant provider denied");
  await shot(page, "11-admin-policy");

  // Invalid YAML is rejected by the server and the saved version is unchanged.
  await editor.fill("providers: {allow: 3}");
  await page.getByRole("button", { name: "Save as new version" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "invalid policy" })).toBeVisible();
  await page.getByRole("button", { name: "Discard changes" }).click();

  // API keys: add, then revoke.
  await page.getByRole("tab", { name: "API keys" }).click();
  await page.getByLabel("Provider").selectOption("anthropic");
  await page.getByLabel("API key").fill("sk-ant-e2e-12345678");
  await page.getByRole("button", { name: "Save key" }).click();
  const row = page.getByTestId("key-anthropic");
  await expect(row).toContainText("•••• 5678");
  await expect(page.locator("body")).not.toContainText("sk-ant-e2e");
  page.once("dialog", (d) => d.accept());
  await row.getByRole("button", { name: "Revoke" }).click();
  await expect(row).toContainText("revoked");

  // Spend and audit render.
  await page.getByRole("tab", { name: "Spend" }).click();
  await expect(page.getByTestId("spend")).toContainText("Model spend");
  await shot(page, "12-admin-spend");
  await page.getByRole("tab", { name: "Audit log" }).click();
  await page.getByLabel("Filter by action").fill("model_policy.updated");
  await expect(page.getByTestId("audit-table")).toContainText("model_policy.updated");

  // Sessions: the admin's own SSO session is listed; revoking it signs them out.
  await page.getByRole("tab", { name: "Sign-in (SSO)" }).click();
  await expect(page.getByLabel("Issuer URL")).toHaveValue(/localhost/);
  const sessions = page.getByTestId("sessions-table");
  await expect(sessions).toContainText("admin@lionpartners.test");
  await shot(page, "13-admin-sso");
  await sessions.getByRole("row", { name: /you/ }).getByRole("button", { name: "Revoke" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/matters");
  await expect(page).toHaveURL(/\/login/);

  expect(cspErrors).toEqual([]);
});

test("partner sees no admin console; sign-out ends the session", async ({ page }) => {
  await sso(page, "wei.ling@lionpartners.test");
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
  await page.goto("/admin");
  await expect(page.getByRole("alert").filter({ hasText: "for firm administrators" })).toBeVisible();
  expect((await page.request.get("/api/v1/admin/audit")).status()).toBe(403);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  expect((await page.request.get("/api/v1/me")).status()).toBe(401);
});

test("writes without the CSRF header are refused", async ({ page }) => {
  await sso(page, "wei.ling@lionpartners.test");
  const r = await page.request.post("/api/v1/matters", {
    data: { number: "X-1", name: "x", jurisdictions: [] },
    headers: { origin: "http://localhost:3790" },
  });
  expect(r.status()).toBe(403);
});

test("development token sign-in still works when enabled", async ({ page }) => {
  await page.goto("/login");
  await page.getByText("Development sign-in").click();
  await page.getByLabel("Access token").fill(process.env.E2E_TOKEN ?? "");
  await page.getByRole("button", { name: "Sign in with token" }).click();
  await expect(page).toHaveURL(/\/matters$/);
  await expect(page.getByTestId("whoami")).toContainText("Partner");
});
