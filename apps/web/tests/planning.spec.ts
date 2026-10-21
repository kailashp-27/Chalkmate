import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
const root = resolve(process.cwd(), "../..");
const env = Object.fromEntries(
  readFileSync(resolve(root, ".env"), "utf8")
    .split(/\r?\n/)
    .filter((l) => l.includes("=") && !l.startsWith("#"))
    .map((l) => {
      const i = l.indexOf("=");
      return [l.slice(0, i), l.slice(i + 1)];
    }),
);
const createdIds: string[] = [];
test.afterAll(() => {
  for (const id of createdIds)
    execFileSync(
      resolve(
        root,
        process.platform === "win32"
          ? ".venv/Scripts/python.exe"
          : ".venv/bin/python",
      ),
      ["scripts/cleanup_e2e.py", id],
      { cwd: root },
    );
});

test("planning approval, private export, help and command navigation", async ({
  page,
  request,
}) => {
  test.setTimeout(240000);
  const email = `e2e-${randomUUID()}@example.com`,
    password = `Test-${randomUUID()}!`;
  const user = await request.post(`${env.SUPABASE_URL}/auth/v1/admin/users`, {
    headers: {
      apikey: env.SUPABASE_SERVICE_ROLE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
    },
    data: { email, password, email_confirm: true },
  });
  expect(user.ok()).toBeTruthy();
  createdIds.push((await user.json()).id);
  const login = await request.post(
    `${env.SUPABASE_URL}/auth/v1/token?grant_type=password`,
    { headers: { apikey: env.SUPABASE_ANON_KEY }, data: { email, password } },
  );
  const token = (await login.json()).access_token;
  async function call(path: string, data: unknown) {
    const r = await request.post(`http://127.0.0.1:8100/v1${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      data,
    });
    expect(r.ok(), await r.text()).toBeTruthy();
    return r.json();
  }
  const workspace = await call("/workspaces", {
    name: "Planning browser test",
  });
  await call(`/workspaces/${workspace.id}/classrooms`, {
    name: "Planning classroom",
    subject: "Data structures",
    term: "2026",
  });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Planning", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Planning studio" }),
  ).toBeVisible();
  const help = page.getByRole("button", {
    name: "About planning",
    exact: true,
  });
  await help.focus();
  await expect(page.getByRole("tooltip")).toContainText(
    "Start with a syllabus",
  );
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tooltip")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Syllabus Topics & coverage" })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Title", { exact: true }).fill("Browser syllabus");
  await dialog.getByLabel("Topic 1", { exact: true }).fill("Stacks");
  await dialog
    .getByLabel("Coverage", { exact: true })
    .fill(
      "A stack uses LIFO ordering. Push adds items; pop removes the latest item.",
    );
  await dialog.getByRole("button", { name: "Save draft", exact: true }).click();
  await page.getByRole("button", { name: /Browser syllabus/ }).click();
  await dialog
    .getByRole("button", { name: "Approve version", exact: true })
    .click();
  await expect(
    dialog.getByText("v1 · Approved", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await page
    .getByRole("button", { name: "Question paper Draft, check, refine" })
    .click();
  await dialog.getByLabel("Title", { exact: true }).fill("Browser paper");
  await dialog.getByRole("checkbox", { name: /Browser syllabus/ }).check();
  await dialog.getByLabel("Total marks", { exact: true }).fill("5");
  await dialog.getByLabel("Topic", { exact: true }).fill("Stacks");
  await dialog.getByLabel("Marks", { exact: true }).fill("5");
  await dialog
    .getByLabel("Question", { exact: true })
    .fill("Describe the removal order used by a stack.");
  await dialog
    .getByLabel("Teacher answer", { exact: true })
    .fill("PRIVATE-KEY: LIFO, last item first.");
  await dialog
    .getByLabel("Marking guide", { exact: true })
    .fill("Five marks for accurate explanation and example.");
  await dialog.getByLabel("Source", { exact: true }).selectOption("S1");
  await dialog
    .getByLabel("Exact quote", { exact: true })
    .fill("A stack uses LIFO ordering.");
  await dialog.getByRole("button", { name: "Save draft", exact: true }).click();
  await page.getByRole("button", { name: /Browser paper/ }).click();
  await expect(
    dialog.getByRole("button", { name: "Approve version", exact: true }),
  ).toBeEnabled();
  const downloadPromise = page.waitForEvent("download");
  await dialog
    .getByRole("button", { name: "Student copy", exact: true })
    .click();
  const download = await downloadPromise;
  const file = await download.path();
  expect(readFileSync(file!, "utf8")).not.toContain("PRIVATE-KEY");
  await dialog
    .getByRole("button", { name: "Approve version", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "Create variant", exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await page.keyboard.press("Control+k");
  await dialog.getByLabel("Find a workflow").fill("send assignment below 25");
  await dialog.getByRole("button", { name: "Find", exact: true }).click();
  await expect(
    dialog.getByText("Review required", { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Open", exact: true }),
  ).toHaveCount(0);
  await dialog
    .getByRole("button", { name: "Pilot readiness", exact: true })
    .click();
  await dialog.getByRole("button", { name: "Open", exact: true }).click();
  await expect(
    page.getByText(
      "Teacher pilot pending consented samples and measured review time.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Planning", exact: true }).click();
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(
    await page
      .locator(".planning-studio")
      .evaluate((el) => getComputedStyle(el).animationName),
  ).toBe("none");
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("button", { name: "About planning", exact: true })
    .click();
  const helpBounds = await page.getByRole("tooltip").boundingBox();
  expect(helpBounds!.x).toBeGreaterThanOrEqual(0);
  expect(helpBounds!.x + helpBounds!.width).toBeLessThanOrEqual(390);
  await page.keyboard.press("Escape");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: resolve(root, ".tmp/phase-six-planning-mobile.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: resolve(root, ".tmp/phase-six-planning-dark.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("radio", { name: "Light", exact: true }).check();
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await page.screenshot({
    path: resolve(root, ".tmp/phase-six-planning-light.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
