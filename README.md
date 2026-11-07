# kobold

*kobo + alfred.* A small creature that hoards ebooks in your directories in properly arranged gleamy stacks.

## The problem

Imagine you have a big library of ebooks, which in the real world means a folder with unstructured subfolders like `New folder` and `To read 2027`. Lots of `epubs`, `fb2`, `pdfs` inside. Every time you want to read a book you have to find it first, and you don't want to waste time, so you go and download it again, optionally pushing it into the same heap. Sometimes you decide to make it neat and structured, move files around for a couple of hours, understand how hard it is to categorize real stuff, and then leave it as is until next time. No problem, I was there.

## The idea

You do not sort the library. You keep three places and let the tool move books between them:

- the **library** — where books arrive: a Calibre folder, Downloads, a backup drive. Kobold only reads it.
- the **vault** — the folder tree on your e-reader (or the folder that syncs with it): `genre / Author, Name / Series / Author - Title (Year).epub`. Kobold keeps it tidy.
- the **nook** — one folder on the e-reader with the handful of books you are reading right now. Nobody reads more than a few books at once; the nook is where they wait.

Everything else is search. Type `kb` in Alfred, see the newest books across all three places with their covers; press ↩ on one and it comes to the nook — copied from the library, or moved out of the vault. Read it. Then `kb done`, ↩, and it is filed into the vault under its genre and author.

## Demo

```
kb delany epub     →  Dhalgren   vault · Samuel R. Delany · 1975 · EPUB 1.2 MB   ↩ to the nook
kb lib heinlein    →  every Heinlein the library has that the device lacks · Import all N copies them
kb nook            →  the books you are reading · ↩ opens one
kb done            →  the nook books with a genre and an author · Finish all 3 · ↩ on one files it into the vault
kb fix             →  Apply N · every vault book to its genre/author home, weaker formats and junk to the trash
kb tag             →  books without a genre · ⌘↩ on any book opens the genre picker
kb retag pohl      →  every Pohl with its genre · Retag all N picks one genre for them all
kb std             →  Delany, Samuel R. ← S. R. Delany · one spelling per writer and per genre
```

## Install (three minutes)

1. Grab `Kobold.alfredworkflow` from [Releases](https://github.com/vlnn/kobold/releases) (every push to `main` publishes a `latest` build) and double-click it.
2. In the workflow's configuration set **Device root** to the folder that is, or syncs with, your e-reader, e.g. `~/Books/kobo` (a Syncthing folder) or `/Volumes/Transcend/kobo` (the card itself). Set **Library folders** to where your books arrive, `~/Calibre Library:~/Downloads`, paths separated by `:`.
3. Type `kb update` ↩. The index is built in the background; `kb` shows *Updating the index… · N of M checked* until it is done. From then on the index refreshes itself: a `kb` typed more than ten minutes after the last update starts another in the background, so books that arrived since show up on their own.

Nothing to install: the workflow bundles `kobold` and [hoard](https://github.com/vlnn/hoard), the library it is built on, and runs on macOS's own `/usr/bin/python3` (3.9+), no dependencies.

If your device root is on a removable volume and `kb` says *Not reachable* while it is mounted, give Alfred access to **Removable Volumes** (System Settings → Privacy & Security → Files and Folders), then `kb update` again.

## Search

Every word you type must match, by prefix, the title, the authors, the series, the year, the format or a genre you set. Case and diacritics are ignored.

```
kb dhalgren              one book
kb delany                everything by Delany
kb delany epub           …only the epubs
kb delany 1975           author + year
kb                       newest books first, books without a cover after
```

A book that exists in several places is one row, shown at its nearest place: nook, then vault, then library. The subtitle starts with the book's genre, the one you set or else the one its vault folder gives it, then says where it is and where else it is: `fiction/sci-fi · vault +library · Samuel R. Delany · 1975 · EPUB 1.2 MB`. A nook book also says how far KOReader got, `nook · 73%`, or `finished` or `abandoned` once you closed it that way, so `kb nook` and `kb done` show which books are through. The icon is the cover embedded in an epub or fb2. Lists show the first 40 matches, so add a word if what you want isn't there.

These keys mean the same thing on every book row:

| Key | Does |
| --- | --- |
| ⇧↩ | open the book |
| ⌥↩ | reveal it in Finder |
| ⌘↩ | set its genre (opens the genre picker) |
| ⌃↩ | books like it (`kb like`) |
| ⌘Y | Quick Look |
| ⌘C | copy its path |
| ⌘L | large type |

↩ belongs to the command that listed the row. In a plain `kb` search it follows the place: a library book is copied into the nook, a vault book is moved there, a nook book opens.

## Commands

A first word that names a command replaces the search with its list. Words after the command narrow its list, as in a search.

| Typed | Lists | ↩ on a book | Head row |
| --- | --- | --- | --- |
| `kb <words>` | every place, books with a cover first, newest first | by place: to the nook, or open | — |
| `kb nook` | the nook | open | — |
| `kb done` / `finish` | the nook | file it into the vault, or pick its genre first | Finish all N |
| `kb lib` / `import` | library books the device lacks | copy into the nook | Import all N |
| `kb remove` / `trash` | device books the library still holds, and unfinished downloads | to the trash | Remove all N |
| `kb fix [words]` | what tidying the device would do, one step per row | that step alone | Apply N · Empty the trash |
| `kb stamp [words]` | tagged books on the device whose file lacks their genre | write its genre into the file | Stamp all N |
| `kb tag [words]` | books without a genre | the genre picker | Tag all N · Accept N suggested |
| `kb retag <words>` | every matching book, with its genre | the genre picker | Retag all N |
| `kb name [words]` | the model's unsure titles and authors | accept it | Accept N |
| `kb std [words]` | author and genre spellings that look like one | make it the standard | Accept N |
| `kb like [words]` | neighbours of the first match, or of the book KOReader opened last | by place, as `kb` | — |
| `kb rnd` | ten random books | by place, as `kb` | — |
| `kb stats` | counts per place and when each was last read | — | — |
| `kb undo` | the last batch | undo it | — |
| `kb update` | — | read every place again, in the background | — |
| `kb model` | what each model server serves | use that model | — |

`kb remove` only sets aside books the library still holds, and unfinished downloads; the only copy of a book stays on the device. Nothing is deleted until you say so: the trash is a hidden `.hoard-trash/` folder at the device root, which the Kobo and KOReader never list, and **Empty the trash** under `kb fix` is the one action that cannot be undone.

## Walkthrough 1: read a book

```
kb dhalgren              Dhalgren   library · Samuel R. Delany · 1975 · EPUB 1.2 MB
   ↩                     To the nook: Dhalgren
kb nook                  Dhalgren   nook +library · Samuel R. Delany · 1975 · EPUB 1.2 MB
```

The copy arrives in the nook under its canonical name, `Delany, Samuel R. - Dhalgren (1975).epub`; the library keeps its file. If the book has no genre yet, Alfred comes back with the genre picker, the suggested genre first; Esc keeps the book untagged for now. Read it on the device. When you are through:

```
kb done
   ↩ on Dhalgren         Finish: Dhalgren
```

and it is in `01_Fiction/02_Sci-Fi/Delany, Samuel R./`. A nook book without a genre reads *needs a genre* (or `fiction/sci-fi?` when kobold has a guess) and ↩ on it in `kb done` opens the picker instead of moving it; **Finish all N** files every book that has a genre and an author and hands the one without a genre to the picker, or several to `kb tag`. A book without an author stays until `kb name` or the model gives it one.

## Walkthrough 2: tidy the vault

`kb fix` lists what tidying the device would do, one row per step with its reason — `Delany, Samuel R - Dhalgren (1975).epub · relocate + rename · from dhalgren.epub` — under **Apply N**. ↩ on that row runs them all; ↩ on one row runs that step alone; words after `fix` narrow the list to matching books. The steps:

- every vault book with a genre and an author moves to its home, `genre / Author / Series / canonical name`. The nook is never touched: books there are being read;
- of several copies of a title the best stays (the nook copy, then complete, in a genre folder, epub > fb2 > mobi > azw3 > azw > pdf > djvu, newest, largest) and the rest go to `_dups/` inside the trash, mirroring their path;
- identical copies and files that are not books (`FSCK*`, `.zip`, `.txt`, empty folders) go to the trash, mirroring their path.

The trash is `.hoard-trash/` at the device root: hidden, so the Kobo and KOReader stop listing what went there at once, and still on the card, so `kb undo` brings it back. When nothing is left to fix, `kb fix` shows **Empty the trash** with what it holds; that is the only step that cannot be undone. In Finder, ⌘⇧. shows hidden folders if you would rather look first. `uv run python -m hoard kobold plan` prints the steps from a terminal without moving anything.

"Identical" and "already on the device" mean the same text: for epubs the fingerprint is a hash of the book's text files only, so two copies with different covers or metadata still count as one book. Other formats are hashed whole.

Every batch, from `kb fix`, `kb done`, an import, `kb remove` or a genre, is one entry in the journal, and `kb undo` reverses the most recent one; undoing an import deletes the copy, the library still has the book. When a move finds a byte-identical file already at the destination, the redundant source is removed instead of moved; undo restores it from the kept copy. Folders left empty are pruned, and case-only and accent-only renames happen in place.

## Walkthrough 3: genres

Genres are how the vault is laid out: the first two folder levels with their order prefixes stripped (`01_Fiction/02_Sci-Fi_Fantasy/…` → `fiction/sci-fi_fantasy`). A vault book has the genre of its folder until you give it one.

The picker offers the genres found in the vault and the ones listed under **Genres** in the workflow configuration, one per line in the same `fiction/sci-fi` form. A new device has no genre folders yet, so list the genres you want there and `kb tag` and the picker have them from the first book; folders appear as books are filed.

- ⌘↩ on any book row opens the picker: the vault's genres, the suggested one first if there is one. Type to narrow them, or to create a new genre.
- `kb tag` lists books without a genre you set; **Tag all N** picks one genre for the whole list.
- `kb retag <words>` lists every book the words match, tagged or not, **Retag all N** gives them all one genre in a single undoable batch. Tagged the wrong genre to every Pohl? `kb retag pohl`, ↩ on the head row, pick the right one.

Only genres you set are searchable; a folder genre is not, so `kb sci-fi` finds the books you tagged `fiction/sci-fi`.

### Suggested genres

Most books say what they are, in `dc:subject` lines or fb2 `<genre>` codes, and every update proposes a genre for each book that has none: `fiction/sci-fi? 80%` in `kb tag`, first in the picker, **Accept N suggested** takes them all. Proposals come from the shelf a book left, from your own picks, and from a built-in table; `kb done` writes the genre into the file so KOReader's genre menu sees it. [docs/genres.md](docs/genres.md) has the rules and the percentages.

## One name per writer, one name per genre

Libraries spell the same writer several ways (`Samuel R. Delany`, `Delany, Samuel R.`, `S. R. Delany`) and genres drift the same way. Every `kb update` finds such spellings, applies the safe merges on its own (case, order, accents, `ё`/`е`) and leaves the rest in `kb std` for **Accept N**. No model is needed. [docs/spellings.md](docs/spellings.md) says what merges, what waits and what never does.

## Books like this

`kb like dhalgren` lists the books that read most like it, by authors, series, genre, decade and shared vocabulary; `kb like` alone starts from the book KOReader opened last, and ⌃↩ on any row does the same for that book. No model is needed. [docs/likeness.md](docs/likeness.md).

## A local model, if you run one

Everything above works with no model. With llama.cpp's `llama-server` on the Mac, `kb tag` can ask it for a genre and `kb name` for a real title and author for a file named `7_815203.epub`. The model never moves a file. Set **Chat model server** in the workflow configuration; [docs/model.md](docs/model.md) has the settings, what the model sees, and how to run the server.

## KOReader users

Reading progress comes from each book's `.sdr` sidecar, and every move carries the sidecar along and rewrites KOReader's history, collections and bookmarks, so nothing is lost on `kb done` or undo. [docs/koreader.md](docs/koreader.md) says what has to live under the device root for that to work.

## Under the hood

How the vault tree is read (genre → author → series), where the index and the rules live, upgrading from 0.5, and the same commands from a terminal: [docs/internals.md](docs/internals.md).

## When something looks off

| You see | Do |
| --- | --- |
| *Index is empty* | ↩ on that row, or `kb update` |
| *No folder set for nook* | set **Device root** in the workflow configuration |
| *Not reachable: …* | the folder is not there right now: mount the volume, or grant Alfred Removable Volumes access |
| *Updating the index… · counting files* | the update is listing the files it will read; the count follows |
| *Asking the model… · N of M asked* | the chat model is answering for every book it has not seen, one at a time; **Ask and embed on update** starts this after each update |
| *Embedding… · N of M embedded* | an update is working out `kb like` for new books; usually well under a minute |
| *Nothing to finish*, yet `kb nook` is full | those books have no genre or no author yet: ⌘↩ on them in `kb nook` or `kb tag` to give them a genre |
| *Remove: nothing to do* | `kb remove` keeps the only copy of a book; import it into the library first, or delete by hand |
| *Chat server not reachable* | start `llama-server`, or fix **Chat model server**; `kb model` shows whether it answers |
| an update or a model pass seems to do nothing | read `worker.log` in the cache folder |
| anything else | `make doctor` in a checkout, or `python3 hoard.py doctor` in the installed workflow's folder |

## Development

```
uv run pytest
uv run ruff check && uv run ruff format --check
uv run --python 3.13 python -m hoard.build --check   → dist/kobold.alfredworkflow, answering an empty query
make link                                             → a workflow in Alfred symlinked to this checkout
make test-system                                      → the suite on /usr/bin/python3, as the workflow runs
```

Two Pythons: the workflow *runs* on macOS's `/usr/bin/python3` (3.9), so the code and `uv run pytest` stay 3.9-clean and CI tests both ends. The *build* reads `workflow/plist.toml` with `tomllib` in hoard, which is 3.11+, so `make build` and `make check` need `uv run --python 3.13` and cannot run on the system Python. Lifting that is a `tomli` fallback in hoard, not here.

hoard is pinned to a tag in `pyproject.toml`. To work on both, keep a hoard checkout next to this one and add `--with-editable ../hoard` to any of the commands above, e.g. `uv run --with-editable ../hoard pytest`. To move to a newer hoard, change the tag and run `uv lock`.

`docs/history/` keeps the 0.5 design notes, from before hoard, for the reasoning; the README is the current interface.
