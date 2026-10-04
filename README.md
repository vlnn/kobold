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
kb delany epub            →  Dhalgren   vault · Delany, Samuel R. · 1975 · EPUB 1.2 MB · 01_Fiction/02_Sci-Fi/…   ↩ to the nook
kbi heinlein              →  every Heinlein the library has that the device lacks · ↩ copies one, Import all copies them
kb nook                   →  3 books in the nook · ⇧↩ opens one
kb done                   →  Finish all 3 books · Remove 3 books instead · ↩ on one files it into the vault
kb fix                    →  Fix all 14 · 9 moves · 4 to _trash · 1 to _dups · Undo last batch
kb catalogue              →  opens catalogue.tsv: genre, author, title, year, path — edit it, kb update applies it
```

## Install (three minutes)

1. Grab `Kobold.alfredworkflow` from [Releases](https://github.com/vlnn/kobold/releases) (every push to `main` publishes a `latest` build) or build it yourself with `./build.sh`. Double-click it.
2. In the workflow's configuration set **Device root** to the folder that is, or syncs with, your e-reader, e.g. `~/Books/kobo` (a Syncthing folder) or `/Volumes/Transcend/kobo` (the card itself). Set **Library folders** to where your books arrive, `~/Calibre Library:~/Downloads`, paths separated by `:`.
3. Type `kb update` ↩. A notification arrives when the index is built.

Nothing to install: the workflow bundles `kobold` and runs on macOS's own `/usr/bin/python3` (3.9+), no dependencies.

If your device root is on a removable volume and `kb` shows *Index is empty — is the device folder there?* while it is mounted, give Alfred access to **Removable Volumes** (System Settings → Privacy & Security → Files and Folders), then `kb update` again.

## Search

Every word you type must match, by prefix, one of: title, authors, series, series number, folder, path, genre, subjects (`dc:subject` in an epub, `genre` in an fb2), format, language (code or English name: `uk` and `ukrainian` both work), year. Case and diacritics are ignored.

```
kb dhalgren              one book
kb delany                everything by Delany
kb delany epub           …only the epubs
kb sci-fi 1975           genre + year
kb                       newest books first, after a count of books without a genre
```

A book that exists in several places is one row, shown at its nearest place: nook, then vault, then library. The subtitle says where it is and where else it is: `vault +library · Delany, Samuel R. · 1975 · EPUB 1.2 MB · 01_Fiction/…`. Nook books wear their cover in a green frame. The icon is the embedded cover for epub and fb2, a Quick Look thumbnail for pdf, and the plain file icon otherwise. Lists show the first 40 matches, so add a word if what you want isn't there.

Four keys mean the same thing on every book row, in every list:

| Key | Does |
| --- | --- |
| ⇧↩ | open the book |
| ⌥↩ | reveal it in Finder |
| ⌃↩ | books like it (`kb like`) |
| ⌘↩ | set its genre (opens the genre picker) |
| ⌘Y | Quick Look |
| ⌘C | copy the device-relative path |
| ⌘L | large type: title, author, path |

↩ belongs to the command that listed the row. In a plain `kb` search it follows the place: a library book is copied into the nook, a vault book is moved there, a nook book opens.

## Commands

A first word that names a command replaces the search with its list. Type two letters and ↩ to complete it. Words after the command narrow its list, as in a search.

| Typed | Lists | ↩ on a book | Head rows |
| --- | --- | --- | --- |
| `kb <words>` | every place, newest first | by place: to the nook, or open | books without a genre |
| `kb nook` | the nook | open | how many the nook holds (a nudge above 7) |
| `kb done` / `finish` | the nook | move to its home in the vault | Finish all N · Remove N instead |
| `kb lib` / `import`, `kbi` | library books the device lacks | copy into the nook | Import all N |
| `kb like [words]` | neighbours of the first match, or of the book KOReader opened last | by place, as `kb` | Embed N new books |
| `kb fix` / `tidy` | what is wrong on the device and how to fix it | apply that one | Fix all N · Undo last batch · Ask the model |
| `kb classify [words]` | books without a genre, or any matching the words | the genre picker | Set genre for all N · Accept N suggested genres |
| `kb remove` / `trash [words]` | unfinished downloads; with words, matching device books | to `_trash/` | Remove all N |
| `kb rnd [words]` | five random books | by place, as `kb` | — |
| `kb stats` | counts per place, chores, sources, embeddings | completes to the command | — |
| `kb update` | — | rebuild the index in the background | — |
| `kb model` | the model server's models | choose what it is for | — |
| `kb catalogue` | — | open `catalogue.tsv` | — |

`kb remove` only sets aside books the library still holds (and unfinished downloads); the only copy of a book stays on the device. Nothing is ever deleted: `_trash/` is a folder you empty yourself.

## Walkthrough 1: read a book

```
kb dhalgren              Dhalgren   library · Delany, Samuel R. · 1975 · EPUB 1.2 MB · Calibre Library/Samuel R. Delany/…
   ↩                     Imported Dhalgren → Nook/
kb nook                  1 book in the nook
                         Dhalgren   nook · … · Nook/Delany, Samuel R. - Dhalgren (1975).epub
```

The copy arrives under its canonical name; the library keeps its file. Read it on the device. When you are through:

```
kb done
   ↩ on Dhalgren         Dhalgren → 01_Fiction/02_Sci-Fi/Delany, Samuel R./
```

A book without a genre or an author has no home yet, so `kb done` says *stays put* and leaves it in the nook: give it a genre with ⌘↩ first. A book you do not want on the device at all: `kb done`, then **Remove N instead**, or `kb remove dhalgren` — it goes to `_trash/` because the library still has it.

## Walkthrough 2: tidy the vault

```
kb fix
```

The first rows are the plan:

```
Fix all 14                 9 moves · 4 to _trash · 1 to _dups
Undo last batch (6 moves)  (only after you've applied something)
3 books without a genre    ↩ lists them in kb classify
2 unfinished downloads     ↩ lists them in kb remove
Delany, Samuel R. - Nova (1968).epub       move · relocate + rename · 00_Inbox/nova.epub → 01_Fiction/02_Sci-Fi/Delany, Samuel R./
FSCK0001.REC                               trash · FSCK0001.REC: not a book · FSCK0001.REC → _trash/
Dhalgren.mobi                              dups · Dhalgren: epub, mobi · 01_Fiction/…/Dhalgren.mobi → _dups/01_Fiction/…/
⚠︎ Babel-17.epub                            skip · destination taken by 01_Fiction/02_Sci-Fi/Delany, Samuel R./Delany, Samuel R. - Babel-17 (1966).epub
nowhere.epub: no such book in the catalogue line      catalogue · games/go · ↩ opens the catalogue
```

- ↩ on a row applies that one operation; ↩ on **Fix all** applies them all. ⌥↩ reveals the file.
- `move` puts a vault book in its genre/author/series home with a canonical name. The nook is never touched: books there are being read.
- `trash` moves junk (`FSCK*`, `.zip`, `.txt`, any non-book file, empty folders, identical copies) to `_trash/`, mirroring its path. Dot-files, KOReader `.sdr` folders and `catalogue.tsv` are never junk.
- `dups` keeps the best copy of a title (the nook copy, then complete, in a genre folder, epub > fb2 > mobi > azw3 > azw > pdf > djvu, newest, largest) and moves the rest to `_dups/`.
- `⚠︎ skip` rows need you: the destination is already taken by another file.

"Identical" and "already on the device" mean the same text: for epubs the fingerprint is a hash of the book's text files only, so two copies with different covers or metadata still count as one book. Other formats are hashed whole.

Every batch is journaled, whether it came from `kb fix`, `kb done`, an import, setting a genre or `kb remove`; **Undo last batch** reverses the most recent one (and undo is itself a batch, so undoing twice re-applies; undoing an import deletes the copy, the library still has the book). `_trash/` and `_dups/` are never scanned, so an `rm -r` there is your decision alone.

The one deletion: when a move finds a byte-identical file already at the destination, the redundant source is removed instead of moved. That is journaled too, and undo restores it from the kept copy. Folders left empty are pruned; case-only and accent-only renames happen in place.

Dry run from a terminal: `kobold fix --dry-run` prints `kind	src	dst	reason`, one per line.

## Walkthrough 3: genres and the catalogue

Genres are how the vault is laid out: the first two folder levels with their order prefixes stripped (`01_Fiction/02_Sci-Fi_Fantasy/…` → `fiction/sci-fi_fantasy`). `kb update` gives every book in a genre folder that genre; books under `inbox`, `archives`, the nook, `_trash` and friends have none and are listed by `kb classify`.

Set a genre three ways:

- ⌘↩ on any book row opens the picker. Type to narrow the known genres; ⇧↩ creates the typed text as a new one. **Keep …** moves the book home without changing the genre.
- `kb classify` lists the books without one; ↩ opens the picker, **Set genre for all N** picks one genre for the whole list.
- Edit `catalogue.tsv`. `kb catalogue` opens it; it lives at the device root (so it syncs with the device; the index folder stands in while the device is away, and **Catalogue** in the configuration can put it anywhere). One line per book:

  ```
  genre	authors	title	year	path	fingerprint
  fiction/sci-fi	Delany, Samuel R.	Dhalgren	1975	01_Fiction/02_Sci-Fi/Delany, Samuel R./Delany, Samuel R. - Dhalgren (1975).epub	3f2a…
  ```

  sorted genre → author → title, so you can read it on the device or in a spreadsheet. Change a genre, delete a line (the book forgets its genre), or add a line with just a genre and a path (the book gets it). `kb update` — and `kb fix` — read the file, file the books accordingly in one undoable batch, and report `Catalogue: 1 genre changed, 2 lines added`. A line naming no book is kept and shown in `kb fix`. If you and kobold change the same line, your edit wins.

A vault book with a genre and an author is moved to its home at once (`Dhalgren → fiction/sci-fi · moved → 01_Fiction/02_Sci-Fi/Delany, Samuel R./`); a nook book keeps its place and gains the genre.

## Walkthrough 4: let a local model do the reading

Everything above works with no model. If you run [llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server` on the Mac, the workflow can propose answers to the two chores that still need a human per book — a genre for a new book, and a real title and author for a file named `7_815203.epub` — plus one view, *what else do I have like this*. The model never moves a file.

Set **Model server** in the workflow configuration to the server's URL (`http://127.0.0.1:8080`), then:

```
kb model                                      what the server serves · ✓ marks the current choices
   ↩ on a model → Use … for the oracle        writes the choice into the workflow configuration
kb classify                                   Ask the model about 12 unclassified books and 4 unnamed files · ↩ asks in the background
   …notification: Asked about 12 books: 9 genres suggested, 2 without an answer, 1 skipped
kb classify                                   Dhalgren   fiction/sci-fi? · …   ← the ? is a suggestion
   Accept 9 suggested genres                  ↩ files every listed book under its suggestion, one undoable batch
   ↩ on Dhalgren                              the picker lists the suggestion first
```

A confident answer to the name question corrects the book's title and author in the index — the row reads *Table Napkin Folding · Ivor Penhale* instead of *Napkin* — so search finds it, and when the book is filed or copied into the nook it gets its canonical name from the corrected row. The file is not touched before that. Corrections survive `kb update`.

What the model sees is the book's metadata, its `dc:subject`/`dc:description` (fb2: `genre`/`annotation`), the first two thousand characters of its text and, for a genre question, the list of known genres; `kobold ask --dry-run` prints exactly that. Every answer is constrained by a JSON schema, stored in `oracle.tsv` keyed by content fingerprint and the hash of the evidence, and kept until the evidence changes. Setting a genre forgets the genre answer. `oracle.log` keeps the last 500 exchanges for *why did it say that*.

Embeddings need a model made for them, served with `--embeddings`; the chat model that answers the questions cannot do it (the server answers 501 if asked). The usual setup is a second server on its own port, pointed at by **Embedding server**:

```sh
llama-server --hf-repo Geofront/BGE-M3-GGUF --hf-file BGE-M3-Q8_0.gguf \
  --embeddings --alias bge-m3 -c 2048 -b 2048 -ub 2048 -ngl 99 --port 8081
```

Any multilingual embedding model with a GGUF does; the batch sizes matter because an embedding model takes each input in one micro-batch, and the workflow sends up to 1 500 characters. If the server wants a key — `--api-key`, or `LLAMA_API_KEY` exported in the shell that started it — put it in **Model server API key**.

With an embedding model chosen too (**Use … for embeddings** in `kb model`), ↩ on *Embed N new books* in `kb model`, `kb stats` or `kb like` embeds every book — vault, nook and library, once per fingerprint — in the background, and then:

```
kb like dhalgren              Like Dhalgren                 vault · Delany, Samuel R. · 01_Fiction/02_Sci-Fi/…
                              Nova                          91% · library · Delany, Samuel R. · 1968 · EPUB 400 KB · …   ↩ copies it in
                              Babel-17                      88% · vault · …                                                  ↩ to the nook
kb like                       seed = the book KOReader opened last (history.lua), else the newest book
⌃↩ on any row                 the same list for that book
```

Vectors live in `vectors.db` keyed by model, so switching the embedding model keeps the old set until the new one is complete. Similarity is cosine over stored vectors, computed when a vector is stored, never while you type.

Turn on **Ask and embed on update** in the configuration and `kb update` does all of this by itself after indexing: the name and genre questions for books without an answer, and embedding for books without a vector — a notification per step, none when there is nothing new. Off by default, so indexing stays as fast as it is.

Nothing in the UI mentions the model until **Model server** is set; a server that does not answer shows as *Model not reachable at …* in `kb classify`, `kb fix` and `kb model`.

### Running llama-server

The workflow only needs an OpenAI-compatible `/v1/chat/completions` that honours `response_format` with a JSON schema; any recent `llama-server` does. Two ways to run it:

```sh
llama-server --hf-repo <org>/<model>-GGUF:Q4_K_M --alias oracle --jinja -c 8192 -ngl 99 --port 8080
```

serves one model; **Model** in `kb model` is then its alias. Or start the server with no model and a preset file, and it runs in *router mode*: every `[section]` is a model it can serve, loaded the first time a request names it:

```ini
[oracle]
hf-repo = <org>/<model>-GGUF:Q4_K_M
jinja = true
ctx-size = 8192
n-gpu-layers = 99
```

```sh
llama-server --port 8080 --models-preset ~/.config/llama.cpp/models.ini --models-max 2
```

Router mode is the comfortable one — swap models in `kb model` without restarting anything — with one thing to know: nothing is loaded until it is asked for. The first question after a start pays for loading the weights, and the very first time for downloading them into `~/.cache/llama.cpp`, which for a 20–30 B model is minutes to tens of minutes during which every request in the pass times out at 60 s and is counted as *skipped*. Wait for the download (the blob grows under `…/blobs/*.downloadInProgress`), or ask once from a terminal with `curl` before the pass, and ask again. `sleep-idle-seconds` in a preset unloads the model after that many idle seconds and brings the loading pause back on the next question; leave it out on a machine with the RAM, or expect one skipped book after each break.

Choices that matter for this workflow:

- **An instruct model, not a thinking one.** Answers are capped at 64 tokens for a genre and 256 for a title; a thinking model spends them inside `<think>` and the answer comes back empty. The workflow asks the template not to think, which the hybrid Qwen3 family respects, but a `-Thinking-` build ignores it.
- **`--jinja`.** Without it the chat template is approximated and the JSON-schema grammar fights the model more than it should.
- **Context of 8 k or so.** A question carries the book's metadata, two thousand characters of text and the genre list: 3–4 k tokens with Cyrillic text.
- **Keep the embedding server separate**, as above: **Model server** on one port, **Embedding server** on the other. Pointing **Model server** at the embedding server makes every question time out, because that server never produces a chat completion.
- **Start it as a service** (`brew services start llama.cpp` with the preset in its arguments, or a launchd agent) rather than from a shell, so it is there when Alfred asks and survives a logout. A manually started copy loses the port to a service that is already listening and exits at once — check `lsof -nP -iTCP:8080 -sTCP:LISTEN` when a restart seems to change nothing.

`kb model` reads `/v1/models` of both servers, so it knows what each one *can* serve; whether a model is loaded right now is `curl localhost:8080/health` (router mode: the per-model entry in `/models`), and `oracle.log` says how long each answer took.

## KOReader users

Moves and renames also carry each book's `.sdr` sidecar along and rewrite the paths in `.adds/koreader/settings/{collection,history,bookmarks}.lua` (a `.bak` is written first) and under `.adds/koreader/docsettings/`, so highlights, progress and collections survive `kb done` and `kb fix`. This only works if `.adds/koreader` lives under your device root: either the root is the device itself, or your sync includes that folder.

## How it reads your folders

The vault tree is what the e-reader shows, so the tool keeps it meaning exactly one thing: **genre → author → series**.

- Genre is the first two folder levels with their order prefixes stripped: `01_Fiction/02_Sci-Fi_Fantasy/…` → `fiction/sci-fi_fantasy`. A folder that looks like an author (`Surname, Given` or `Given Surname`) ends the genre early, so `programming/Dietrich, Erik/…` is genre `programming` with the author straight under it. Books under the nook, `inbox`, `archives`, `_inbox`, `_dups`, `_trash` or `_broken` have no genre from their folder.
- The nook is the top-level folder whose name is `nook` after the order prefix (`00_Nook`, `Nook`); when there is none, `Nook/` is created on the first import.
- Author folders are `Surname, Given`. An epub's `file-as` sort name and an fb2's name tags are taken as they are; a plain `Given Surname` string is split by rule, and for Cyrillic names the rule knows a few hundred given names, patronymics and surname endings, so `Роджер Желязни` and `Шевчук Валерій` both file under the surname. Existing folders win: if you already have `Le Guin, Ursula K.`, that spelling is reused.
- A series gets its own folder only when the vault holds more than one book of it.
- Canonical file name: `Surname, Given - Title (Series 03) (Year).epub`, FAT-safe, ≤ 255 bytes. A book is renamed to it when it is filed into the vault or copied into the nook, never where it lies.
- Genres live in `catalogue.tsv` keyed by a content fingerprint, so they survive renames and moves. `kb update` bootstraps a genre for every book from its folder, never overwriting one you set.

## Where things are

The index (`books.db`), `covers/`, the model's answers (`oracle.tsv`, `oracle.log`), `vectors.db`, a snapshot of the catalogue and the undo journal (`journal.jsonl`) live in Alfred's workflow data folder, `~/Library/Application Support/Alfred/Workflow Data/com.anokhin.kobold`, which survives workflow updates and cache clears. Override with **Index folder**. `catalogue.tsv` lives at the device root.

**Upgrading from 0.4:** the first `kb update` adopts `library.db` as `books.db` (and asks for the one rebuild the new columns need), converts `genres.tsv` into `catalogue.tsv` and drops `sources.db`. `authors.tsv` is ignored: aliases already applied to folders stay as they are, and there are no more merges. `KOBOLD_ROOT` and `KOBOLD_SOURCES` keep their names; the configuration labels them *Device root* and *Library folders*. `kb src` is `kb lib`, `kb trash` is `kb remove`, and the inbox is gone: books arrive in the library, not on the device, and a device book without a genre is simply listed by `kb classify`.

**Upgrading from kobo-alfred:** the workflow was called Kobo Library and its data lived under `com.anokhin.kobolib`. The first run renames that folder to `com.anokhin.kobold`, so the index, covers and genres carry over. Workflow settings don't: Alfred keys them by bundle id, so set **Device root** (and any model settings) again.

Format support: epub and fb2 are read for metadata and cover; mobi, azw, azw3, pdf and djvu are described from their filename (libgen, Anna's Archive, `[Series №N]`, `Title - Author` and friends). `.part` files are indexed, flagged as unfinished downloads, and only ever offered to `kb remove`. Library folders are indexed the same way, except that unreadable and unfinished files are left out.

## From a terminal

The same commands, same data:

```
export KOBOLD_ROOT=/Volumes/Transcend/kobo
export KOBOLD_SOURCES="$HOME/Calibre Library:$HOME/Downloads"
export KOBOLD_DATA="$HOME/Library/Application Support/Alfred/Workflow Data/com.anokhin.kobold"
uv run kobold update
uv run kobold search delany | jq '.items[].title'
uv run kobold nook "$KOBOLD_ROOT/01_Fiction/02_Sci-Fi/Delany, Samuel R./Delany, Samuel R. - Dhalgren (1975).epub"
uv run kobold done "$KOBOLD_ROOT/Nook/Delany, Samuel R. - Dhalgren (1975).epub"
uv run kobold import "$HOME/Calibre Library/Samuel R. Delany/Nova/Nova - Samuel R. Delany.epub"
uv run kobold remove "$KOBOLD_ROOT/00_Inbox/broken.epub.part"
uv run kobold genre "$KOBOLD_ROOT/00_Inbox/nova.epub" fiction/sci-fi
uv run kobold fix --dry-run
uv run kobold fix delany
uv run kobold undo
uv run kobold catalogue
uv run kobold ask [genre|name] [<words>]           # --force re-asks, --dry-run prints the evidence
uv run kobold embed [<words>]                      # --force re-embeds
uv run kobold models
uv run kobold choose oracle|embed <model>
```

`nook`, `done`, `remove` and `genre` take absolute device paths or fingerprints, several per line. `import` takes absolute paths of indexed library books. `KOBOLD_CATALOGUE` moves the catalogue; `KOBOLD_ORACLE_URL`, `KOBOLD_ORACLE_MODEL`, `KOBOLD_EMBED_URL` and `KOBOLD_EMBED_MODEL` configure the model from the terminal the way the workflow panel does; `KOBOLD_ORACLE_KEY` (and `KOBOLD_EMBED_KEY` when the embedding server has its own) is sent as a bearer token to a server started with `--api-key`.

`search` and `genres` print Alfred's JSON; everything else prints one line and, with `--notify`, posts it as a macOS notification.

Set `KOBOLD_DATA` as above if you want the terminal and Alfred to share one index: without it the CLI defaults to `~/Library/Application Support/kobold`, a separate copy.

## When something looks off

| You see | Do |
| --- | --- |
| *No index yet* | ↩ on that row, or `kb update` |
| *Index is from an older version* | ↩ on that row: the workflow was updated and the index format changed |
| *Index is empty — is the device folder there?* | the device root is missing or empty: check the path, mount the volume, or grant Alfred Removable Volumes access |
| *Library root not mounted: …* (after `kb update`) | the **Device root** path doesn't exist right now |
| *No books found: …* (after `kb update`) | the root exists but holds no epub/fb2/mobi/azw/azw3/pdf/djvu; the message says why if it's a permissions problem |
| *Indexing is running, try again later* | wait for the notification; a stale lock expires after an hour |
| *No library indexed* | **Library folders** is empty, or none of them was mounted at the last `kb update` |
| *skipped 1: … no library copy* | `kb remove` keeps the only copy of a book; import it into the library first, or delete by hand |
| *The nook is empty* | ↩ on a `kb` row brings a book there |
| *stays put (no author or already home)* | `kb done` found no home: give the book a genre with ⌘↩, or an author in its metadata |
| *No book selected* in the genre picker | it was opened directly; use ⌘↩ on a book or ↩ in `kb classify` |
| *Nothing to fix* | the device is tidy |
| *… no such book in the catalogue line* | a line in `catalogue.tsv` names a path the index doesn't know; `kb catalogue` to fix or delete it |
| *Asking the model… a notification follows* / *The model is already being asked* | one pass runs at a time; wait for its notification. A pass that died leaves `oracle.lock` behind for an hour; delete it to go on |
| *Model not reachable at …* | start `llama-server`, or fix **Model server**; `kb model` shows whether it answers |
| every request skipped, `oracle.log` says *401* | the server wants a key: set **Model server API key** |
| `oracle.log` full of *timed out*, `seconds` = 60 | the model is still downloading or loading, **Model server** points at the embedding server, or the oracle is a thinking model; choose a plain instruct model in `kb model` |
| `oracle.log` full of *400 Bad Request* | the request names a model the server does not know; pick one in `kb model`, or set `KOBOLD_ORACLE_MODEL` in the terminal |
| the terminal and Alfred disagree about what was asked | they use different data folders unless `KOBOLD_DATA` is set |
| `kobold embed` skips every book | the embedding server answers 501: it was started without `--embeddings`, or with a chat model |
| *No embedding model* in `kb like` | ↩ on a model in `kb model`, then **Use … for embeddings** |
| *No embeddings yet* | ↩ on that row embeds in the background |

## Development

```
uv run pytest
uv run ruff check && uv run ruff format --check
uv run python scripts/make_plist.py   → workflow/info.plist, from the tables in docs/interface.md
./build.sh                            → dist/Kobold.alfredworkflow
```

`docs/interface.md` is the design; `docs/plan.md` says how it was built. CI runs the tests on Python 3.9 and 3.13, builds the workflow and publishes it as the `latest` pre-release; a `v*` tag makes a proper release.
