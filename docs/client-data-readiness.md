# Tara client-data readiness

Development is ready for real client data. Tara starts clean; no preview purge is needed
unless a future preview batch is explicitly imported.

## Received and applied (phase 1)

Everything the client has confirmed apart from the catalog is in
[`instance/tara-store.yaml`](../instance/tara-store.yaml) and is applied with:

```bash
cd backend
python -m scripts.instance_cli plan  --profile ../instance/tara-store.yaml   # writes nothing
python -m scripts.instance_cli apply --profile ../instance/tara-store.yaml   # idempotent
```

That file now carries, beside the store identity and theme it always did:

- the brand name (latin "Tara" — the storefront is Arabic, the brand is not), currency,
  and the confirmed phone/WhatsApp line and working hours;
- the client's approved policy copy for من نحن, الخصوصية, الشروط والأحكام, الشحن والتوصيل
  and الاستبدال والاسترجاع, plus a contact page built only from confirmed details;
- the delivery table — الضفة 25, القدس 35, الداخل 80, free delivery from 220 / 220 / 400.

Bootstrap fills a static page only while its body is still blank and creates a delivery
area only when no area of that name exists, so an Admin edit is never overwritten. Change
published copy in Admin, not by re-applying the profile.

Deliberately left empty because the client has not supplied them: tagline, SEO title and
description, announcement bar, address, email, social links, legal and tax fields (tax
stays disabled), hero slides and banners.

## Still to come

- completed [catalog spreadsheet template](client-templates/tara-store-catalog-template.xlsx), including categories, products, options, variants, packages, prices and stock;
- product/category images named exactly as the spreadsheet references;
- hero/banner assets and copy;
- the administrator account, created at production deployment with:
  `python -m app.initial_data --email OWNER_EMAIL --password OWNER_CHOSEN_PASSWORD`.

Never place passwords in a spreadsheet or document. Upload media first, then run
`tara-catalog-prep prepare --input CLIENT.xlsx --dry-run`, generate the canonical YAML,
and import it using the existing catalog workflow.
