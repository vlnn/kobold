# Under the hood

How kobold reads a device, where its files live, and the same commands from a terminal.

## How it reads your folders

The vault tree is what the e-reader shows, so the tool keeps it meaning exactly one thing: **genre → author → series**.

- The vault is every top-level folder of the device root except the nook, hidden ones, and `_trash` and `_dups` left by kobold 0.7 (a move into the trash cleans them up). Books loose at the top of the device root are not read.
- Genre is the first two folder levels with their order prefixes stripped: `01_Fiction/02_Sci-Fi_Fantasy/…` → `fiction/sci-fi_fantasy`. A folder that looks like an author (`Surname, Given` or `Given Surname`) ends the genre early, so `programming/Dietrich, Erik/…` is genre `programming` with the author straight under it. Books under `inbox`, `archives`, `_inbox` or `_broken` have no genre from their folder.
- The nook is the top-level folder whose name is `nook` after the order prefix (`00_Nook`, `Nook`); when there is none, `Nook/` is created on the first import.
- Author folders are `Surname, Given`. An epub's `file-as` sort name and an fb2's name tags are taken as they are; a plain `Given Surname` string is split by rule, and for Cyrillic names the rule knows a few hundred given names, patronymics and surname endings, so `Роджер Желязни` and `Шевчук Валерій` both file under the surname. Existing folders win: if you already have `Le Guin, Ursula K.`, that spelling is reused.
- A series gets its own folder only when the vault holds more than one book of it.
- Canonical file name: `Surname, Given - Title (Series 03) (Year).epub`, FAT-safe, ≤ 255 bytes. A book is renamed to it when it is filed into the vault, tidied or copied into the nook, never where it lies.

Format support: epub and fb2 are read for metadata and cover; mobi, azw, azw3, pdf and djvu are described from their filename (libgen, Anna's Archive, `[Series №N]`, `Title - Author` and friends). `.part` files on the device are indexed as unfinished downloads, and only ever offered to `kb remove`. Library folders leave out unreadable and unfinished files.

## Where things are

Alfred's workflow data folder, `~/Library/Application Support/Alfred/Workflow Data/com.anokhin.kobold`, holds `kobold.sqlite`: the index, your genres, the standard spellings, the model's answers and the last 300 exchanges with it, the vectors and the undo journal, and `kobold-rules.sqlite`: each book's subjects and the genre rules learned from your picks. Both survive workflow updates and cache clears. The cache folder, `~/Library/Caches/com.runningwithcrayons.Alfred/Workflow Data/com.anokhin.kobold`, holds the covers and `worker.log`, where background updates and model passes write what went wrong.

**Upgrading from 0.5:** 0.6 is kobold rebuilt on hoard. **Device root** and **Library folders** carry over; the first `kb update` builds the new index. Not carried over: genres from `catalogue.tsv` (vault books get theirs from their folders again, nook books need one set), the model's answers and vectors, and the model settings, which are now **Chat model server**, **Embeddings server** and their keys. `books.db`, `oracle.tsv`, `oracle.log`, `vectors.db`, `journal.jsonl` and `covers/` in the data folder are no longer read; delete them when you like. Gone for now: `kb catalogue`, `kb classify` (use `kb tag`), the `kbi` keyword (use `kb lib`), searching by folder, path, subject or language, the green nook frame and pdf thumbnails.

## From a terminal

The workflow is hoard's command line with the kobold kind, so the same commands work in a checkout:

```
export KOBOLD_ROOT=/Volumes/Transcend/kobo
export KOBOLD_SOURCES="$HOME/Calibre Library:$HOME/Downloads"
export alfred_workflow_data="$HOME/Library/Application Support/Alfred/Workflow Data/com.anokhin.kobold"
export alfred_workflow_cache="$HOME/Library/Caches/com.runningwithcrayons.Alfred/Workflow Data/com.anokhin.kobold"
uv run python -m hoard kobold update
uv run python -m hoard kobold filter --text delany
uv run python -m hoard kobold plan                  kb fix's steps, nothing moved
uv run python -m hoard kobold ask name --dry-run    what the model would be sent
uv run python -m hoard kobold doctor                Python, SQLite, folders, settings and servers
```

`filter` without `--text` prints Alfred's JSON, whose `arg` is a book's fingerprint; `act <verb> <fingerprint>…` runs a verb on books, e.g. `act to_nook …`, `act done …`, `act undo`. Without the two `alfred_workflow_*` variables the terminal uses `~/.local/share/hoard/kobold`, a copy of its own.
