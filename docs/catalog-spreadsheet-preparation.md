# Catalog spreadsheet preparation

How a client's product spreadsheet becomes a Vista catalog.

```
client workbook (.xlsx)                 client images
        │                                     │
        │                                     ▼
        │                          uploaded to the Media Library first
        ▼
vista-catalog-prep prepare  ──►  canonical dataset YAML
        │                                     │
   validates, resolves every                  ▼
   filename, writes no DB row       vista-preview seed  ──►  database
```

Two commands, deliberately. Preparation reads a spreadsheet and writes a file.
Importing reads that file and writes the database. Nothing in the preparation step can
create, change or delete a product, a category, a media asset or an order.

## Before you start: upload the images

The spreadsheet references pictures **by filename**, never by URL. Those files must
already exist in the Media Library (Admin → Media), because the tool resolves each name
against `media_assets.original_filename`:

* no match → error;
* more than one match → error, and it never picks between duplicates;
* matching is case-sensitive: `VST-1001-01.jpg` is not `vst-1001-01.jpg`.

Recommended client naming, `<SKU>-<POSITION>.<ext>`:

```
VST-1001-01.jpg   VST-1001-02.jpg   VST-1001-03.jpg
```

That is a convention for humans, not a parser rule — the tool uses whatever the cell says.

Imported products point at the owner's existing media. The import batch does **not** own
those assets, so purging the batch removes its products and categories and leaves every
uploaded file exactly where it was.

## The workbook

The blank template to send the client lives at
`docs/client-templates/vista-store-catalog-template.xlsx` — Arabic instructions, dropdowns
and example sheets included. Regenerate it with
`python ../docs/client-templates/generate_catalog_template.py`.

One `.xlsx` file with a `products` sheet and a `categories` sheet. (A directory holding
`products.csv` and `categories.csv` works too — pass the directory.) Column headers are
matched case-insensitively, and spaces become underscores: `Compare At Price` is
`compare_at_price`.

### `products`

| Column | Required | Notes |
| --- | --- | --- |
| `name` | yes | |
| `category_slug` *or* `category_name` | yes | must exist in the `categories` sheet |
| `price` | yes | greater than zero |
| `sku` | no | must be unique; how packages refer to this row |
| `product_type` | no | `standard`, `package`, … (default `standard`) |
| `compare_at_price` | no | must be **above** `price` |
| `cost_price`, `stock_quantity`, `low_stock_threshold`, `track_inventory` | no | |
| `short_description`, `description` | no | |
| `is_active`, `is_featured`, `is_new`, `is_bestseller` | no | |
| `sort_order` | no | defaults to spreadsheet order |
| `seo_title`, `seo_description` | no | derived from the name when blank |
| `slug` | no | only needed when a slug cannot be derived (see below) |
| `image_1` … `image_n` | no | filenames; **`image_1` is the cover** |
| `spec_1_name` / `spec_1_value`, … | no | numbered pairs, no fixed limit |
| `option_1_name` / `option_1_values`, … | no | values separated by `,` `،` or `|` |
| `package_items` | packages only | `VST-1001 x2; VST-1005` |

**Image order is meaning.** `image_1` becomes `sort_order` 0, which is what the storefront
shows as the cover; `image_2` is the hover image. Blank image columns are skipped, not
padded, so `image_1` + `image_3` gives a two-picture gallery in that order.

**Options, not variants.** Option columns create the choice axes (Colour: Red, White). A
priced variant matrix — per-combination SKU, price override, stock — is not expressible in
a flat sheet and stays a manual Admin job.

### `categories`

| Column | Required | Notes |
| --- | --- | --- |
| `name` | yes | |
| `parent_name` *or* `parent_slug` | no | must be another row in this sheet |
| `description`, `image_filename`, `sort_order`, `is_featured`, `is_active` | no | |
| `slug` | no | see below |

### System-generated — never ask the client for these

Slugs, `search_text`, SEO fallbacks, image `sort_order`, database ids, and the media keys
in the generated YAML. Slugs are derived from the name (ASCII, lowercase, hyphenated),
falling back to the SKU. An Arabic-only name yields no ASCII slug, and the tool then asks
for an explicit `slug` column value rather than inventing one.

### Values

Booleans accept `true/false`, `yes/no`, `1/0`, `on/off`, `نعم/لا`, and real Excel
checkboxes. Numbers accept thousands separators and Arabic-Indic digits (`٩٩٠` → `990`).
Anything else is an error — no value is quietly reinterpreted.

## Dry run

From `backend/`:

```bash
python -m scripts.catalog_prep_cli prepare --input client-products.xlsx --dry-run
```

Parses the workbook, validates every field, resolves every filename against the Media
Library, prints counts, and writes nothing:

```
Workbook OK: client-products.xlsx
  categories           8
  products             42
  images referenced    118
  media resolved       118
  packages             4
  dataset hash         4b8344ec…
```

Errors name the sheet, the row and the column, and every bad row is reported, not just the
first:

```
products row 14: image_2 — 'VST-1012-02.jpg' was not found in the Media Library
products row 21: price — 'free' is not a number
```

## Generate the dataset

```bash
python -m scripts.catalog_prep_cli prepare \
  --input client-products.xlsx \
  --output ../instance/generated/client-catalog.yaml \
  --batch-key client-catalog \
  --source-label "Client catalog, 2026-08"
```

The output is deterministic: the same workbook against the same Media Library produces
byte-identical YAML, with no timestamps, absolute paths or database ids in it. Generated
catalogs are client data — keep them out of Git.

## Import it

The generated file is an ordinary dataset, so the existing importer takes it unchanged:

```bash
python -m scripts.preview_cli validate --dataset ../instance/generated/client-catalog.yaml
python -m scripts.preview_cli plan     --dataset ../instance/generated/client-catalog.yaml
python -m scripts.preview_cli seed     --dataset ../instance/generated/client-catalog.yaml
python -m scripts.preview_cli status   --dataset ../instance/generated/client-catalog.yaml
python -m scripts.preview_cli purge    --dataset ../instance/generated/client-catalog.yaml --confirm
```

`plan` shows what a seed would do without writing. Seeding is idempotent, an owner's later
edit in Admin is never overwritten, and a purge removes only what the batch created.

If the instance currently holds preview/demo content, the demo has to come out **before**
this import goes in — and some of it may be the client's by now. The full ordering, with
the step that promotes real content out of the demo batch first, is in
[client-data-cutover.md](client-data-cutover.md).

## Requirements

Reading `.xlsx` needs openpyxl, which is not part of a default install:

```bash
pip install -e .[catalog-prep]
```
