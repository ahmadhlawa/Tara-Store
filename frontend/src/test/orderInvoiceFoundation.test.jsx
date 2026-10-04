import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  INVOICE_STATUSES,
  ORDER_STATUSES,
  orderStatusLabels,
  PAYMENT_METHODS,
  PAYMENT_STATUSES,
  calculateOrderTotals,
  canCompleteOrder,
  canCreateManualOrder,
  canEditIncompleteOrder,
  canReopenOrder,
  formatMoney,
  multiplyMoney,
  paymentMethodLabels,
  paymentStatusLabels,
} from "../admin/orderInvoice/domain.js";
import {
  CompleteOrderDialog,
  OrderActivityTimeline,
  OrderItemsEditor,
  OrderStatusBadge,
  OrderTotalsSummary,
  PaymentStatusBadge,
} from "../admin/orderInvoice/components.jsx";
import { adminApi } from "../api/adminApi.js";
import { setAuthToken } from "../api/client.js";
import { stubApi } from "./utils.jsx";

describe("order and invoice domain", () => {
  it("offers four canonical statuses and retains legacy read labels", () => {
    expect(ORDER_STATUSES.map(([value]) => value)).toEqual(["new", "ready", "completed", "cancelled"]);
    ["confirmed", "delivered", "pending", "reviewing", "processing", "preparing", "shipped", "out_for_delivery"].forEach((status) => {
      expect(orderStatusLabels[status]).toBeTruthy();
    });
  });

  it("allows authorized completed and previously completed order eligibility despite legacy locks", () => {
    const order = { source: "website", status: "completed", is_locked: true, completed_at: "2026-10-03T00:00:00Z" };
    expect(canEditIncompleteOrder({ role: "admin" }, order)).toBe(true);
    expect(canEditIncompleteOrder({ role: "viewer" }, order)).toBe(false);
    expect(canEditIncompleteOrder({ role: "admin" }, { ...order, source: "whatsapp" })).toBe(false);
    expect(canEditIncompleteOrder({ role: "admin" }, { ...order, items: [{ item_kind: "manual" }] })).toBe(false);
    expect(canCompleteOrder({ role: "admin" }, { ...order, status: "ready" })).toBe(true);
  });
  it("calculates totals from decimal strings without floating-point rounding", () => {
    const totals = calculateOrderTotals({
      items: [
        { unit_price: "0.10", quantity: 3 },
        { unit_price: "1.25", quantity: 2 },
      ],
      discount: "0.05",
      delivery_fee: "4.20",
    });

    expect(totals).toEqual({ subtotal: "2.80", total: "6.95" });
    expect(calculateOrderTotals({ items: [{ unit_price: "2.00", quantity: 1 }], discount: "9.00", delivery_fee: "0.00" })).toEqual({ subtotal: "2.00", total: "0.00" });
    expect(multiplyMoney("2", 3)).toBe("6.00");
    expect(formatMoney("1000000000000000.05", "₪")).toBe("₪ 1,000,000,000,000,000.05");
  });

  it("includes one packaging fee after discount and delivery in edit and completion breakdowns", () => {
    expect(calculateOrderTotals({ items: [{ unit_price: "10.00", quantity: 2 }], discount: "1.00", delivery_fee: "3.00", packaging_fee: "5.00" })).toEqual({ subtotal: "20.00", total: "27.00" });
    render(<CompleteOrderDialog isOpen order={{ final_review: { items: [{ unit_price: "10.00", quantity: 2 }], discount: "1.00", delivery_fee: "3.00", packaging_type: "gift", packaging_fee: "5.00", total: "27.00" } }} onClose={vi.fn()} onComplete={vi.fn()} />);
    expect(screen.getByLabelText("مراجعة الطلب النهائية")).toHaveTextContent("تغليف كهدية");
    expect(screen.getByLabelText("مراجعة الطلب النهائية")).toHaveTextContent("27.00");
  });

  it("keeps manager-only actions separate from normal admin actions", () => {
    expect(canCreateManualOrder({ role: "super_admin" })).toBe(true);
    expect(canCreateManualOrder({ role: "admin" })).toBe(false);
    expect(canCompleteOrder({ role: "admin" }, { is_locked: false, status: "confirmed" })).toBe(true);
    expect(canEditIncompleteOrder({ role: "admin" }, { source: "website", is_locked: false, status: "completed" })).toBe(true);
    expect(canEditIncompleteOrder({ role: "admin" }, { source: "website", is_locked: false, status: "ready" })).toBe(true);
    expect(canEditIncompleteOrder({ role: "super_admin" }, { source: "whatsapp", is_locked: false, status: "ready" })).toBe(true);
    expect(canEditIncompleteOrder({ role: "admin" }, { source: "whatsapp", is_locked: false, status: "ready" })).toBe(false);
    expect(canEditIncompleteOrder({ role: "super_admin" }, { source: "whatsapp", is_locked: false, status: "cancelled" })).toBe(false);
    expect(canReopenOrder({ role: "admin" }, { status: "completed" })).toBe(false);
    expect(canReopenOrder({ role: "super_admin" }, { status: "completed", is_locked: false })).toBe(false);
    expect(canReopenOrder({ role: "super_admin" }, { status: "completed", is_locked: true })).toBe(true);
    const reopened = { source: "website", status: "ready", is_locked: false, completed_at: "2026-08-04T00:00:00Z" };
    expect(canEditIncompleteOrder({ role: "admin" }, reopened)).toBe(true);
    expect(canCompleteOrder({ role: "admin" }, reopened)).toBe(true);
    expect(canEditIncompleteOrder({ role: "super_admin" }, reopened)).toBe(true);
  });
});

describe("order and invoice API contract", () => {
  it("sends workflow writes to their authenticated backend endpoints", async () => {
    const calls = stubApi({
      "POST /api/v1/admin/orders/manual": {},
      "PATCH /api/v1/admin/orders/7": {},
      "POST /api/v1/admin/orders/7/complete": {},
      "POST /api/v1/admin/orders/7/reopen": {},
      "PATCH /api/v1/admin/invoices/INV-7/payment": {},
    });
    setAuthToken("workflow-token");

    await adminApi.createManualOrder({ source: "phone", items: [] });
    await adminApi.updateOrder(7, { items: [] });
    await adminApi.completeOrder(7, { payment_status: "unpaid" });
    await adminApi.reopenOrder(7, "تصحيح");
    await adminApi.updateInvoicePayment("INV-7", { payment_status: "paid" });

    expect(calls.map((call) => `${call.method} ${call.path}`)).toEqual([
      "POST /api/v1/admin/orders/manual",
      "PATCH /api/v1/admin/orders/7",
      "POST /api/v1/admin/orders/7/complete",
      "POST /api/v1/admin/orders/7/reopen",
      "PATCH /api/v1/admin/invoices/INV-7/payment",
    ]);
    expect(calls.every((call) => call.headers.Authorization === "Bearer workflow-token")).toBe(true);
    setAuthToken(null);
  });
});

describe("order and invoice components", () => {
  it("edits a manual line through labelled RTL-safe controls", async () => {
    const onChange = vi.fn();
    render(
      <OrderItemsEditor
        items={[{ kind: "manual", name: "طلب خاص", quantity: 1, unit_price: "2.50" }]}
        onChange={onChange}
      />,
    );

    fireEvent.change(screen.getByLabelText("سعر القطعة 1"), { target: { value: "3.75" } });

    expect(onChange).toHaveBeenLastCalledWith([
      { kind: "manual", name: "طلب خاص", quantity: 1, unit_price: "3.75" },
    ]);
  });

  it("renders totals and known status badges", () => {
    render(
      <>
        <OrderTotalsSummary items={[{ quantity: 2, unit_price: "1.50" }]} discount="0.25" deliveryFee="3.00" currencySymbol="₪" />
        <OrderStatusBadge status="completed" />
        <PaymentStatusBadge status="partially_paid" />
      </>,
    );

    expect(screen.getByText("₪ 5.75")).toBeInTheDocument();
    expect(screen.getByText("مكتمل")).toBeInTheDocument();
    expect(screen.getByText("غير مدفوع")).toBeInTheDocument();
  });

  // The Arabic strings here are display labels only. The values are the contract the
  // API validates against, so a drift between the two turns a valid manager choice
  // into a 422 "البيانات المرسلة غير صالحة." with nothing wrong on screen.
  it("offers only the payment status values the API accepts", () => {
    expect(PAYMENT_STATUSES.map(([value]) => value)).toEqual([
      "unpaid",
      "paid",
      "refunded",
    ]);
  });

  it("offers only the payment method values the API accepts", () => {
    expect(PAYMENT_METHODS.map(([value]) => value)).toEqual(["cash_on_delivery", "bank_transfer"]);
  });

  it("offers only the invoice status values the API accepts", () => {
    expect(INVOICE_STATUSES.map(([value]) => value)).toEqual(["active", "cancelled", "replaced"]);
  });

  it("labels every canonical payment status and method the API can return", () => {
    ["unpaid", "partially_paid", "paid", "partially_refunded", "refunded"].forEach((status) => {
      expect(paymentStatusLabels[status]).toBeTruthy();
    });
    ["cash_on_delivery", "card", "bank_transfer"].forEach((method) => {
      expect(paymentMethodLabels[method]).toBeTruthy();
    });
  });

  it("keeps the totals summary visible while a monetary field is blank during editing", () => {
    const { rerender } = render(
      <OrderTotalsSummary items={[{ quantity: 2, unit_price: "1.50" }]} discount="0.25" deliveryFee="3.00" currencySymbol="₪" />,
    );

    rerender(<OrderTotalsSummary items={[{ quantity: 2, unit_price: "1.50" }]} discount="" deliveryFee="3.00" currencySymbol="₪" />);

    expect(screen.getByLabelText("ملخص إجمالي الطلب")).toBeInTheDocument();
    expect(screen.getByText("₪ 6.00")).toBeInTheDocument();
  });

  it("renders activity as an ordered, labelled timeline", () => {
    render(
      <OrderActivityTimeline
        activities={[{ id: 1, event_type: "order_completed", reason: "تم الاستلام", created_at: "2026-08-04T10:00:00Z" }]}
      />,
    );

    expect(screen.getByRole("list", { name: "سجل نشاط الطلب" })).toHaveTextContent("اكتمل الطلب");
    expect(screen.getByRole("list", { name: "سجل نشاط الطلب" })).toHaveTextContent("تم الاستلام");
  });

  it("does not calculate a fractional item quantity", () => {
    render(<OrderItemsEditor items={[{ kind: "manual", name: "طلب خاص", quantity: "1.5", unit_price: "2.50" }]} onChange={vi.fn()} />);

    expect(screen.getByText("إجمالي الصنف: —")).toBeInTheDocument();
  });

  it.each(["unpaid", "paid", "refunded"])("submits %s completion state without client amounts and closes on Escape", async (payment_status) => {
    const onComplete = vi.fn();
    const onClose = vi.fn();
    render(<CompleteOrderDialog isOpen order={{ total: "0.00" }} onClose={onClose} onComplete={onComplete} />);
    const selector = screen.getByLabelText("حالة الدفع");
    expect(Array.from(selector.options, (option) => [option.value, option.textContent])).toEqual([
      ["unpaid", "غير مدفوع"], ["paid", "مدفوع"], ["refunded", "مردود"],
    ]);
    expect(screen.queryByLabelText("المبلغ المدفوع")).not.toBeInTheDocument();
    await userEvent.selectOptions(selector, payment_status);
    await userEvent.type(screen.getByLabelText("تفاصيل الدفع (اختياري)"), " Receipt ");
    await userEvent.type(screen.getByLabelText("ملاحظات الفاتورة (اختياري)"), " Note ");
    await userEvent.click(screen.getByRole("button", { name: "إتمام الطلب وإصدار الفاتورة" }));
    expect(onComplete).toHaveBeenCalledWith({
      payment_method: "cash_on_delivery", payment_status, payment_details: "Receipt", invoice_notes: "Note",
    });
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows the latest persisted review totals before completing", () => {
    render(<CompleteOrderDialog isOpen order={{ total: "12.50", final_review: { subtotal: "10.00", discount: "1.00", delivery_fee: "3.50", total: "12.50", items: [{ quantity: 2, unit_price: "5.00" }] } }} onClose={vi.fn()} onComplete={vi.fn()} />);

    expect(screen.getByLabelText("مراجعة الطلب النهائية")).toHaveTextContent("12.50");
  });

  it("opens the native dialog only through showModal", () => {
    const original = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "showModal");
    const showModal = vi.fn(function showModal() {
      if (this.hasAttribute("open")) throw new Error("dialog already open");
      this.setAttribute("open", "");
    });
    Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: showModal });

    try {
      render(<CompleteOrderDialog isOpen order={{ total: "12.50" }} onClose={vi.fn()} onComplete={vi.fn()} />);
      expect(showModal).toHaveBeenCalledTimes(1);
    } finally {
      if (original) Object.defineProperty(HTMLDialogElement.prototype, "showModal", original);
      else delete HTMLDialogElement.prototype.showModal;
    }
  });
});
