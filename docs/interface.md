# The interface

What the workflow does, in one page. `plan.md` says how it was built.

## Three places

- **library** — the folders where books arrive (`KOBOLD_SOURCES`: Calibre, Downloads…). Never touched; only read and copied from.
- **vault** — the device tree, `genre / Author, Name / Series / Author - Title (Year).ext`, kept tidy by `kb fix`.
- **nook** — one folder on the device (any top-level folder whose name is `nook` after the order prefix; `Nook/` is created when there is none) holding the handful of books being read right now.

One index (`books.db`) holds every place; a book that exists in several places is one row, shown at its nearest place (nook > vault > library) with the others noted. Genres live in `catalogue.tsv` at the device root, a plain file the reader may edit.

## Rows

Every book row reads `title` over `place · authors · series #n · year · FORMAT size · path`; a book held elsewhere too says so (`vault +library`). A nook book wears its cover in a green frame. Four keys mean the same thing on every row:

| Key | Does |
| --- | --- |
| ⇧↩ | open the book |
| ⌥↩ | reveal it in Finder |
| ⌃↩ | books like it (`kb like`) |
| ⌘↩ | set its genre (the picker) |

↩ belongs to the command that listed the row.

## Commands and ↩

| Typed | Lists | ↩ on a book | Head rows |
| --- | --- | --- | --- |
| `kb <words>` | every place folded, newest first | by place: library → copy into the nook, vault → move to the nook, nook → open | count of unclassified books |
| `kb nook` | the nook | open | how many books the nook holds (a nudge above 7) |
| `kb done` / `finish` | the nook | move to its home in the vault | Finish all N · Remove instead (to `_trash/`, only books the library still holds) |
| `kb lib` / `import`, `kbi` | library books the device lacks | copy into the nook | Import all N |
| `kb like [words]` | neighbours of the first match (or the book KOReader opened last) | by place, as `kb` | Embed N new books |
| `kb fix` / `tidy` | the plan: moves, junk, duplicates; conflicts; catalogue lines naming no book | apply that one | Fix all N · Undo last batch · Ask the model · reminders |
| `kb classify [words]` | books without a genre (or any matching the words) | the genre picker | Set genre for all N · Accept N suggested genres · Ask the model |
| `kb remove` / `trash [words]` | unfinished downloads; with words, matching device books | to `_trash/` | Remove all N |
| `kb rnd [words]` | five random books | by place, as `kb` | — |
| `kb stats` | counts per place, pending fixes, sources, embeddings | completes to the command | — |
| `kb update` | — | rebuild the index in the background | — |
| `kb model` | the model server's models | choose what it is for | — |
| `kb catalogue` | — | open `catalogue.tsv` | — |

Two letters and ↩ complete a command. Words after a command narrow its list, as in a search.

## Actions

Each row carries `variables.action`; the dispatcher has one branch per action, the runner one case per background action:

| action | reaches |
| --- | --- |
| `nook`, `done`, `import`, `remove`, `fix`, `undo`, `update`, `genre`, `ask`, `embed` | the runner, in the background, then a notification |
| `classify` | the genre picker |
| `model` | the model chooser |
| `reveal` | Finder |
| anything else | opens the file in `arg` |

## From a terminal

```
kobold update · search <words> · nook <refs> · done <refs> · remove <refs> · import <paths>
kobold genre <refs> <genre> · genres <typed> · fix [--dry-run] [targets] · undo
kobold ask [genre|name] [words] · embed [words] · models · choose <role> <model> · chooser · catalogue
```

A `ref` is an absolute path on the device or a fingerprint; several come one per line.
