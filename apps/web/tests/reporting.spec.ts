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
test("teacher prepares department exports and reviews question-bank performance", async ({
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
  const syllabus = await call(`/classrooms/${classroom.id}/planning`, {
    kind: "syllabus",
    title: "Stack syllabus",
    content: {
      topics: [
        {
          name: "Stacks",
          text: "A stack uses LIFO. Push and pop track the last added item.",
        },
      ],
    },
  });
  await call(`/planning/${syllabus.id}/approve`, {});
  const bank = await call(`/classrooms/${classroom.id}/planning`, {
    kind: "question_bank",
    title: "Reusable stacks",
    source_ids: [syllabus.id],
    content: {
      questions: [
        {
          topic: "Stacks",
          text: "Explain stack removal order.",
          marks: "50",
          solution: "LIFO",
          rubric: "Credit correct ordering and explanation.",
          references: [{ source_id: "S1", quote: "A stack uses LIFO." }],
        },
      ],
    },
  });
  await call(`/planning/${bank.id}/approve`, {});
  await page.goto("/");
  await page.getByLabel("Email address", { exact: true }).fill(teacher.email);
  await page.getByLabel("Password", { exact: true }).fill(teacher.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Planning", exact: true }).click();
  await page
    .getByRole("button", { name: "Marks template Your columns, your format" })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Title", { exact: true }).fill("Department export");
  await dialog
    .getByLabel("Heading for column 1", { exact: true })
    .fill("Department ID");
  await dialog
    .getByRole("button", { name: "Move column 4 up", exact: true })
    .click();
  await dialog.getByRole("button", { name: "Save draft", exact: true }).click();
  await page.getByRole("button", { name: /Department export/ }).click();
  await dialog
    .getByRole("button", { name: "Approve version", exact: true })
    .click();
  await expect(
    dialog.getByText("v1 · Approved", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await page
    .getByLabel("Assessment", { exact: true })
    .selectOption(assessment.id);
  await page
    .getByLabel("Export template", { exact: true })
    .selectOption({ label: "Department export · v1" });
  await page
    .getByRole("button", { name: "Prepare preview", exact: true })
    .click();
  await expect(
    dialog.getByRole("heading", { name: "Review marks export", exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("cell", { name: "24.50", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(root, ".tmp/phase-eight-export-preview.png"),
    fullPage: true,
  });
  const downloading = page.waitForEvent("download");
  await dialog
    .getByRole("button", { name: "Download CSV", exact: true })
    .click();
  const file = await (await downloading).path();
  const csv = readFileSync(file!, "utf8");
  expect(csv).toContain("Department ID,Name,Total,Result status,Maximum");
  expect(csv).toContain("24.50");
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("radio", { name: "Light", exact: true }).check();
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await page.screenshot({
    path: resolve(root, ".tmp/phase-eight-reporting-light.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: /Reusable stacks/ }).click();
  await dialog.getByText("Review a question link", { exact: true }).click();
  await dialog
    .getByLabel("Linked assessment", { exact: true })
    .selectOption(assessment.id);
  await dialog
    .getByLabel("Graded question", { exact: true })
    .selectOption(rubric.questions[0].id);
  await dialog
    .getByLabel("Review note", { exact: true })
    .fill("Teacher confirmed this bank question was used.");
  await dialog
    .getByRole("button", { name: "Save reviewed link", exact: true })
    .click();
  await expect(
    dialog.getByText(/1 reviewed · average 24\.50 \/ 50(?:\.00)?/),
  ).toBeVisible();
  await dialog
    .getByLabel("Review note", { exact: true })
    .fill("This mapping is no longer needed.");
  await dialog
    .getByRole("button", { name: "Remove link", exact: true })
    .click();
  await expect(
    dialog.getByText("Link history · 2", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Readiness", exact: true }).click();
  await expect(
    page.locator(".service-card").filter({ hasText: "Database" }),
  ).toContainText("Ready");
  await expect(
    page.locator(".service-card").filter({ hasText: "Private files" }),
  ).toContainText("Ready");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: resolve(root, ".tmp/phase-nine-readiness-mobile.png"),
    fullPage: true,
  });
  const studentPage = await browser.newPage();
  await studentPage.goto(new URL(page.url()).origin);
  await studentPage
    .getByLabel("Email address", { exact: true })
    .fill(student.email);
  await studentPage
    .getByLabel("Password", { exact: true })
    .fill(student.password);
  await studentPage
    .getByRole("button", { name: "Sign in", exact: true })
    .click();
  await studentPage
    .getByRole("button", { name: "Results", exact: true })
    .click();
  await studentPage
    .getByRole("button", { name: "Request a review", exact: true })
    .click();
  const studentDialog = studentPage.getByRole("dialog");
  await studentDialog
    .getByLabel("What should your teacher review?")
    .fill("Please check whether my explanation earns partial credit.");
  await studentDialog
    .getByRole("button", { name: "Send review request", exact: true })
    .click();
  await expect(
    studentPage.getByText("Awaiting teacher", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Your classroom, at a glance" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Respond", exact: true }).click();
  await dialog
    .getByLabel("Teacher response", { exact: true })
    .fill(
      "I reviewed your answer against the criterion. The released result remains correct.",
    );
  await dialog
    .getByRole("button", { name: "Save response", exact: true })
    .click();
  await expect(page.getByText("Responded", { exact: true })).toBeVisible();
  await studentPage.reload();
  await studentPage
    .getByRole("button", { name: "Results", exact: true })
    .click();
  await expect(
    studentPage.getByText(
      "I reviewed your answer against the criterion. The released result remains correct.",
      { exact: true },
    ),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: resolve(root, ".tmp/release-overview-mobile.png"),
    fullPage: true,
  });
  await studentPage.close();
  expect(errors).toEqual([]);
});
