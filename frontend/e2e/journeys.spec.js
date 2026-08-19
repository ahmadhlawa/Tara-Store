import { expect, test } from "@playwright/test";
import { EMPLOYEE, MANAGER, apiToken, expectClean, login, watchPage } from "./helpers.js";

const PRODUCT = "vfx-resin-clear-1l";

/**
 * Never let an acceptance run reach WhatsApp, and record the hand-off deterministically.
 *
 * Replacing `window.open` rather than watching for a popup: a blocked or immediately
 * closed popup is not reliably observable, and this is the exact call the checkout page
 * makes, so recording it is both stricter and stable.
 */
async function stubWhatsApp(page) {
  await page.addInitScript(() => {
    window.__whatsappOpens = [];
    window.open = (url) => {
      window.__whatsappOpens.push(String(url));
      return null;
    };
  });
  await page.context().route(/wa\.me|whatsapp\.com/, (route) => route.abort());
}

const whatsappOpens = (page) => page.evaluate(() => window.__whatsappOpens || []);

test.describe("journey C — website order lifecycle", () => {
  test("checkout persists exactly one order, clears the cart and shows it in admin", async ({
    page,
    request,
  }) => {
    await stubWhatsApp(page);
    const watcher = watchPage(page);

    await page.goto(`/product/${PRODUCT}`);
    await page.getByRole("button", { name: /أضف إلى العربة|إضافة إلى العربة/ }).first().click();

    await page.goto("/checkout");
    const customerName = `عميل قبول ${Date.now()}`;

    const confirmation = page.getByRole("button", { name: /تأكيد وإرسال الطلب/ });
    await expect(confirmation).toBeDisabled();
    await expect(page.getByRole("heading", { name: "سياسة الإرجاع والاستبدال" })).toBeVisible();
    await expect(page.getByRole("link", { name: "سياسة الإرجاع والاستبدال" })).toHaveAttribute("href", "/page/return-policy");

    await page.getByLabel("الاسم الكامل").fill(customerName);
    await page.getByLabel("رقم الهاتف").fill("0591234567");
    await page.getByLabel("العنوان بالتفصيل").fill("رام الله - شارع الإرسال ١٢");
    await page.getByLabel("منطقة التوصيل").selectOption({ index: 1 });

    await page.getByRole("checkbox").check();
    await expect(confirmation).toBeEnabled();
    await expect(page.locator('form input[name="pay"]')).toHaveCount(1);

    const created = page.waitForResponse(
      (response) => response.url().includes("/api/v1/orders") && response.request().method() === "POST",
    );
    await confirmation.click();
    const response = await created;
    expect(response.status(), await response.text()).toBe(201);
    const order = await response.json();
    expect(order.payment_method).toBe("cash_on_delivery");

    // The hand-off happens only after the order exists, and it carries the server's
    // order number rather than anything the browser made up.
    const opened = await whatsappOpens(page);
    expect(opened, "no WhatsApp hand-off was attempted").toHaveLength(1);
    expect(decodeURIComponent(opened[0])).toContain(order.order_number);

    await page.waitForURL(new RegExp(`/order-success/${order.order_number}$`));

    // The cart is emptied only after the order exists.
    await page.goto("/cart");
    await expect(page.getByText(/لا توجد منتجات|العربة فارغة/)).toBeVisible();

    // Exactly one order, and it is visible to an admin immediately.
    const token = await apiToken(request, MANAGER);
    const found = await (
      await request.get(`/api/v1/admin/orders?q=${encodeURIComponent(customerName)}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();
    expect(found.total).toBe(1);
    expect(found.items[0].order_number).toBe(order.order_number);
    expect(found.items[0].source).toBe("website");
    expect(found.items[0].payment_status).toBe("unpaid");

    await login(page, MANAGER);
    await page.goto(`/admin/orders/${found.items[0].id}`);
    await expect(page.locator("body")).toContainText(order.order_number);
    await expect(page.locator("body")).toContainText(customerName);
    expectClean(watcher);
  });
});

test.describe("journey D — manual order lifecycle", () => {
  test("a manager creates a mixed manual order that reaches the orders workspace", async ({
    page,
    request,
  }) => {
    const token = await apiToken(request, MANAGER);
    const products = await (
      await request.get("/api/v1/admin/products?page_size=1", {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();

    const customerName = `طلب يدوي ${Date.now()}`;
    const created = await request.post("/api/v1/admin/orders/manual", {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        source: "whatsapp",
        customer_name: customerName,
        customer_phone: "0598887777",
        address: "نابلس - شارع فيصل ٥",
        payment_method: "cash_on_delivery",
        discount: "5.00",
        delivery_fee: "20.00",
        items: [
          { kind: "catalog", product_id: products.items[0].id, quantity: 2 },
          { kind: "manual", name: "نقش بالليزر", quantity: 1, unit_price: "40.00" },
        ],
      },
    });

    // The route exists on the API the browser actually talks to: no 405, no 422.
    expect(created.status(), await created.text()).toBe(201);
    const order = await created.json();

    // An incomplete manual order issues no invoice.
    const detail = await (
      await request.get(`/api/v1/admin/orders/${order.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();
    expect(detail.active_invoice).toBeNull();
    expect(detail.invoices).toEqual([]);
    expect(detail.source).toBe("whatsapp");

    // The manual line created no catalog product.
    const catalogue = await (
      await request.get("/api/v1/admin/products?q=%D9%86%D9%82%D8%B4%20%D8%A8%D8%A7%D9%84%D9%84%D9%8A%D8%B2%D8%B1", {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();
    expect(catalogue.total).toBe(0);

    const watcher = watchPage(page);
    await login(page, MANAGER);
    await page.goto(`/admin/orders/${order.id}`);
    await expect(page.locator("body")).toContainText(customerName);
    await expect(page.locator("body")).toContainText("نقش بالليزر");
    expectClean(watcher);
  });

  test("completing a manual order issues exactly one active invoice", async ({ request }) => {
    const token = await apiToken(request, MANAGER);
    const products = await (
      await request.get("/api/v1/admin/products?page_size=1", {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();

    const created = await request.post("/api/v1/admin/orders/manual", {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        source: "walk_in",
        customer_name: `إتمام فوري ${Date.now()}`,
        customer_phone: "0597776666",
        address: "رام الله - المعرض",
        items: [{ kind: "catalog", product_id: products.items[0].id, quantity: 1 }],
        completion: { payment_method: "cash_on_delivery", paid_amount: "10.00" },
      },
    });
    expect(created.status(), await created.text()).toBe(201);
    const order = await created.json();

    const detail = await (
      await request.get(`/api/v1/admin/orders/${order.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();
    expect(detail.status).toBe("completed");
    expect(detail.active_invoice).not.toBeNull();
    expect(detail.invoices.filter((invoice) => invoice.status === "active")).toHaveLength(1);

    // The order payload carries only a summary link; the issuer snapshot lives on the
    // invoice itself, which is what the archive and the invoice screen read.
    const invoice = await (
      await request.get(`/api/v1/admin/invoices/${detail.active_invoice.invoice_number}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();
    expect(invoice.issued_by_admin_name).toBeTruthy();
    expect(invoice.issued_by_admin_email).toBe(MANAGER.email);

    // Completing again is deliberately idempotent rather than an error: the service
    // returns the order untouched once an invoice exists. What must hold is that no
    // second invoice is minted and the first one is unchanged.
    const again = await request.post(`/api/v1/admin/orders/${order.id}/complete`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { payment_method: "card", paid_amount: "999.00" },
    });
    expect(again.status(), await again.text()).toBe(200);

    const after = await (
      await request.get(`/api/v1/admin/orders/${order.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();
    expect(after.invoices.filter((entry) => entry.status === "active")).toHaveLength(1);
    expect(after.active_invoice.invoice_number).toBe(invoice.invoice_number);

    const unchanged = await (
      await request.get(`/api/v1/admin/invoices/${invoice.invoice_number}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();
    expect(unchanged.payment_method).toBe(invoice.payment_method);
    expect(unchanged.paid_amount).toBe(invoice.paid_amount);
    expect(unchanged.grand_total).toBe(invoice.grand_total);
  });
});

test.describe("journey E — invoice archive filters", () => {
  const STATUSES = ["active", "cancelled", "replaced"];
  const PAYMENTS = ["unpaid", "partially_paid", "paid", "partially_refunded", "refunded"];
  const SOURCES = ["website", "whatsapp", "phone", "walk_in", "social", "other"];

  test("every canonical filter value is accepted by the API", async ({ request }) => {
    const token = await apiToken(request, MANAGER);
    const headers = { Authorization: `Bearer ${token}` };

    for (const status of STATUSES) {
      const response = await request.get(`/api/v1/admin/invoices?status=${status}`, { headers });
      expect(response.status(), `status=${status} → ${await response.text()}`).toBe(200);
    }
    for (const payment of PAYMENTS) {
      const response = await request.get(`/api/v1/admin/invoices?payment_status=${payment}`, { headers });
      expect(response.status(), `payment_status=${payment} → ${await response.text()}`).toBe(200);
    }
    for (const source of SOURCES) {
      const response = await request.get(`/api/v1/admin/invoices?source=${source}`, { headers });
      expect(response.status(), `source=${source} → ${await response.text()}`).toBe(200);
    }
  });

  test("filter combinations the archive screen can produce all return 200", async ({ request }) => {
    const token = await apiToken(request, MANAGER);
    const headers = { Authorization: `Bearer ${token}` };
    const combinations = [
      "status=replaced&payment_status=partially_paid",
      "status=replaced",
      "status=active&payment_status=paid",
      "source=website&issued_from=2020-01-01&issued_to=2030-12-31",
      "status=active&issued_from=2026-01-01",
      "q=INV&payment_status=unpaid",
      // An inverted range is a legitimate thing for a user to type; it must return an
      // empty result, not an error.
      "issued_from=2030-01-01&issued_to=2020-01-01",
    ];

    for (const query of combinations) {
      const response = await request.get(`/api/v1/admin/invoices?${query}`, { headers });
      expect(response.status(), `${query} → ${await response.text()}`).toBe(200);
    }
  });

  test("the archive screen filters without a client-side error", async ({ page }) => {
    const watcher = watchPage(page);
    await login(page, MANAGER);
    await page.goto("/admin/invoices");
    await page.waitForLoadState("networkidle");

    // Drive every select on the screen through all of its options.
    const selects = page.locator("select");
    const count = await selects.count();
    expect(count, "the archive screen exposes no filter selects").toBeGreaterThan(0);

    for (let index = 0; index < count; index += 1) {
      const select = selects.nth(index);
      const values = await select.locator("option").evaluateAll((options) =>
        options.map((option) => option.value),
      );
      for (const value of values) {
        await select.selectOption(value);
        await page.waitForLoadState("networkidle");
        await expect(page.locator("body")).not.toContainText("بيانات غير صالحة");
      }
      await select.selectOption(values[0]);
    }

    expectClean(watcher);
  });
});

test.describe("journey H — permission boundaries", () => {
  test("a normal admin is denied the manager-only screens in the browser", async ({ page }) => {
    await login(page, EMPLOYEE);

    for (const route of ["/admin/orders/manual", "/admin/admins", "/admin/audit"]) {
      await page.goto(route);
      await expect(page, `${route} should have redirected`).toHaveURL(/\/admin$/);
    }
  });

  test("a normal admin is denied the manager-only endpoints by the API", async ({ request }) => {
    const token = await apiToken(request, EMPLOYEE);
    const headers = { Authorization: `Bearer ${token}` };

    const admins = await request.get("/api/v1/admin/admins", { headers });
    expect(admins.status()).toBe(403);

    const audit = await request.get("/api/v1/admin/audit-logs", { headers });
    expect(audit.status()).toBe(403);

    const manual = await request.post("/api/v1/admin/orders/manual", {
      headers,
      data: {
        source: "phone",
        customer_name: "محاولة غير مصرّح بها",
        customer_phone: "0591111111",
        address: "عنوان اختباري كافٍ",
        items: [{ kind: "manual", name: "بند", quantity: 1, unit_price: "1.00" }],
      },
    });
    expect(manual.status(), "hidden navigation is not a permission boundary").toBe(403);
  });

  test("a super admin reaches the manager-only screens", async ({ page }) => {
    await login(page, MANAGER);
    for (const route of ["/admin/orders/manual", "/admin/admins", "/admin/audit"]) {
      await page.goto(route);
      await expect(page).toHaveURL(new RegExp(`${route.replace(/\//g, "\\/")}$`));
    }
  });

  test("a normal admin cannot reverse a payment or refund an invoice", async ({ request }) => {
    const managerToken = await apiToken(request, MANAGER);
    const employeeToken = await apiToken(request, EMPLOYEE);

    const invoices = await (
      await request.get("/api/v1/admin/invoices?status=active&payment_status=paid&page_size=1", {
        headers: { Authorization: `Bearer ${managerToken}` },
      })
    ).json();
    test.skip(invoices.items.length === 0, "no fully paid invoice in the fixture");
    const number = invoices.items[0].invoice_number;

    const refund = await request.patch(`/api/v1/admin/invoices/${number}/payment`, {
      headers: { Authorization: `Bearer ${employeeToken}` },
      data: { refunded_amount: "1.00" },
    });
    expect(refund.status()).toBeGreaterThanOrEqual(400);

    const lower = await request.patch(`/api/v1/admin/invoices/${number}/payment`, {
      headers: { Authorization: `Bearer ${employeeToken}` },
      data: { paid_amount: "0.00" },
    });
    expect(lower.status()).toBeGreaterThanOrEqual(400);
  });
});
