export const CUSTOMER_COUNTRY_CODES = ["+970", "+972"];

const digitsOnly = (value) => String(value || "").replace(/\D/g, "");

export function normalizeCustomerPhone(countryCode, localPhone) {
  if (!CUSTOMER_COUNTRY_CODES.includes(countryCode)) return null;
  const localDigits = digitsOnly(localPhone).replace(/^0/, "");
  if (!/^\d{9}$/.test(localDigits)) return null;
  return `${digitsOnly(countryCode)}${localDigits}`;
}

export function normalizeLegacyCustomerPhone(phone) {
  const digits = digitsOnly(phone);
  if (/^(970|972)\d{9}$/.test(digits)) return digits;
  if (/^059\d{7}$/.test(digits)) return `970${digits.slice(1)}`;
  if (/^052\d{7}$/.test(digits)) return `972${digits.slice(1)}`;
  return digits;
}

export function customerWhatsAppHref(phone) {
  const normalized = normalizeLegacyCustomerPhone(phone);
  return normalized ? `https://wa.me/${normalized}` : "#";
}
