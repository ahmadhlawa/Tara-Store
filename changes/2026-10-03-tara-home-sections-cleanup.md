# Home Sections deployment cleanup review

Tara bootstrap and demo seed no longer supply default Home Sections. Existing rows
remain untouched; Admin CRUD and explicitly supplied generic profile sections remain
supported. The backend `/home-showcases` compatibility endpoint remains available.

Before any later Production cleanup, review rows with `section_key` values
`categories`, `packages`, `molds`, `featured`, `new`, and `bestsellers`, plus demo keys
`new-and-best` and `workshop-note`. These are candidates, not deletion instructions.
Review each row's current content, visibility, configuration, and edit/history evidence
with the owner: matching a legacy key does not establish that it is unwanted.

Only separately approved rows may be disabled or removed during a deliberate later
cleanup. This task performs no Production cleanup, row deletion, or cleanup migration.
