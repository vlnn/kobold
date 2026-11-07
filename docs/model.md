# A local model, if you run one

Everything in the README works with no model. If you run [llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server` on the Mac, the workflow can propose answers to the two chores that still need a human per book — a genre for a new book, and a real title and author for a file named `7_815203.epub`. The model never moves a file.

Set **Chat model server** in the workflow configuration to the server's URL (`http://127.0.0.1:8080`), then:

```
kb model                       Chat models · http://127.0.0.1:8080, then a row per model · ↩ uses it
kb tag                         Ask about 12 books · ↩ asks in the background
kb tag                         Dhalgren   fiction/sci-fi? 90% · …   ← the ? is a suggestion
   Accept 9 suggested          ↩ gives every listed book its suggestion, one undoable batch
```

A confident answer to the name question (80% or more) corrects the book's title and author in the index, so search finds it, and when the book is filed or copied into the nook it gets its canonical name from the corrected row. The file is not touched before that. Less certain answers wait in `kb name` for **Accept N**. Corrections survive `kb update`.

What the model sees is the book's title, authors, series and year, its `dc:subject`/`dc:description` (fb2: `genre`/`annotation`) and the first two thousand characters of its text; `ask --dry-run` from a terminal (see [internals.md](internals.md)) prints exactly that. Every answer is constrained by a JSON schema and kept until that evidence changes. Setting a genre by hand forgets the model's guess.

If the server wants a key — `--api-key`, or `LLAMA_API_KEY` exported in the shell that started it — put it in **Chat server API key**.

Turn on **Ask and embed on update** and `kb update` asks the name and genre questions by itself after reading the places, for books without an answer. Off by default, so updating stays as fast as it is. The **Embeddings server** setting is not used: `kb like` makes its own vectors.

Nothing in the UI mentions a model until its server is set; a server that does not answer shows as *Chat server not reachable* in `kb model`.

## Running llama-server

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
