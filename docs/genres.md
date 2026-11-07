# Suggested genres, no model needed

Most books say what they are: an epub carries `dc:subject` lines (`FICTION / Science Fiction / Space Opera`, or Calibre's tags), an fb2 its `<genre>` codes (`sf_space`). Every update reads them and proposes a genre for each book that has none, shown as `fiction/sci-fi? 80%` in `kb tag`, in the subtitle of a plain search, and first in the picker; **Accept N suggested** takes them all. The proposals come from three places, in this order:

- **the shelf a book left.** A vault book moved to the nook is proposed the genre of the folder it came from, at 90%;
- **what you picked before.** Setting a genre by hand teaches kobold that this book's subjects mean that genre; once two books with the same subject got the same genre, that is a rule, at 60% plus 10% per agreeing pick, up to 90%. Undoing a pick unlearns it; accepting a suggestion teaches nothing, so a rule cannot feed itself. The books already filed in your vault teach their subjects their shelf the first time they are read, so the rules know your library from the start;
- **a built-in table** of BISAC headings, common Calibre tags and fb2 genre codes, at 80%. Its genres are spelled `fiction/sci-fi`, `nonfiction/history` and so on; a vault shelf with the same meaning (`01_Fiction/02_SciFi`) is used instead when one exists, otherwise the genre is proposed as written and the picker creates it when you accept.

A book carrying several subjects that map to several genres is proposed the genre with more books on your shelves. The rules live in `kobold-rules.sqlite` next to the index and survive `kb update`. With a model server set, the model's answer replaces the rule's when it arrives; a book with a rule's proposal is still asked.

KOReader's genre menu reads the metadata inside each book, not kobold's tags, so `kb done` writes the genre into the file as it files the book: `dc:subject` in an epub, `<genre>` in an fb2, replacing whatever the publisher put there. **Stamp the genre on finish** in the workflow configuration turns this off. `kb stamp` does the same for books already on the device. The book's text is untouched, so it stays the same book to kobold, and the batch is undoable. Other formats cannot be written and are left as they are; the library is never written.

A genre you set wins over the folder. The book moves to the new genre's folder on the next `kb fix`, or on `kb done` when it leaves the nook.
