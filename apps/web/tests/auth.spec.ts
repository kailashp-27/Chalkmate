import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";

const root = resolve(process.cwd(), "../..");
const env = Object.fromEntries(
  readFileSync(resolve(root, ".env"), "utf8")
    .split(/\r?\n/)
    .filter((l) => l.includes("=") && !l.startsWith("#"))
    .map((l) => {
      const at = l.indexOf("=");
      return [l.slice(0, at), l.slice(at + 1)];
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

test("local signup explains captured email, verifies successfully, and supports both themes", async ({
  page,
  request,
  browser,
}) => {
  const email = `e2e-${randomUUID()}@example.com`;
  const password = `Test-${randomUUID()}!`;
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(
    page.getByRole("link", { name: "Open local email inbox" }),
  ).toHaveAttribute("href", "http://127.0.0.1:54324");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("radio", { name: "Light", exact: true }).check();
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("radio", { name: "Dark", exact: true }).check();
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await page.screenshot({
    path: resolve(root, ".tmp/auth-dark.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "New here? Create an account" })
    .click();
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  const response = page.waitForResponse(
    (r) =>
      r.url().includes("/auth/v1/signup") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  const signup = await response;
  expect(signup.ok()).toBeTruthy();
  accountId = (await signup.json()).id;
  await expect(
    page.getByText(
      "Open the local email inbox below to verify your account, then sign in.",
    ),
  ).toBeVisible();
  const messages = await request.get("http://127.0.0.1:54324/api/v1/messages");
  expect(messages.ok()).toBeTruthy();
  const message = (await messages.json()).messages.find(
    (m: { To: { Address: string }[] }) => m.To.some((t) => t.Address === email),
  );
  expect(message).toBeTruthy();
  const detail = await request.get(
    `http://127.0.0.1:54324/api/v1/message/${message.ID}`,
  );
  const html = (await detail.json()).HTML as string;
  const link = html.match(/href="([^"]*\/auth\/v1\/verify[^\"]*)"/);
  expect(link).toBeTruthy();
  await page.goto(link![1].replaceAll("&amp;", "&"));
  await expect(
    page.getByRole("heading", { name: "A home for your teaching." }),
  ).toBeVisible();
  // Verification must also satisfy the API's confirmed-email check.
  const session = await request.post(
    `${env.SUPABASE_URL}/auth/v1/token?grant_type=password`,
    { headers: { apikey: env.SUPABASE_ANON_KEY }, data: { email, password } },
  );
  expect(session.ok()).toBeTruthy();
  const apiSession = await request.get("http://127.0.0.1:8100/v1/session", {
    headers: { Authorization: `Bearer ${(await session.json()).access_token}` },
  });
  expect(apiSession.ok()).toBeTruthy();
  const recovery = await browser.newPage();
  await recovery.goto(new URL(page.url()).origin);
  await recovery
    .getByRole("button", { name: "Forgot your password?", exact: true })
    .click();
  await recovery.getByLabel("Email address", { exact: true }).fill(email);
  await recovery
    .getByRole("button", { name: "Send recovery link", exact: true })
    .click();
  await expect(
    recovery.getByText(
      "If this email has an account, open the local email inbox below for the recovery link.",
      { exact: true },
    ),
  ).toBeVisible();
  const recoveryMessages = await request.get(
    "http://127.0.0.1:54324/api/v1/messages",
  );
  const resetMessage = (await recoveryMessages.json()).messages.find(
    (m: { To: { Address: string }[]; Subject: string }) =>
      m.To.some((t) => t.Address === email) && /reset|recover/i.test(m.Subject),
  );
  expect(resetMessage).toBeTruthy();
  const resetDetail = await request.get(
    `http://127.0.0.1:54324/api/v1/message/${resetMessage.ID}`,
  );
  const resetLink = ((await resetDetail.json()).HTML as string).match(
    /href="([^"]*\/auth\/v1\/verify[^\"]*)"/,
  );
  expect(resetLink).toBeTruthy();
  await recovery.goto(resetLink![1].replaceAll("&amp;", "&"));
  await expect(
    recovery.getByRole("heading", {
      name: "Choose a new password",
      exact: true,
    }),
  ).toBeVisible();
  const newPassword = `Changed-${randomUUID()}!`;
  await recovery.getByLabel("Password", { exact: true }).fill(newPassword);
  await recovery
    .getByRole("button", { name: "Save password", exact: true })
    .click();
  await expect(
    recovery.getByRole("heading", { name: "A home for your teaching." }),
  ).toBeVisible();
  const changedLogin = await request.post(
    `${env.SUPABASE_URL}/auth/v1/token?grant_type=password`,
    {
      headers: { apikey: env.SUPABASE_ANON_KEY },
      data: { email, password: newPassword },
    },
  );
  expect(changedLogin.ok()).toBeTruthy();
  await recovery.close();
});
