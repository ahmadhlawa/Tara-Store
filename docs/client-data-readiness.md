# Tara client-data readiness

Development is ready for real client data. Tara starts clean; no preview purge is needed
unless a future preview batch is explicitly imported.

Provide:

- completed [catalog spreadsheet template](client-templates/tara-store-catalog-template.xlsx), including categories, products, options, variants, packages, prices and stock;
- product/category images named exactly as the spreadsheet references;
- currency confirmation, delivery areas and prices;
- store contact details, WhatsApp and social links;
- policy/static-page content and final hero/banner assets/content;
- real administrator name and email. Create its password locally with:
  `python -m app.initial_data --email OWNER_EMAIL --password OWNER_CHOSEN_PASSWORD`.

Never place passwords in a spreadsheet or document. Upload media first, then run
`tara-catalog-prep prepare --input CLIENT.xlsx --dry-run`, generate the canonical YAML,
and import it using the existing catalog workflow.
