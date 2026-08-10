# Client data cutover

How a preview instance becomes the client's real store.

```
   inspect            decide              delete             load
      │                  │                  │                  │
tara-cutover       tara-cutover       tara-preview       tara-catalog-prep
    plan             preserve         purge --confirm     →  tara-preview seed
      │                  │                  │                  │
 read-only        explicit, targeted   destructive,        the existing
                                       confirmed           importer
```

Four separate operator actions, on purpose. No command in this repository both deletes
demo content and imports client content: every step stops and lets you look at the result
before the next one is run.

The whole procedure runs against **one instance database**. Nothing here touches a server.

Tara currently has no preview batch. For normal client onboarding, skip the preview-purge
steps and start with media upload; every preview command requires an explicit `--dataset PATH`.

---

## The problem this solves

The preview batch owns the rows it created — the demo catalog, the placeholder hero
slides, the banners, their pictures. `tara-preview purge --confirm` deletes exactly those
rows and nothing else, which is what makes the demo safe to load.

But over the life of a preview, something genuinely the client's can arrive *through* the
batch: a hero slide they approved, a banner that is their real artwork, an image the store
now depends on. The purge cannot tell the difference — as far as it knows, the batch made
it, so the batch takes it back.

So before the purge, you look at the list, and you promote by hand whatever turned out to
be real. Promotion drops the batch's *claim* on the row. The row, its id, its picture and
every reference to it stay exactly as they are; no later purge considers it again.

---

## 1. Back up first

Non-negotiable, and it must be the database **and** the media directory together — see
[backup-and-restore.md](backup-and-restore.md). The purge deletes stored image objects as
well as database rows.

```bash
cd backend
python -c "import sqlite3; s=sqlite3.connect('data/commerce_dev.db'); d=sqlite3.connect('data/pre-cutover.db'); s.backup(d); d.close(); s.close()"
cp -r data/uploads ../pre-cutover-uploads
```

## 2. Run the cutover plan

Read-only. It writes nothing and opens no transaction you have to think about.

```bash
cd backend
python -m scripts.client_cutover_cli plan --dataset path/to/preview.yaml
```

It reports:

| Group | Meaning |
| --- | --- |
| would delete | preview-owned records the purge will remove, counted by type |
| protected (edited) | preview rows the owner has since edited; the purge keeps them |
| refused (blocked) | rows the purge will not delete at all, `--force` or not |
| media removed | the image assets and objects that go with them |
| media kept at risk | preview-owned pictures that **surviving** content still displays |
| surviving | owner and system rows the batch never owned |
| bootstrap / commercial | store settings, pages, admins, orders, invoices |

Add `--json` for the machine-readable form.

`plan` exits `3` when there is anything in *refused* or *media at risk* — a signal to read
before continuing, not an error.

## 3. Review the delete list

Go through **would delete** and ask one question per row: *is this the client's, or is it
ours?* The plan prints the type, the natural key, the row id and the human-readable
name/title/filename, which is everything you need to find it in Admin.

Nothing is decided for you. The tool never promotes a record because of what it is called
or what it looks like.

## 4. Preserve what is genuinely the client's

Name each record exactly as `plan` printed it. Dry run first:

```bash
python -m scripts.client_cutover_cli preserve \
    --dataset path/to/preview.yaml \
    --target "hero_slide:عنوان الشريحة" \
    --target "banner:لافتة العميل"
```

Then apply:

```bash
python -m scripts.client_cutover_cli preserve \
    --dataset path/to/preview.yaml \
    --target "hero_slide:عنوان الشريحة" \
    --target "banner:لافتة العميل" \
    --confirm
```

### If the record has been renamed

`--target` finds a record by its natural key — the title or slug the batch recorded when
it created the row. Prefer it while it still matches. But the owner may have renamed the
record in Admin since, in which case the key in the plan is no longer the name you see,
and the row id printed beside it is the stable handle. Select by id instead:

```bash
python -m scripts.client_cutover_cli preserve \
    --dataset path/to/preview.yaml \
    --entity-type hero_slide \
    --entity-id 12 \
    --confirm
```

Both forms do exactly the same thing to exactly the same record. The id is read from the
`#12` that `plan` prints after each entry. `--entity-type` and `--entity-id` go together,
and cannot be combined with `--target` in one command — the tool refuses rather than
guesses. An id is always looked up within its own entity type, so a number belonging to
another table can never promote the wrong row.

### Notes on both forms

* The pictures a preserved record **displays** are promoted with it, so the slide does not
  survive pointing at a file the purge is about to remove. Use `--without-media` only if
  you have decided the picture should go.
* A media asset can also be named directly: `--target "media_asset:<key>"`.
* Re-running is safe: a record that is already promoted reports `already-unmanaged`.
* Each promotion is written to the audit log as `preview.preserve`.

Run `plan` again and confirm the preserved rows have left the delete list.

## 5. Purge dry run

The default mode of the existing purge. Same eligibility computation as the real thing,
zero writes:

```bash
python -m scripts.preview_cli purge --dataset path/to/preview.yaml
```

Read the `blocked` section. A picture still shown by surviving content is refused here,
not silently deleted — that refusal is what keeps working pages from turning into broken
images.

## 6. Run the confirmed purge

The destructive step. It deletes preview-owned rows and the storage objects the batch
uploaded, and nothing else.

```bash
python -m scripts.preview_cli purge --dataset path/to/preview.yaml --confirm
```

## 7. Verify the clean state

```bash
python -m scripts.client_cutover_cli verify
python -m scripts.client_cutover_cli plan --dataset path/to/preview.yaml
```

`verify` checks that instance metadata, store settings, static pages and home sections are
still there; that no import batch record points at a deleted row; that no content points at
an uploaded file that no longer exists; and that every order still resolves to its product
and delivery area. `plan` should now report the batch as absent.

## 8. Upload the client's real media

Admin → Media → upload. Multi-file selection is supported. Filenames must be unique — the
database enforces it — and they are what the spreadsheet will reference, so agree the
naming convention with the client first (`<SKU>-<POSITION>.<ext>` works well).

Images must be uploaded **before** the next step: catalog preparation resolves every
filename against `media_assets.original_filename` and fails loudly on a name it cannot
find.

## 9. Validate the client spreadsheet

Read-only, writes no file and no database row:

```bash
python -m scripts.catalog_prep_cli prepare --input ../instance/client/client-products.xlsx --dry-run
```

Fix the workbook and re-run until it is clean. Details and the column contract are in
[catalog-spreadsheet-preparation.md](catalog-spreadsheet-preparation.md).

## 10. Generate the canonical YAML

```bash
python -m scripts.catalog_prep_cli prepare \
    --input ../instance/client/client-products.xlsx \
    --output ../instance/generated/client-catalog.yaml
```

Still no database row is written. Validate the result on its own:

```bash
python -m scripts.preview_cli validate --dataset ../instance/generated/client-catalog.yaml
```

## 11. Import with the existing importer

Plan first — it writes nothing and shows exactly which rows would be created:

```bash
python -m scripts.preview_cli plan --dataset ../instance/generated/client-catalog.yaml
python -m scripts.preview_cli seed --dataset ../instance/generated/client-catalog.yaml
```

The client catalog becomes its own import batch, with the same ownership and fingerprint
semantics: re-running is idempotent, an owner edit in Admin is never overwritten, and the
batch can be inspected with `tara-preview status`.

## 12. Verify the result

```bash
python -m scripts.preview_cli status --dataset ../instance/generated/client-catalog.yaml
python -m scripts.client_cutover_cli verify
```

Then confirm by eye in Admin and on the storefront:

* product, category and hero counts match the workbook;
* every product shows its cover image, in the order the spreadsheet gave;
* the preserved records from step 4 are still present and still show their pictures;
* no image is broken.

---

## Rules worth keeping in mind

* `plan` and `verify` are read-only. `preserve` writes only with `--confirm`, and only to
  the targets you named. `purge` is a dry run unless `--confirm`.
* Preservation is a promotion, not a copy. There is only ever one row.
* Ownership lives in `import_batch_records`; there is no second mechanism. Dropping the
  record is what "this is the owner's now" means.
* A picture referenced by any surviving row is refused by the purge, not deleted.
* Orders, order lines and invoices are never touched by any of these commands, and the
  purge refuses to delete a product or delivery area an order references.
