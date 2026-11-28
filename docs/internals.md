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

## What a keystroke reads

Nothing on the device. Alfred runs `kb` afresh for every key, and a card or disk that has gone to sleep makes whoever asks it wait until it is awake, so the nook and the vault are declared to hoard as storages that sleep:

- **Where the nook and the vault folders are, and that they are reachable**, is what the last update recorded in the index, as long as that update reached all of them. An update that found the device missing records that too, and then every keystroke looks for it, so plugging it in shows at once; a missing device answers immediately.
- **Each nook book's progress, the vault's genre folders and KOReader's last book** (the seed of a bare `kb like`) are noted by every update in `seen.json` in the cache folder, and read from there while the device is left asleep. Clearing the cache leaves rows without progress until the next update.
- **The library folders** are looked at on every keystroke as before; they are on the Mac's own disk.

An update is the background one, started by `kb update` or by a `kb` typed more than ten minutes after the last, and the one that ends every ↩ that changes something: to the nook, `kb done`, `kb remove`, `kb fix`, undo. Those read the device as it is, and so does `kb fix` while it lists its plan.

Set the environment variable `KOBOLD_TIMING=1` in the workflow (the `[x]` panel) to see what was read and how long it took: every listing of the device root and every sidecar read prints a `kobold timing:` line, with a total when the run ends. Keystrokes print to Alfred's debugger, the background update to `worker.log`, where a first line of several seconds is the device waking up.

## The window

`workflow/kobold.alfredui/` is an Alfred UI bundle: `ui.json` and `components/` describe the window, and every event runs one script, `scripts/window`, which prints one JSON action for Alfred to apply. The script is a shim over `kobold.window`:

| Mode | Run by | Answers with |
| --- | --- | --- |
| `search <typed>` | opening the window, a pause in typing | the rows, the first one selected and shown in the pane, the shelf counts |
| `tick <typed> <selected> <fingerprint> <watch>` | the pulse, once a second while a job runs | the job bar; the rows only if they changed, keeping the selection |
| `act <key> <typed> <row> <back>` | ↩ and its modifiers, double-click | what `hoard.py act` would do, then the list it leads to and a line for the footer |
| `look <typed> <row>` | ⌘Y | nothing; hands the file to `qlmanage` |

The rows are hoard's own, from `api.filter`, so the window lists and does exactly what `kbc` does. Two things are layered on top:

- **Facts instead of a subtitle.** The window's kind is `KIND` with `subtitle` replaced by `kobold.facts.packed`, which returns the same facts as JSON behind a marker byte; `kobold.cells` turns them into a row's colours, bar and texts. Rows hoard writes itself (heads, fix steps, genre choices) have no marker and get a symbol.
- **Home.** An empty query asks hoard for a command that exists only for that call and keeps the wanted ids and the nook (`kobold.home`), then orders them: the nook books with progress first, a finished one with `done` as its ↩, then one timeline of openings and additions. KOReader's history is noted by every update in `seen.json`, like progress; the window's own openings are in `opened.json` in the data folder. The index knows which update first saw a book but not when that update ran, so `kobold.runs` notes each run's time in `runs.json` as the window meets it; a book of an untimed run, or of the first build, falls back to its file date.

The side pane follows the selection without a script: `actions/show-selected.json` copies the selected row's values into the pane. It is generated from `kobold.pane.PANE`, and a test fails when the two drift. `kobold.dashboard` builds the `stats` bars from the index; books finished per month are the `done` rows of hoard's journal, so they count what kobold filed and was not undone.

A verb's follow-up (`kb tag #<id> ` after ↩ on an untagged book) is shown in the window instead of reopening Alfred's search bar. The window passes `follow_up=` to `api.act` (hoard 1.12) and takes the query from there.

Two races are closed in the script. Searches run in the background, so each claims a token in the cache folder before it looks and prints nothing if a newer search has claimed since: an answer to what is no longer typed never replaces the list. And only a tick stops the pulse, and not for five seconds after ↩ started a job (`watch`), so the worker has time to show up.

`workflow/assemble.py` builds what is released: hoard's bundle, plus the window bundle, a `kb` keyword that opens it, the old list moved to `kbc`, and every workflow setting exported to the window's scripts.

## Where things are

Alfred's workflow data folder, `~/Library/Application Support/Alfred/Workflow Data/com.anokhin.kobold`, holds `kobold.sqlite`: the index, your genres, the standard spellings, the model's answers and the last 300 exchanges with it, the vectors and the undo journal, `opened.json`: the books opened from the window, `runs.json`: when each update ran, and `kobold-rules.sqlite`: each book's subjects and the genre rules learned from your picks. Both survive workflow updates and cache clears. The cache folder, `~/Library/Caches/com.runningwithcrayons.Alfred/Workflow Data/com.anokhin.kobold`, holds the covers, `seen.json` and `worker.log`, where background updates and model passes write what went wrong.

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
