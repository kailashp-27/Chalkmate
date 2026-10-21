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
test("teacher publishes, previews and captures follow-up; student responds privately", async ({
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
  const ws = await call("/workspaces", { name: "Follow-up browser test" });
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
  await page.getByRole("button", { name: "Assignments", exact: true }).click();
  await page
    .getByRole("button", { name: "New assignment", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Assignment title").fill("Stack recovery practice");
  await dialog
    .getByLabel("Assignment instructions", { exact: true })
    .fill("Write a private stack example.");
  await dialog
    .getByRole("button", { name: "Save assignment draft", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
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
  await page.getByRole("button", { name: "Follow-up", exact: true }).click();
  await page
    .getByLabel("Assessment for score filter")
    .selectOption(assessment.id);
  await page.getByLabel("Published assignment").selectOption(vid);
  await page.getByLabel("Score threshold").fill("25");
  await page.getByLabel("Include the student’s approved score").check();
  await page
    .getByRole("button", { name: "Preview recipients", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "1 selected · 0 unresolved" }),
  ).toBeVisible();
  await expect(page.locator(".personal-message")).toContainText(
    "24.50 / 50.00",
  );
  await page
    .getByRole("button", { name: "Review approval", exact: true })
    .click();
  await dialog
    .getByLabel(
      "I reviewed the intended recipients and private message content.",
    )
    .check();
  await dialog
    .getByRole("button", {
      name: "Approve & queue local test emails",
      exact: true,
    })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText("Captured locally", { exact: true })).toBeVisible(
    { timeout: 30000 },
  );
  await page.screenshot({
    path: resolve(root, ".tmp/phase-four-followup-dark.png"),
    fullPage: true,
  });
  const context = await browser.newContext();
  const sp = await context.newPage();
  sp.on("pageerror", (e) => errors.push(e.message));
  await sp.goto(`/assignments/${vid}`);
  await sp.getByLabel("Email address", { exact: true }).fill(student.email);
  await sp.getByLabel("Password", { exact: true }).fill(student.password);
  await sp.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    sp.getByRole("heading", { name: "Stack recovery practice", exact: true }),
  ).toBeVisible();
  await sp
    .getByLabel("Your assignment response", { exact: true })
    .fill("Push A, push B; pop returns B then A.");
  await sp
    .getByRole("button", { name: "Submit response", exact: true })
    .click();
  await expect(
    sp.getByText("Your response v1 has been submitted.", { exact: true }),
  ).toBeVisible();
  await expect(
    sp.getByRole("button", { name: "Review & publish", exact: true }),
  ).toHaveCount(0);
  await sp.setViewportSize({ width: 390, height: 844 });
  expect(
    await sp.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await sp.screenshot({
    path: resolve(root, ".tmp/phase-four-student-mobile.png"),
    fullPage: true,
  });
  await context.close();
  expect(errors).toEqual([]);
});
