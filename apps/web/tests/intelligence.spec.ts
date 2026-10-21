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
test("teacher inspects evidence, reviews findings and approves a private revision pack", async ({
  page,
  request,
  browser,
}) => {
  test.setTimeout(240000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  async function user() {
    const email = `e2e-${randomUUID()}@example.com`,
      password = `Test-${randomUUID()}!`;
    const r = await request.post(`${env.SUPABASE_URL}/auth/v1/admin/users`, {
      headers: {
        apikey: env.SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
      },
      data: { email, password, email_confirm: true },
    });
    expect(r.ok()).toBeTruthy();
    const { id } = await r.json();
    createdIds.push(id);
    const login = await request.post(
      `${env.SUPABASE_URL}/auth/v1/token?grant_type=password`,
      { headers: { apikey: env.SUPABASE_ANON_KEY }, data: { email, password } },
    );
    return { id, email, password, token: (await login.json()).access_token };
  }
  const teacher = await user(),
    student = await user();
  async function call(path: string, data?: unknown, token = teacher.token) {
    const r = await request.fetch(`http://127.0.0.1:8100/v1${path}`, {
      method: data === undefined ? "GET" : "POST",
      headers: { Authorization: `Bearer ${token}` },
      data,
    });
    expect(r.ok(), await r.text()).toBeTruthy();
    return r.json();
  }
  const ws = await call("/workspaces", { name: "Teaching intelligence test" });
  const classroom = await call(`/workspaces/${ws.id}/classrooms`, {
    name: "Stack classroom",
    subject: "Data structures",
    term: "2026",
  });
  const pre = await request.post(
    `http://127.0.0.1:8100/v1/classrooms/${classroom.id}/imports/preview`,
    {
      headers: { Authorization: `Bearer ${teacher.token}` },
      multipart: {
        file: {
          name: "roster.csv",
          mimeType: "text/csv",
          buffer: Buffer.from(
            `registration_number,name,email\nS001,Practice Student,${student.email}`,
          ),
        },
      },
    },
  );
  expect(pre.ok()).toBeTruthy();
  await call(
    `/classrooms/${classroom.id}/imports/${(await pre.json()).id}/confirm`,
    {},
  );
  const roster = await call(`/classrooms/${classroom.id}/students`);
  const invitation = await call(`/classrooms/${classroom.id}/invitations`, {
    email: student.email,
    role: "student",
    student_id: roster[0].id,
  });
  await call(
    "/invitations/accept",
    { token: invitation.url.split("#token=")[1] },
    student.token,
  );
  const assessment = await call(`/classrooms/${classroom.id}/assessments`, {
    title: "Stack check",
  });
  const rubric = await call(`/assessments/${assessment.id}/rubrics`, {
    questions: [
      {
        label: "Q1",
        prompt: "Explain a stack",
        maximum: "50",
        model_answer: "LIFO",
        criteria: [{ label: "Ordering", maximum: "50" }],
      },
    ],
  });
  await call(`/assessments/${assessment.id}/activate`, {
    rubric_id: rubric.id,
  });
  const upload = await request.post(
    `http://127.0.0.1:8100/v1/classrooms/${classroom.id}/files`,
    {
      headers: { Authorization: `Bearer ${teacher.token}` },
      multipart: {
        file: {
          name: "answer.pdf",
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
        },
      },
    },
  );
  expect(upload.ok()).toBeTruthy();
  const paper = await call(`/assessments/${assessment.id}/submissions`, {
    student_id: roster[0].id,
    file_id: (await upload.json()).id,
    identity_confirmed: true,
  });
  const extraction = await call(`/submissions/${paper.id}/extractions`, {
    base_version: 0,
    pages_complete: true,
    identity_confirmed: true,
    answers: [
      {
        question_id: rubric.questions[0].id,
        text: "Last in first out",
        page_from: 1,
        page_to: 1,
        readable: true,
      },
    ],
  });
  const decision = await call(`/submissions/${paper.id}/decisions`, {
    extraction_id: extraction.id,
    feedback: "Practice one more example.",
    reason: "Teacher checked against rubric.",
    marks: [{ criterion_id: rubric.questions[0].criteria[0].id, mark: "24.5" }],
  });
  await call(`/submissions/${paper.id}/release`, { decision_id: decision.id });
  await page.goto("/");
  await page.getByLabel("Email address", { exact: true }).fill(teacher.email);
  await page.getByLabel("Password", { exact: true }).fill(teacher.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Intelligence", exact: true }).click();
  await page.getByLabel("Assessment to explore").selectOption(assessment.id);
  await expect(
    page.getByRole("heading", { name: "Topic overview", exact: true }),
  ).toBeVisible();
  await expect(page.locator("table")).toContainText("24.5 / 50");
  await page
    .getByLabel("Question for analysis")
    .selectOption(rubric.questions[0].id);
  await page
    .getByLabel("Teaching topic", { exact: true })
    .fill("Stack ordering");
  await page
    .getByRole("button", { name: "Inspect source answers", exact: true })
    .click();
  await expect(
    page.getByText("1 source answers selected", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Record a manual finding", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Finding title", { exact: true })
    .fill("Practice applying stack ordering");
  await dialog
    .getByLabel("Evidence explanation")
    .fill(
      "The answer names the ordering but would benefit from a concrete trace.",
    );
  await dialog
    .getByLabel("Suggested teaching action")
    .fill("Trace two push operations followed by a pop.");
  await dialog.getByLabel("Exact evidence quote").fill("Last in first out");
  await dialog
    .getByRole("button", { name: "Save manual finding", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await page.getByText("Inspect 1 evidence citations", { exact: true }).click();
  await expect(page.locator("blockquote")).toContainText("Last in first out");
  await page
    .getByRole("button", { name: "Review finding", exact: true })
    .click();
  await dialog
    .getByLabel("Teacher review reason")
    .fill("Checked the exact answer and the approved rubric.");
  await dialog
    .getByRole("button", { name: "Save finding review", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await page
    .getByLabel("Practice applying stack ordering", { exact: true })
    .check();
  await page.getByLabel("Material type").selectOption("revision");
  await page
    .getByRole("button", { name: "Write practice manually", exact: true })
    .click();
  await dialog
    .getByLabel("Practice title", { exact: true })
    .fill("Stack revision pack");
  await dialog
    .getByLabel("Student introduction")
    .fill("Review LIFO ordering and trace the stack.");
  await dialog
    .getByLabel("Learning objectives")
    .fill("Trace push and pop operations.");
  await dialog
    .getByLabel("Revision notes")
    .fill("The newest item is removed first.");
  await dialog
    .getByLabel("Question 1", { exact: true })
    .fill("Push A then B. What does the next pop return?");
  await dialog
    .getByLabel("Hint 1 (student-visible)")
    .fill("Consider the last item added.");
  await dialog
    .getByLabel("Teacher answer 1", { exact: true })
    .fill("PRIVATE-KEY: B then A.");
  await dialog
    .getByLabel("Teacher rationale 1", { exact: true })
    .fill("PRIVATE-RATIONALE: Connect operations to LIFO.");
  await dialog
    .getByRole("button", {
      name: "Save teacher-authored material",
      exact: true,
    })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".material-student-preview")).not.toContainText(
    "PRIVATE-KEY",
  );
  await expect(page.locator(".material-student-preview")).toContainText(
    "Push A then B",
  );
  const downloadWait = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export student pack", exact: true })
    .click();
  const downloaded = await downloadWait;
  await downloaded.saveAs(resolve(root, ".tmp/browser-student-revision.md"));
  expect(
    readFileSync(resolve(root, ".tmp/browser-student-revision.md"), "utf8"),
  ).not.toContain("PRIVATE-KEY");
  await page
    .getByRole("button", { name: "Edit material as new version", exact: true })
    .click();
  await dialog
    .getByLabel("Practice title", { exact: true })
    .fill("Reviewed stack revision pack");
  await dialog
    .getByLabel("Reason for material revision")
    .fill("Clarify the title for students.");
  await dialog
    .getByRole("button", { name: "Save new material version", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(
    page.getByText("MATERIAL VERSION 2", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Review & approve material", exact: true })
    .click();
  await dialog
    .getByLabel(
      "I reviewed the student content, hints, and separate teacher answers for accuracy and suitability.",
    )
    .check();
  await dialog
    .getByLabel("Material approval reason")
    .fill("Reviewed the private key and student questions for accuracy.");
  await dialog
    .getByRole("button", {
      name: "Approve & create assignment draft",
      exact: true,
    })
    .click();
  await expect(dialog).not.toBeVisible();
  await page.screenshot({
    path: resolve(root, ".tmp/phase-five-material-dark.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Open assignment draft", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Reviewed stack revision pack",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator(".assignment-instructions")).not.toContainText(
    "PRIVATE-KEY",
  );
  await expect(page.getByText("Draft", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Review & publish", exact: true })
    .click();
  await dialog
    .getByLabel("I reviewed the instructions, due date, and intended audience.")
    .check();
  await dialog
    .getByRole("button", { name: "Publish assignment", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  const assignments = await call(`/classrooms/${classroom.id}/assignments`);
  const vid = assignments[0].version.id;
  const context = await browser.newContext();
  const sp = await context.newPage();
  await sp.goto(`/assignments/${vid}`);
  await sp.getByLabel("Email address", { exact: true }).fill(student.email);
  await sp.getByLabel("Password", { exact: true }).fill(student.password);
  await sp.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    sp.getByRole("heading", {
      name: "Reviewed stack revision pack",
      exact: true,
    }),
  ).toBeVisible();
  await expect(sp.locator("main")).not.toContainText("PRIVATE-KEY");
  await expect(sp.locator("main")).not.toContainText(
    "Private teacher answer key",
  );
  await sp.setViewportSize({ width: 390, height: 844 });
  expect(
    await sp.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await sp.screenshot({
    path: resolve(root, ".tmp/phase-five-revision-mobile.png"),
    fullPage: true,
  });
  await context.close();
  expect(errors).toEqual([]);
});
