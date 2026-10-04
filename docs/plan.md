# Implementation plan for the new interface

Companion to `interface.md`, which says what the workflow should do. This says in what order to build it, what each step deletes, and what stays green. Every step ends with `uv run pytest` passing and `./build.sh` producing a workflow you could use that evening; no step leaves the tool half-migrated.

## What is kept untouched

`metadata.py`, `filenames.py`, `cyrillic.py`, `naming.py`, `identity.py`, `languages.py`, `covers.py`, `scan.py`, `apply.py`, `koreader.py`, `history.py`, `oracle.py`, `evidence.py`, `suggestions.py`, `vectors.py`, `embedder.py`, `store.py`, `model.py` and their tests. These are the parts that took effort and that the design does not change. If a step needs to edit one of them, the step is wrong or the design is incomplete; stop and say which.

## What is cut

Not carried across to the new top layer. Each is removed in the step named, with its tests, and nothing is written to keep it alive in between.

- **The inbox and `kb inbox`** (step 3). Books arrive in the library, not on the device. An unclassified device book is a vault book without a genre; it shows in `kb fix` and `kb classify`, not in a folder of its own. `inbox_folder`, `import_blocked`'s inbox destination, `inbox_note`, `UNCLASSIFIED_FOLDERS` keeps `inbox` only so old trees still index.
- **Filename lint: noisy, opaque, double extension, author inversion** (step 3). They flagged bad names on the device; nothing reaches the device under a bad name any more, and the library is allowed to be a mess. `lint.py` keeps `junk`, `exact_duplicates` and `title_duplicates`. `fix` loses its rows-with-no-verb category and `MANUAL_RULES`.
- **Suggested renames from the `name` question** (step 3). The answer corrects the index row — title, authors, and so the canonical name used when the book is copied in — instead of producing a move. Goes: `suggested_renames`, `renamed`, `confident_names`, the per-book dismiss flow, forgetting a `name` answer on apply. Stays: the question itself, `evidence.py`, `oracle.name_of`.
- **Author merges and `aliases.tsv`** (step 3). The `authors` question, `asking.py`'s author pass, `authors.py`, `evidence.author_samples`, `obvious_groups`, `learn_aliases`/`unlearn_aliases`, merge rows in `fix`, `kobold ask authors --embed-dry-run`, the `authors` branch of `kobold ask`. `naming.author_folder` drops its `aliases` argument; `Shelves` keeps only known folders. Two author folders for one person become a plain `fix` finding with a manual rename, if ever.

## What is replaced

`commands.py`, `alfred.py`, `cli.py`, `workflow/info.plist`, and their tests (`test_commands`, `test_alfred`, `test_cli`, `test_workflow`). Written fresh against `interface.md`, not patched. `index.py` keeps its FTS and row code and loses the second index. `vault.py`, `library.py`, `nook.py` fold into one `places.py` once there is one index. `genres.py` becomes the catalogue.

## Steps

### 1. One index, one `place` column

- `Row` gains `place: str` — `nook`, `vault`, `library` — derived at index time from root and first path part. `inbox` is not a place; an unclassified device book is a vault book without a genre.
- `build_index(device_root, library_dirs)` writes one `device.db`… renamed `books.db`. Device rows keep `root = device_root`; library rows keep their folder's parent as today. `library.db` is adopted once and deleted.
- `Index.search(words, places=None)` filters by place when asked. `Index.fold()` collapses rows by fingerprint, keeping the nearest place (nook > vault > library) and recording the others as `copies`.
- `kb update` is one build; `kb stats` reads counts from one table.
- Tests: `test_index` grows place and fold tests; `test_library`'s index tests move there. Nothing user-visible changes yet except the single notification.

Deletes: `build_library_index`, `library_records`, `library_db_path`, `library_index`, `not_on_device`, `fingerprints_among`.

### 2. The catalogue

- `genres.tsv` becomes `catalogue.tsv`: `genre  authors  title  year  path  fingerprint`, header line, sorted genre → author → title. Location is a setting, device root by default, data folder as fallback. The old file is converted on first run.
- `CatalogueStore` keeps `TsvStore`'s read/write and adds `merge(disk, known) -> Changes`: genre changed, line removed, line added by path. It is called whenever the file's mtime is newer than the one kobold last wrote; the changes become one journaled batch and a notification. Unmatched lines are kept and surface in `kb fix`.
- `kb catalogue` opens the file.
- Tests: `test_genres` becomes `test_catalogue`: format, sort, round trip, each kind of edit, an unmatched line, a conflict (kobold and the user both changed a genre; the user wins).

Deletes: nothing yet; `GenreStore` is renamed, its interface stays until step 4.

### 3. Operations as one module

- `places.py`: `to_nook(rows)`, `to_vault(rows)` (today's `rehome` and `done`), `remove(rows)` (to `_trash/`, only when a library copy exists), `copy_in(row)` (library → nook), `classify(rows, genre)`. Each returns `Applied` and refreshes the index; each is one journaled batch.
- `plan.py` learns `place`: `desired()` covers vault rows only; junk and duplicates cover the device only; library rows are never in an operation.
- The cuts above land here: `lint.py` down to junk and duplicates, `asking.py` down to the genre pass plus `name` as an index correction (`Index.correct(fingerprint, title, authors)` on a confident answer), `authors.py` and `aliases.tsv` gone, `naming` without aliases.
- Tests: `test_nook` and the operation halves of `test_library` become `test_places`; `test_lint`, `test_asking`, `test_naming`, `test_plan` lose the cut cases; `test_authors` goes.

Deletes: `vault.py`, `library.py`, `nook.py`, `authors.py`, `inbox_folder`, `import_blocked`, `transfer`, `rehome`, `suggested_operations` and everything under it, the inbox as a destination.

### 4. The new top layer

Written from the design, in this order, each with its tests before its code:

1. `alfred.py`: `book_item(row)` with the place subtitle and the green-framed cover; the fixed modifiers ⇧↩ open, ⌥↩ folder, ⌃↩ like, ⌘↩ picker; ↩ left to the command through `variables.action`. Head rows: count, Import all, Fix all, Undo, Remove instead.
2. `cli.py`: `update`, `search`, `nook`, `done`, `remove`, `import`, `genre`, `genres`, `fix`, `undo`, `ask` (genre and name only), `embed`, `models`, `choose`, `chooser`, `catalogue`. Thin: resolve references, call `places`, print one line.
3. `commands.py`: `kb`, `nook`, `done`/`finish`, `lib`/`import`, `like`, `fix`/`tidy`, `rnd`, `stats`, `update`, `model`, `catalogue`; each a `Command` with its own ↩ action. Bare `kb` is the folded search, newest first.
4. `info.plist`: `kb` and `kbi`, the dispatcher with one branch per action, the runner, the picker, ⌃ and ⌘ connections.
5. `test_workflow`: every declared modifier reaches what its subtitle says, every action has a runner branch, every command's ↩ lands where the table in `interface.md` says.

The old modules are deleted at the start of this step, not the end, so the test suite tells you what is missing.

### 5. Green frame and `like` everywhere

- `covers.py` gains `framed(cover_path) -> Path`: the same PNG with a 3-px green border, cached beside it. Only the row builder decides which one to show; the index stores the plain one.
- `vectors.py` already keys by fingerprint; `kb like` and ⌃↩ search the folded index, so library books appear as neighbours. Embedding on update covers library rows too, behind the existing setting.

### 6. Docs and release

- README rewritten from `interface.md`; `docs/oracle.md` updated for the single index and the two remaining questions; upgrade notes: `KOBOLD_ROOT`/`KOBOLD_SOURCES` still read, `library.db` + `sources.db` → `books.db`, `genres.tsv` → `catalogue.tsv`, `authors.tsv` ignored (aliases already applied to folders stay as they are).
- Version 0.5.0. Tag.

## Order and why

1 before everything because the fold is what makes "one search" and "vault copy found first" true, and every command reads through it. 2 before 4 because the picker and `done` need the catalogue's merge to exist, not the old store. 3 before 4 so the new top layer never imports the old orchestration. 5 is cosmetic and can slip. Steps 1–3 can land on the current `main` one at a time; step 4 is the one that should be a branch, because it deletes the old interface in its first commit.

## Decisions still open

- Catalogue location when the device is unmounted: fall back to the data folder silently, or refuse to classify until the device is back? The plan assumes fallback with a note in `kb stats`.
- Whether `kb` bare shows all places folded (plan) or library only (simpler, loses "vault found first" for the empty query).
- Nook capacity: nudge only (plan) or a swap prompt at the limit.
