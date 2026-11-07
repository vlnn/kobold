# KOReader users

Each book's reading progress is read from its `.sdr` sidecar next to the file, the one KOReader keeps by default; sidecars kept under `docsettings/` are moved with the book but not read.

Moves and renames also carry each book's `.sdr` sidecar along and rewrite the paths in `.adds/koreader/settings/{collection,history,bookmarks}.lua` (a `.bak` is written first) and under `.adds/koreader/docsettings/`, so highlights, progress and collections survive `kb done`, `kb fix`, ↩ to the nook, `kb remove` and undo. This only works if `.adds/koreader` lives under your device root: either the root is the device itself, or your sync includes that folder.
