import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const token = process.env.E2E_TOKEN ?? ""; // presence = harness is running
const fixtures = process.env.E2E_FIXTURES ?? "";
const shots = process.env.E2E_SCREENSHOTS;

async function shot(page: Page, name: string) {
  if (shots) await page.screenshot({ path: path.join(shots, `${name}.png`), fullPage: false });
}

test("lawyer reviews an NDA end to end", async ({ page }) => {
  test.skip(!token, "E2E_TOKEN not set — run via scripts/e2e.sh");
  await page.setViewportSize({ width: 1440, height: 900 });

  // Sign in with single sign-on (mock IdP in e2e).
  await page.goto("/matters");
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Work email").fill("wei.ling@lionpartners.test");
  await page.getByRole("button", { name: "Continue with single sign-on" }).click();
  await expect(page).toHaveURL(/\/matters$/);
  await expect(page.getByTestId("whoami")).toContainText("Partner");
  // The browser never holds the bearer token.
  expect(await page.evaluate(() => document.cookie)).not.toContain("travo_session");
  expect(await page.evaluate(() => JSON.stringify(sessionStorage) + JSON.stringify(localStorage))).not.toMatch(/eyJ/);

  // Create a matter with a provider conflict.
  await page.getByRole("button", { name: "New matter" }).click();
  await page.getByLabel("Matter number").fill("LP-2026-014");
  await page.getByLabel("Matter name").fill("Klang Freight — supplier NDA");
  await page.getByLabel("SG").uncheck();
  await page.getByLabel("MY").check();
  await page.getByLabel("Blocked AI providers (conflicts)").fill("openai");
  await page.getByRole("button", { name: "Create matter" }).click();
  await expect(page.getByRole("heading", { name: "Klang Freight — supplier NDA" })).toBeVisible();
  await expect(page.getByText("No openai")).toBeVisible();

  // Upload → classified.
  await page.getByTestId("upload-input").setInputFiles(path.join(fixtures, "my_one_way_nda.docx"));
  await expect(page.getByText("classified")).toBeVisible();
  await expect(page.getByText("MY law")).toBeVisible();
  await shot(page, "01-matter");

  // Start review → canvas.
  await page.getByRole("button", { name: "Start review" }).click();
  await expect(page).toHaveURL(/\/reviews\//);
  const cards = page.getByTestId("finding-card");
  await expect(cards.first()).toBeVisible();
  const redlineBtn = page.getByRole("button", { name: "Export redline (DOCX)" });
  await expect(redlineBtn).toBeDisabled();
  await shot(page, "02-canvas");

  // Sources drawer from a law-note citation.
  await page.getByRole("combobox", { name: "Kind filter" }).selectOption("law");
  await page.getByTestId("citation-chip").first().click();
  const drawer = page.getByTestId("sources-drawer");
  await expect(drawer).toContainText("Test fixture — not real law");
  await shot(page, "03-sources");
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();

  // "Why this model?"
  await cards.first().getByRole("button", { name: "Why this model?" }).click();
  await expect(page.getByTestId("why-model").first()).toContainText("travo-rules-v0");
  await expect(page.getByTestId("why-model").first()).toContainText("matter conflict deny");
  await page.getByRole("combobox", { name: "Kind filter" }).selectOption("all");

  // Edit the liability cap wording.
  const cap = page.locator('[data-rule="liability_cap_floor"]');
  await cap.click();
  await page.keyboard.press("e");
  await cap.getByLabel("Edit wording").fill("Each party's aggregate liability is capped at RM1,000,000.");
  await cap.getByRole("button", { name: "Save" }).click();
  await expect(cap).toHaveAttribute("data-disposition", "edited");

  // Reject one finding with a reason (keyboard).
  const forum = page.locator('[data-rule="forum"]');
  await forum.click();
  await page.keyboard.press("r");
  await forum.getByLabel("Reason for rejecting").selectOption("not_relevant_to_client");
  await forum.getByRole("button", { name: "Reject" }).click();
  await expect(forum).toHaveAttribute("data-disposition", "rejected");

  // Accept + undo.
  const term = page.locator('[data-rule="term_length"]');
  await term.click();
  await page.keyboard.press("a");
  await expect(term).toHaveAttribute("data-disposition", "accepted");
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(term).toHaveAttribute("data-disposition", "");

  // Clear the rest with the keyboard; the gate opens.
  const open = page.locator("[data-testid='finding-card'][data-disposition='']");
  for (let i = 0; i < 30 && (await open.count()) > 0; i++) {
    const before = await open.count();
    await open.first().click();
    await page.keyboard.press("a");
    await expect(open).toHaveCount(before - 1);
  }
  await expect(page.getByText("All issues resolved — ready to export.")).toBeVisible();
  await shot(page, "04-gate-open");

  const download = page.waitForEvent("download");
  await redlineBtn.click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("my_one_way_nda-redline.docx");

  // Document pane shows accepted/edited wording as tracked insertions.
  await expect(page.locator("ins.redline").first()).toBeVisible();
  await expect(page.getByText("capped at RM1,000,000.").first()).toBeVisible();

  // Dark theme renders with the same layout.
  await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
  await page.waitForTimeout(400); // let colour transitions finish before capturing
  await expect(page.getByRole("button", { name: "Export memo (DOCX)" })).toHaveCSS(
    "background-color",
    "rgb(27, 28, 31)",
  );
  await shot(page, "05-dark");
});
