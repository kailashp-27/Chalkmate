import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";

const root = resolve(process.cwd(), "../..");
const env = Object.fromEntries(
  readFileSync(resolve(root, ".env"), "utf8")
    .split(/\r?\n/)
    .filter((line) => line.includes("=") && !line.startsWith("#"))
    .map((line) => {
      const at = line.indexOf("=");
      return [line.slice(0, at), line.slice(at + 1)];
    }),
);
let accountId = "";

test.afterAll(() => {
  if (accountId)
    execFileSync(
      resolve(
        root,
        process.platform === "win32"
          ? ".venv/Scripts/python.exe"
          : ".venv/bin/python",
      ),
      ["scripts/cleanup_e2e.py", accountId],
      { cwd: root },
    );
});

test("teacher completes classroom setup, question review, rubric revision, and replacement release", async ({
  page,
  request,
}) => {
  // This journey spans all three phases; individual UI actions still time out in 15s.
  test.setTimeout(300_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const email = `e2e-${randomUUID()}@example.com`;
  const password = `Test-${randomUUID()}!`;
  const created = await request.post(
    `${env.SUPABASE_URL}/auth/v1/admin/users`,
    {
      headers: {
        apikey: env.SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
      },
      data: { email, password, email_confirm: true },
    },
  );
  expect(created.ok()).toBeTruthy();
  accountId = (await created.json()).id;
  await page.goto("/");
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "A home for your teaching." }),
  ).toBeVisible();
  await page.getByLabel("Workspace name").fill("Teaching workspace");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await page
    .getByRole("button", { name: "New classroom", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Classroom name")
    .fill("Computer Science · Section A");
  await dialog.getByLabel("Subject", { exact: true }).fill("Data Structures");
  await dialog.getByLabel("Academic term").fill("Fall 2026");
  await dialog
    .getByRole("button", { name: "Create classroom", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await page
    .getByRole("button", { name: "Import students", exact: true })
    .click();
  await dialog.getByLabel("Choose a roster").setInputFiles({
    name: "roster.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "registration_number,name,email\nCS001,Ada Lovelace,ada@example.com\nCS002,Alan Turing,invalid\nCS003,Grace Hopper,grace@example.com",
    ),
  });
  await dialog.getByRole("button", { name: "Preview roster" }).click();
  await expect(dialog.getByText("3 student rows")).toBeVisible();
  await expect(dialog.getByText(/0 errors · 1 warnings/)).toBeVisible();
  await dialog.getByRole("button", { name: /Confirm import/ }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByRole("cell", { name: "Ada Lovelace" })).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "No email", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(root, ".tmp/classroom-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Files", exact: true }).click();
  await page.getByLabel("Upload file").setInputFiles({
    name: "teaching-note.pdf",
    mimeType: "application/pdf",
    buffer: execFileSync(
      resolve(
        root,
        process.platform === "win32"
          ? ".venv/Scripts/python.exe"
          : ".venv/bin/python",
      ),
      ["scripts/create_test_pdf.py"],
      { cwd: root },
    ),
  });
  await expect(
    page.getByText("teaching-note.pdf", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "People", exact: true }).click();
  await page
    .getByLabel("Email address", { exact: true })
    .fill("colleague@example.com");
  await page.getByRole("button", { name: "Create invite link" }).click();
  await expect(page.getByLabel("Invitation link")).toHaveValue(
    /\/invite#token=/,
  );
  await page.getByRole("button", { name: "Activity", exact: true }).click();
  await expect(
    page.getByText("roster imported", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /^Students/ }).click();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("radio", { name: "Dark", exact: true }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Assessments", exact: true }).click();
  await page
    .getByRole("button", { name: "New assessment", exact: true })
    .click();
  await dialog
    .getByLabel("Assessment title")
    .fill("CAT 1 · Stack fundamentals");
  await dialog
    .getByRole("button", { name: "Create assessment", exact: true })
    .click();
  await page.getByRole("button", { name: "Build rubric", exact: true }).click();
  await dialog
    .getByLabel("Question text", { exact: true })
    .fill("Explain how a stack orders its elements.");
  await dialog
    .getByLabel("Model answer / accepted alternatives")
    .fill("A stack follows last in, first out (LIFO).");
  await dialog
    .getByRole("button", { name: "Save rubric version", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Approve rubric & activate", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Upload papers", exact: true })
    .click();
  const pdfBuffer = execFileSync(
    resolve(
      root,
      process.platform === "win32"
        ? ".venv/Scripts/python.exe"
        : ".venv/bin/python",
    ),
    ["scripts/create_test_pdf.py"],
    { cwd: root },
  );
  await dialog.getByLabel("Answer papers", { exact: true }).setInputFiles({
    name: "ada-paper.pdf",
    mimeType: "application/pdf",
    buffer: pdfBuffer,
  });
  await dialog
    .getByLabel("Student for ada-paper.pdf")
    .selectOption({ label: "CS001 · Ada Lovelace" });
  await dialog
    .getByRole("checkbox", {
      name: "I have checked the student identity for every paper.",
    })
    .check();
  await dialog
    .getByRole("button", { name: "Confirm matches & upload", exact: true })
    .click();
  await expect(
    dialog.getByText("Matched and saved", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await page.getByRole("button", { name: "Review paper", exact: true }).click();
  await page
    .getByLabel("Reviewed answer for Q1", { exact: true })
    .fill("A stack uses LIFO: last in, first out.");
  await page
    .getByRole("checkbox", {
      name: "This answer is readable (or visibly blank).",
    })
    .check();
  await page
    .getByRole("checkbox", {
      name: "I checked the student identity, page completeness/order, and every question mapping.",
    })
    .check();
  await page
    .getByRole("button", { name: "Save extraction review", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Make every mark traceable." }),
  ).toBeVisible();
  // Save the same question in the across-paper review lane, then finish the paper.
  await page.getByRole("button", { name: "All papers", exact: true }).click();
  await page
    .getByRole("button", { name: "Question review", exact: true })
    .click();
  await page
    .getByLabel("Q1 reference score: Key concepts", { exact: true })
    .fill("4.5");
  await page
    .getByLabel("Q1 reference score: Explanation and supporting example", {
      exact: true,
    })
    .fill("5");
  await page
    .getByLabel("Question feedback", { exact: true })
    .fill("Good LIFO explanation. Add a concrete example.");
  await page
    .getByRole("button", { name: "Save question review", exact: true })
    .click();
  await expect(page.getByText(/Question review saved/)).toBeVisible();
  await page
    .getByRole("button", { name: "Open original & full review" })
    .click();
  const markInputs = page.getByRole("spinbutton", { name: /^Mark for/ });
  await expect(markInputs.nth(0)).toHaveValue("4.5");
  await markInputs.nth(0).fill("4.5");
  await markInputs.nth(1).fill("5");
  await page
    .getByLabel("Feedback for the student", { exact: true })
    .fill(
      "Clear explanation of LIFO. Add a concrete push/pop example next time.",
    );
  await page
    .getByLabel("Manual grading reason", { exact: true })
    .fill("Reviewed the original paper against both criteria.");
  await page
    .getByRole("checkbox", {
      name: "I reviewed every criterion and the student feedback.",
    })
    .check();
  await page
    .getByRole("button", { name: "Approve result", exact: true })
    .click();
  await expect(
    page.getByText("Approved. Ready for your final release."),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(root, ".tmp/review-dark.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Release to student", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm release", exact: true })
    .click();
  await expect(
    page.getByText(
      "Released. This approved result is visible only to the linked student.",
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Capture calibration example", exact: true })
    .click();
  await dialog.getByLabel("Example band").selectOption("high");
  await dialog
    .getByLabel("Why this is a useful example")
    .fill("Strong LIFO answer with a useful teacher reference.");
  await dialog
    .getByRole("button", { name: "Save calibration example", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "All papers", exact: true }).click();
  await page.getByRole("button", { name: "Calibration", exact: true }).click();
  await expect(
    page.getByText("Strong LIFO answer with a useful teacher reference."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Review queue", exact: true }).click();
  await page.getByText("Export marks", { exact: true }).click();
  const exportEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download CSV", exact: true }).click();
  expect((await exportEvent).suggestedFilename()).toBe("marks.csv");
  await page.screenshot({
    path: resolve(root, ".tmp/assessment-dark.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("radio", { name: "Light", exact: true }).check();
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.screenshot({
    path: resolve(root, ".tmp/assessment-light.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Revise rubric", exact: true })
    .click();
  await dialog
    .getByLabel("Reason for rubric revision")
    .fill("Clarify partial credit for correct ordering.");
  await dialog.getByLabel("Marks", { exact: true }).nth(0).fill("6");
  await dialog
    .getByLabel("Accepted alternatives (one per line)")
    .fill("Last pushed, first popped.");
  await dialog
    .getByRole("button", { name: "Save rubric version", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await page
    .getByRole("button", { name: "Rubric history", exact: true })
    .click();
  await page
    .getByRole("article")
    .filter({ has: page.getByText("Version 2", { exact: true }) })
    .getByRole("button", { name: "Review changes", exact: true })
    .click();
  await expect(dialog.getByText(/Version 1 → version 2/)).toBeVisible();
  await page.screenshot({
    path: resolve(root, ".tmp/rubric-diff-light.png"),
    fullPage: true,
  });
  await dialog
    .getByRole("checkbox", {
      name: "I reviewed these changes. Existing papers require separate re-evaluation.",
    })
    .check();
  await dialog
    .getByRole("button", { name: "Activate this rubric version", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "Review queue", exact: true }).click();
  await page.getByLabel("Queue filter").selectOption("stale");
  await expect(page.getByText("v2 available", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "View result", exact: true }).click();
  await page
    .getByRole("button", { name: "Re-evaluate paper", exact: true })
    .click();
  await dialog
    .getByLabel("Reason for re-evaluation")
    .fill("Apply the clarified partial-credit policy.");
  await dialog
    .getByRole("button", { name: "Start re-evaluation", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(
    page.getByText(/The previous released result stays visible/),
  ).toBeVisible();
  await page
    .getByRole("checkbox", {
      name: "I checked the student identity, page completeness/order, and every question mapping.",
    })
    .check();
  await page
    .getByRole("button", { name: "Save extraction review", exact: true })
    .click();
  await page
    .getByRole("spinbutton", { name: /^Mark for/ })
    .nth(0)
    .fill("6");
  await page
    .getByRole("spinbutton", { name: /^Mark for/ })
    .nth(1)
    .fill("5");
  await page
    .getByLabel("Feedback for the student", { exact: true })
    .fill("Re-evaluated with clarified ordering criteria.");
  await page
    .getByLabel("Manual grading reason", { exact: true })
    .fill("Reviewed the original answer against rubric version two.");
  await page
    .getByRole("checkbox", {
      name: "I reviewed every criterion and the student feedback.",
    })
    .check();
  await page
    .getByRole("button", { name: "Approve result", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Release to student", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm release", exact: true })
    .click();
  await expect(
    page.getByText(
      "Released. This approved result is visible only to the linked student.",
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Review history", exact: true })
    .click();
  await expect(
    dialog.getByText("Apply the clarified partial-credit policy.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    dialog.getByText(
      "Clear explanation of LIFO. Add a concrete push/pop example next time.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(root, ".tmp/review-history-light.png"),
    fullPage: true,
  });
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "All papers", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: resolve(root, ".tmp/review-queue-mobile.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: /^Students/ }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "Student roster" }),
  ).toBeVisible();
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: resolve(root, ".tmp/classroom-mobile.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "Good to see you." }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
