import { expect } from "@playwright/test";

/**
 * Acceptance credentials. They exist only inside the disposable validation database
 * created by backend/scripts/seed_full_validation.py and are worthless anywhere else.
 */
export const MANAGER = { email: "super@tara-acceptance.dev", password: "Validation!Pass42" };
export const EMPLOYEE = { email: "admin@tara-acceptance.dev", password: "Validation!Pass42" };
export const DISABLED = { email: "inactive@tara-acceptance.dev", password: "Validation!Pass42" };

/**
 * Collect console errors and failed responses for the lifetime of a page.
 *
 * Returned arrays are live, so a test asserts on them after the navigation it cares
 * about rather than having to wire listeners itself.
 */
export function watchPage(page) {
  const consoleErrors = [];
  const failedRequests = [];

  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    // React Router's v7 migration notices are warnings printed at error level by
    // some builds; they say nothing about this application's behaviour.
    if (text.includes("React Router Future Flag Warning")) return;
    consoleErrors.push(text);
  });
  page.on("pageerror", (error) => consoleErrors.push(`pageerror: ${error.message}`));
  page.on("response", (response) => {
    if (response.status() >= 400) {
      failedRequests.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });

  return { consoleErrors, failedRequests };
}

/** Assert a page loaded cleanly: no console errors and no 4xx/5xx responses. */
export function expectClean({ consoleErrors, failedRequests }, { allowStatus = [] } = {}) {
  const unexpected = failedRequests.filter(
    (entry) => !allowStatus.some((code) => entry.startsWith(String(code))),
  );
  // Assert the request list first: it carries the URLs, so a failure here names the
  // offending resource instead of only reporting "404" from the console.
  expect(unexpected, `failed requests:\n${unexpected.join("\n")}`).toEqual([]);
  expect(consoleErrors, `console errors:\n${consoleErrors.join("\n")}`).toEqual([]);
}

/** Sign in through the real login form and land on the dashboard. */
export async function login(page, account = MANAGER) {
  await page.goto("/admin/login");
  await page.locator('form input[type="email"]').fill(account.email);
  await page.locator('form input[type="password"]').fill(account.password);
  await page.getByRole("button", { name: "دخول" }).click();
  await page.waitForURL(/\/admin(?!\/login)/, { timeout: 20_000 });
}

/** Call the API directly with an admin token, for permission-boundary assertions. */
export async function apiToken(request, account) {
  const response = await request.post("/api/v1/auth/login", {
    data: { email: account.email, password: account.password },
  });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()).access_token;
}
