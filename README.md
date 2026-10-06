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
kb done            →  Finish all 3 · ↩ on one files it into the vault under its genre and author
kb tidy            →  Tidy all N · every vault book to its genre/author home, weaker formats to _dups
kb tag             →  books without a genre · ⌘↩ on any book opens the genre picker
```

## Install (three minutes)

1. Grab `Kobold.alfredworkflow` from [Releases](https://github.com/vlnn/kobold/releases) (every push to `main` publishes a `latest` build) and double-click it.
2. In the workflow's configuration set **Device root** to the folder that is, or syncs with, your e-reader, e.g. `~/Books/kobo` (a Syncthing folder) or `/Volumes/Transcend/kobo` (the card itself). Set **Library folders** to where your books arrive, `~/Calibre Library:~/Downloads`, paths separated by `:`.
3. Type `kb update` ↩. The index is built in the background; `kb` shows *Updating the index… · N of M checked* until it is done.

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

A book that exists in several places is one row, shown at its nearest place: nook, then vault, then library. The subtitle says where it is and where else it is: `vault +library · Samuel R. Delany · 1975 · EPUB 1.2 MB`. The icon is the cover embedded in an epub or fb2. Lists show the first 40 matches, so add a word if what you want isn't there.

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
| `kb done` / `finish` | the nook | file it into the vault | Finish all N |
| `kb lib` / `import` | library books the device lacks | copy into the nook | Import all N |
| `kb remove` / `trash` | device books the library still holds, and unfinished downloads | to `_trash/` | Remove all N |
| `kb tidy` | the device's books | file it home, set duplicates aside | Tidy all N |
| `kb fix` | junk files on the device | to the trash | Apply N |
| `kb tag [words]` | books without a genre | the genre picker | Tag all N · Accept N suggested |
| `kb name [words]` | the model's unsure titles and authors | accept it | Accept N |
| `kb like [words]` | neighbours of the first match, or of the book KOReader opened last | by place, as `kb` | — |
| `kb rnd` | ten random books | by place, as `kb` | — |
| `kb stats` | counts per place and when each was last read | — | — |
| `kb undo` | the last batch | undo it | — |
| `kb update` | — | read every place again, in the background | — |
| `kb model` | what each model server serves | use that model | — |

`kb remove` only sets aside books the library still holds, and unfinished downloads; the only copy of a book stays on the device. Nothing is ever deleted: `_trash/` is a folder you empty yourself.

## Walkthrough 1: read a book

```
kb dhalgren              Dhalgren   library · Samuel R. Delany · 1975 · EPUB 1.2 MB
   ↩                     To the nook: Dhalgren
kb nook                  Dhalgren   nook +library · Samuel R. Delany · 1975 · EPUB 1.2 MB
```

The copy arrives in the nook under its canonical name, `Delany, Samuel R. - Dhalgren (1975).epub`; the library keeps its file. Read it on the device. When you are through:

```
kb done
   ↩ on Dhalgren         Finish: Dhalgren
```

and it is in `01_Fiction/02_Sci-Fi/Delany, Samuel R./`. A book without a genre or an author has no home yet, so `kb done` says *Finish: nothing to do* and leaves it in the nook: give it a genre with ⌘↩ first.

## Walkthrough 2: tidy the vault

`kb tidy` lists the books on the device under **Tidy all N**. ↩ on that row:

- moves every vault book with a genre and an author to its home, `genre / Author / Series / canonical name`. The nook is never touched: books there are being read;
- keeps the best copy of a title (the nook copy, then complete, in a genre folder, epub > fb2 > mobi > azw3 > azw > pdf > djvu, newest, largest) and moves the rest to `_dups/`, mirroring their path;
- moves identical copies to `_trash/`.

↩ on one book does the same for that book alone. `kb fix` is the other half: files that are not books (`FSCK*`, `.zip`, `.txt`, empty folders) go to a hidden `.hoard-trash/` inside their top-level folder.

"Identical" and "already on the device" mean the same text: for epubs the fingerprint is a hash of the book's text files only, so two copies with different covers or metadata still count as one book. Other formats are hashed whole.

Every batch, from `kb tidy`, `kb done`, an import, `kb remove` or a genre, is one entry in the journal, and `kb undo` reverses the most recent one; undoing an import deletes the copy, the library still has the book. When a move finds a byte-identical file already at the destination, the redundant source is removed instead of moved; undo restores it from the kept copy. Folders left empty are pruned, and case-only and accent-only renames happen in place.

## Walkthrough 3: genres

Genres are how the vault is laid out: the first two folder levels with their order prefixes stripped (`01_Fiction/02_Sci-Fi_Fantasy/…` → `fiction/sci-fi_fantasy`). A vault book has the genre of its folder until you give it one.

- ⌘↩ on any book row opens the picker: the vault's genres, the model's guess first if there is one. Type to narrow them, or to create a new genre.
- `kb tag` lists books without a genre you set; **Tag all N** picks one genre for the whole list.

Only genres you set are searchable; a folder genre is not, so `kb sci-fi` finds the books you tagged `fiction/sci-fi`.

A genre you set wins over the folder. The book moves to the new genre's folder on the next `kb tidy`, or on `kb done` when it leaves the nook.

## Books like this

`kb like` needs no model. On every update kobold works out, for each new book, how it reads: its authors, series, genre, decade and title words, plus its subjects, description and opening text taken as short letter runs, so *корабель* and *корабля* still count as the same word. Books that share more of that come out closer.

```
kb like dhalgren     Like Dhalgren
                     Nova        91% · library · Samuel R. Delany · 1968 · EPUB 400 KB   ↩ copies it in
                     Babel-17    88% · vault · …                                          ↩ to the nook
kb like              starts from the book KOReader opened last, else the newest book
⌃↩ on any row        the same list for that book
```

It is a likeness of words, not of meaning: same author, same series, same genre and shared vocabulary rank high, while two novels with the same mood in different words do not find each other. A book whose file is not reachable during the update is placed by its title, authors, series, year and genre alone. A genre set later does not move a book until its vector is made again.

## Walkthrough 4: let a local model do the reading

Everything above works with no model. If you run [llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server` on the Mac, the workflow can propose answers to the two chores that still need a human per book — a genre for a new book, and a real title and author for a file named `7_815203.epub`. The model never moves a file.

Set **Chat model server** in the workflow configuration to the server's URL (`http://127.0.0.1:8080`), then:

```
kb model                       Chat models · http://127.0.0.1:8080, then a row per model · ↩ uses it
kb tag                         Ask about 12 books · ↩ asks in the background
kb tag                         Dhalgren   fiction/sci-fi? 90% · …   ← the ? is a suggestion
   Accept 9 suggested          ↩ gives every listed book its suggestion, one undoable batch
```

A confident answer to the name question (80% or more) corrects the book's title and author in the index, so search finds it, and when the book is filed or copied into the nook it gets its canonical name from the corrected row. The file is not touched before that. Less certain answers wait in `kb name` for **Accept N**. Corrections survive `kb update`.

What the model sees is the book's title, authors, series and year, its `dc:subject`/`dc:description` (fb2: `genre`/`annotation`) and the first two thousand characters of its text; `ask --dry-run` from a terminal (see *From a terminal*) prints exactly that. Every answer is constrained by a JSON schema and kept until that evidence changes. Setting a genre by hand forgets the model's guess.

If the server wants a key — `--api-key`, or `LLAMA_API_KEY` exported in the shell that started it — put it in **Chat server API key**.

Turn on **Ask and embed on update** and `kb update` asks the name and genre questions by itself after reading the places, for books without an answer. Off by default, so updating stays as fast as it is. The **Embeddings server** setting is not used: `kb like` makes its own vectors.

Nothing in the UI mentions a model until its server is set; a server that does not answer shows as *Chat server not reachable* in `kb model`.

### Running llama-server

The workflow only needs an OpenAI-compatible `/v1/chat/completions` that honours `response_format` with a JSON schema; any recent `llama-server` does. Two ways to run it:

```sh
llama-server --hf-repo <org>/<model>-GGUF:Q4_K_M --alias oracle --jinja -c 8192 -ngl 99 --port 8080
```

serves one model; `kb model` then lists it under its alias. Or start the server with no model and a preset file, and it runs in *router mode*: every `[section]` is a model it can serve, loaded the first time a request names it:

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

Router mode is the comfortable one — swap models in `kb model` without restarting anything — with one thing to know: nothing is loaded until it is asked for. The first question after a start pays for loading the weights, and the very first time for downloading them into `~/.cache/llama.cpp`, which for a 20–30 B model is minutes to tens of minutes during which every request times out at 60 s and the pass stops. Wait for the download (the blob grows under `…/blobs/*.downloadInProgress`), or ask once from a terminal with `curl` before the pass, and ask again. `sleep-idle-seconds` in a preset unloads the model after that many idle seconds and brings the loading pause back on the next question; leave it out on a machine with the RAM, or expect the first question after each break to time out.

Choices that matter for this workflow:

- **An instruct model, not a thinking one.** A thinking model spends its time inside `<think>` and often misses the 60 s limit.
- **`--jinja`.** Without it the chat template is approximated and the JSON-schema grammar fights the model more than it should.
- **Context of 8 k or so.** A question carries the book's metadata, subjects, blurb and two thousand characters of text: 3–4 k tokens with Cyrillic text.
- **Start it as a service** (`brew services start llama.cpp` with the preset in its arguments, or a launchd agent) rather than from a shell, so it is there when Alfred asks and survives a logout. A manually started copy loses the port to a service that is already listening and exits at once — check `lsof -nP -iTCP:8080 -sTCP:LISTEN` when a restart seems to change nothing.

`kb model` reads `/v1/models` of both servers, so it knows what each one *can* serve; whether a model is loaded right now is `curl localhost:8080/health` (router mode: the per-model entry in `/models`), and `ask --dry-run` from a terminal shows what a question would send.

## KOReader users

Moves and renames also carry each book's `.sdr` sidecar along and rewrite the paths in `.adds/koreader/settings/{collection,history,bookmarks}.lua` (a `.bak` is written first) and under `.adds/koreader/docsettings/`, so highlights, progress and collections survive `kb done`, `kb tidy`, ↩ to the nook, `kb remove` and undo. This only works if `.adds/koreader` lives under your device root: either the root is the device itself, or your sync includes that folder.

## How it reads your folders

The vault tree is what the e-reader shows, so the tool keeps it meaning exactly one thing: **genre → author → series**.

- The vault is every top-level folder of the device root except the nook, `_trash`, `_dups` and hidden ones. Books loose at the top of the device root are not read.
- Genre is the first two folder levels with their order prefixes stripped: `01_Fiction/02_Sci-Fi_Fantasy/…` → `fiction/sci-fi_fantasy`. A folder that looks like an author (`Surname, Given` or `Given Surname`) ends the genre early, so `programming/Dietrich, Erik/…` is genre `programming` with the author straight under it. Books under `inbox`, `archives`, `_inbox` or `_broken` have no genre from their folder.
- The nook is the top-level folder whose name is `nook` after the order prefix (`00_Nook`, `Nook`); when there is none, `Nook/` is created on the first import.
- Author folders are `Surname, Given`. An epub's `file-as` sort name and an fb2's name tags are taken as they are; a plain `Given Surname` string is split by rule, and for Cyrillic names the rule knows a few hundred given names, patronymics and surname endings, so `Роджер Желязни` and `Шевчук Валерій` both file under the surname. Existing folders win: if you already have `Le Guin, Ursula K.`, that spelling is reused.
- A series gets its own folder only when the vault holds more than one book of it.
- Canonical file name: `Surname, Given - Title (Series 03) (Year).epub`, FAT-safe, ≤ 255 bytes. A book is renamed to it when it is filed into the vault, tidied or copied into the nook, never where it lies.

Format support: epub and fb2 are read for metadata and cover; mobi, azw, azw3, pdf and djvu are described from their filename (libgen, Anna's Archive, `[Series №N]`, `Title - Author` and friends). `.part` files on the device are indexed as unfinished downloads, and only ever offered to `kb remove`. Library folders leave out unreadable and unfinished files.

## Where things are

Alfred's workflow data folder, `~/Library/Application Support/Alfred/Workflow Data/com.anokhin.kobold`, holds `kobold.sqlite`: the index, your genres, the model's answers and the last 300 exchanges with it, the vectors and the undo journal. It survives workflow updates and cache clears. The cache folder, `~/Library/Caches/com.runningwithcrayons.Alfred/Workflow Data/com.anokhin.kobold`, holds the covers and `worker.log`, where background updates and model passes write what went wrong.

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

## When something looks off

| You see | Do |
| --- | --- |
| *Index is empty* | ↩ on that row, or `kb update` |
| *No folder set for nook* | set **Device root** in the workflow configuration |
| *Not reachable: …* | the folder is not there right now: mount the volume, or grant Alfred Removable Volumes access |
| *Updating the index… · counting files* | the update is listing the files it will read; the count follows |
| *Asking the model… · N of M asked* | the chat model is answering for every book it has not seen, one at a time; **Ask and embed on update** starts this after each update |
| *Embedding… · N of M embedded* | an update is working out `kb like` for new books; usually well under a minute |
| *Finish: nothing to do* | the book has no genre or no author yet: ⌘↩ to give it a genre |
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
```

hoard is pinned to a tag in `pyproject.toml`. To work on both, keep a hoard checkout next to this one and add `--with-editable ../hoard` to any of the commands above, e.g. `uv run --with-editable ../hoard pytest`. To move to a newer hoard, change the tag and run `uv lock`.

`docs/interface.md`, `docs/plan.md` and `docs/oracle.md` describe the 0.5 design, before hoard.
