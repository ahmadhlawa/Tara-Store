# Data needed from the Vista Store owner

The supplied Facebook page could not be read without a logged-in session
(see `facebook-source-audit.md`). Only the business name is confirmed. Everything below
is **blank in the build** and must come from the owner before the store can go live.

Nothing here has been guessed. A blank field is a real blank, not a placeholder to be
overwritten silently.

## 1. Blocking — the store cannot take a real order without these

| # | Item | Where it lands | Status |
| --- | --- | --- | --- |
| 1 | Contact phone number | Admin → إعدادات المتجر → الهاتف | **Pending** |
| 2 | WhatsApp number (if different) | Admin → إعدادات المتجر → واتساب | **Pending** |
| 3 | Business address / pickup location | Admin → إعدادات المتجر → العنوان | **Pending** |
| 4 | Currency (code + symbol) | `instance/vista-store.yaml` → `store.currency_code` / `currency_symbol` | **Pending** — currently the template default `ILS` / `₪`, unverified |
| 5 | Delivery areas and the fee for each | Admin → مناطق التوصيل | **Pending** — no area exists, so checkout cannot complete |
| 6 | Free-delivery threshold per area, if any | Admin → مناطق التوصيل | **Pending** |
| 7 | Product catalog: name, price, description, stock per item | Admin → المنتجات | **Pending** — catalog is empty |
| 8 | Product categories | Admin → الأقسام | **Pending** |

Item 5 is the hardest blocker: the checkout form requires a delivery area, so until at
least one area with a real fee exists, no customer can place an order.

## 2. Branding

| # | Item | Where it lands | Status |
| --- | --- | --- | --- |
| 9 | Logo — original file, PNG or SVG, transparent background | Admin → الوسائط, then إعدادات المتجر → شعار المتجر | **Pending** |
| 10 | Favicon | Admin → إعدادات المتجر → أيقونة الموقع | **Pending** |
| 11 | Cover / hero image, ideally ≥ 1920px wide | Admin → شرائح الواجهة | **Pending** |
| 12 | Brand colours (primary, secondary, accent) as hex | Admin → إعدادات المتجر | **Pending** — template defaults in use, not Vista colours |
| 13 | Product photography, original resolution | Admin → المنتجات → الصور | **Pending** |
| 14 | Arabic tagline, one line | Admin → إعدادات المتجر → الوصف المختصر | **Pending** |

**Please send original files, not Facebook downloads.** Facebook re-encodes and
downscales every upload; a logo pulled from the page will look soft on a product card
and unusable on a printed invoice.

## 3. Payments

| # | Item | Where it lands | Status |
| --- | --- | --- | --- |
| 15 | Confirm cash on delivery is offered | Enabled by default | Assumed — please confirm |
| 16 | Manual/bank transfer instructions: bank, branch, account name, IBAN or account number | Admin → إعدادات المتجر → تعليمات الدفع اليدوي | **Pending** — blank, so the manual option shows no instructions |
| 17 | Confirm no card/online payment is wanted for now | Online payment is disabled and cannot be enabled from Admin | Assumed — please confirm |

## 4. Invoicing, legal and tax

The invoice system is built and works. By default it produces a **plain commercial
invoice, not a tax invoice**, and tax is off.

| # | Item | Where it lands | Status |
| --- | --- | --- | --- |
| 18 | Is a **tax** invoice required? | Admin → إعدادات المتجر → تفعيل الضريبة | **Pending** — currently off |
| 19 | Registered legal business name | Admin → إعدادات المتجر → الاسم القانوني | **Pending** |
| 20 | Commercial registration number | Admin → إعدادات المتجر → رقم التسجيل | **Pending** |
| 21 | Tax / VAT number | Admin → إعدادات المتجر → الرقم الضريبي | **Pending** |
| 22 | Tax rate, and whether listed prices already include it | Admin → إعدادات المتجر | **Pending** |
| 23 | Preferred invoice number prefix | Admin → إعدادات المتجر → بادئة رقم الفاتورة | Defaults to `INV`; change before the first invoice is issued |

**Do not fill 19–22 without written confirmation from the owner.** Printing a wrong
registration or tax number on a customer invoice is a legal problem, not a cosmetic one.

Note on 23: the prefix should be settled *before* the first confirmed order. Numbers
already issued keep their prefix; changing it later produces two visually different
series in the same ledger.

## 5. Policy pages

Created empty at bootstrap, and each is linked from the storefront footer. Empty pages
are dead ends for customers, so the owner needs to supply the text.

| # | Page | Status |
| --- | --- | --- |
| 24 | من نحن (about) | **Pending** |
| 25 | سياسة الخصوصية (privacy-policy) | **Pending** |
| 26 | سياسة التبديل والإرجاع (return-policy) | **Pending** |
| 27 | الشروط والأحكام (terms) | **Pending** |
| 28 | سياسة الشحن (shipping-policy) | **Pending** |
| 29 | تواصل معنا (contact) | **Pending** |

## 6. Operations

| # | Item | Status |
| --- | --- | --- |
| 30 | Opening hours, as they should display | **Pending** |
| 31 | Email address for order notifications | **Pending** |
| 32 | Instagram / TikTok / YouTube links, if any | **Pending** |
| 33 | Real name and email for the owner's admin account | **Pending** — only a temporary local admin exists |

## 7. Hosting — see also `docs/deployment/cpanel-capability-checklist.md`

| # | Item | Status |
| --- | --- | --- |
| 34 | Domain and subdomain for the store | **Pending** |
| 35 | cPanel capability answers | **Pending** — blocks any deployment planning |
