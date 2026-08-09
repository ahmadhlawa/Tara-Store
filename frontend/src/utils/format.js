// Display formatting. The currency symbol comes from StoreSettings, so a client
// instance changes it from the admin area without touching code.

export function makeMoney(symbol = "₪") {
  return (value) => `${Math.round(Number(value) || 0)} ${symbol}`;
}

export function discountPercent(price, compareAt) {
  if (!compareAt || compareAt <= price) return 0;
  return Math.round((1 - price / compareAt) * 100);
}

export function normalizeAr(value) {
  return String(value || "")
    .replace(/[ً-ْـ]/g, "")
    .replace(/[أإآ]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/ؤ/g, "و")
    .replace(/ئ/g, "ي")
    .replace(/ة/g, "ه")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

export function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("ar", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(date);
}

export function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("ar", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function readingTime(text) {
  const words = String(text || "").trim().split(/\s+/).filter(Boolean).length;
  return `${Math.max(1, Math.round(words / 180))} دقائق`;
}

export function whatsappHref(number, message) {
  const digits = String(number || "").replace(/\D/g, "");
  if (!digits) return "#";
  return `https://wa.me/${digits}?text=${encodeURIComponent(message || "")}`;
}
