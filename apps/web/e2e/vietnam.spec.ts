import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const token = process.env.E2E_TOKEN ?? ""; // presence = harness is running
const vnDocx = process.env.E2E_VN_DOCX ?? "";
const shots = process.env.E2E_SCREENSHOTS;

async function shot(page: Page, name: string) {
  if (shots) await page.screenshot({ path: path.join(shots, `${name}.png`), fullPage: false });
}

test("Vietnamese UI: bilingual contract review and export", async ({ page }) => {
  test.skip(!token || !vnDocx, "run via scripts/e2e.sh");
  await page.setViewportSize({ width: 1440, height: 900 });

  await page.goto("/login");
  await page.getByRole("button", { name: "VI" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "vi");
  await page.getByLabel("Email công việc").fill("wei.ling@lionpartners.test");
  await page.getByRole("button", { name: "Tiếp tục với đăng nhập một lần (SSO)" }).click();
  await expect(page).toHaveURL(/\/matters$/);
  await expect(page.getByRole("heading", { name: "Vụ việc" })).toBeVisible();

  await page.getByRole("button", { name: "Vụ việc mới" }).click();
  await page.getByLabel("Số vụ việc").fill("VN-2026-001");
  await page.getByLabel("Tên vụ việc").fill("Sông Hồng — thỏa thuận bảo mật");
  await page.getByLabel("SG").uncheck();
  await page.getByLabel("VN").check();
  await page.getByRole("button", { name: "Tạo vụ việc" }).click();
  await expect(page.getByRole("heading", { name: "Sông Hồng — thỏa thuận bảo mật" })).toBeVisible();

  await page.getByTestId("upload-input").setInputFiles(vnDocx);
  await expect(page.getByText("đã phân loại")).toBeVisible();
  await expect(page.getByTestId("bilingual-layout")).toHaveText("Bảng Việt | Anh");
  await expect(page.getByText("Pháp luật VN").first()).toBeVisible();
  await shot(page, "vn-01-matter");

  await page.getByRole("button", { name: "Bắt đầu rà soát" }).click();
  await expect(page).toHaveURL(/\/reviews\//);
  const cards = page.getByTestId("finding-card");
  await expect(cards.first()).toBeVisible();
  await expect(page.getByTestId("bilingual-clause").first()).toBeVisible();
  await expect(page.getByText("Tóm tắt.", { exact: false }).first()).toBeVisible();
  await shot(page, "vn-02-canvas");

  // VI/EN discrepancies with both language versions and the prevailing language.
  await page.getByRole("combobox", { name: "Lọc theo loại" }).selectOption("bilingual");
  const duration = page.locator('[data-rule="bilingual:duration"]');
  await expect(duration).toContainText("Thời hạn khác nhau");
  await expect(duration.getByTestId("bilingual-evidence")).toBeVisible();
  const figures = page.locator('[data-rule="bilingual:figure_words"]');
  await expect(figures).toContainText("200.000.000");
  await shot(page, "vn-03-bilingual");
  await page.getByRole("combobox", { name: "Lọc theo loại" }).selectOption("all");

  // Resolve every open finding with the keyboard, then export.
  const exportRedline = page.getByRole("button", { name: "Xuất bản sửa đổi (DOCX)" });
  for (let i = 0; i < 80 && !(await exportRedline.isEnabled()); i++) {
    await page.keyboard.press("a");
    await page.waitForTimeout(150);
  }
  await expect(exportRedline).toBeEnabled();
  await expect(page.getByText("Đã xử lý mọi vấn đề — có thể xuất.")).toBeVisible();
  const download = page.waitForEvent("download");
  await exportRedline.click();
  expect((await download).suggestedFilename()).toMatch(/\.docx$/);
  await shot(page, "vn-04-exported");
});
