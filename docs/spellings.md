# One name per writer, one name per genre

Libraries spell the same writer several ways: `Samuel R. Delany` in one epub, `Delany, Samuel R.` in another, `S. R. Delany` in a third. Without a fix each of these gets its own author folder, its own file names and its own search results. Genres drift the same way: `02_SciFi` next to `03_Sci-Fi`, a hand tag `sci-fi` next to the folder genre `fiction/sci-fi`. Every `kb update` looks for such spellings and proposes a standard for each group. No model is needed.

```
kb update                  Delany, Samuel R.  ←  Samuel R. Delany        applied: only order, case or marks differ
kb std                     Accept 2
                           Delany, Samuel R.    authors · S. R. Delany · 3 books
                           fiction/sci-fi       tags · sci-fi · 1 book
   ↩ on one                Standard: Delany, Samuel R.
   ⌘↩ on one               pick another spelling as the standard, or Keep apart
```

- **Applied on update, no question asked:** spellings that differ only in word order (when one of them is `Surname, Given`, or both name the same surname), case, punctuation, accents (`Stanislaw` / `Stanisław`), `ё`/`е` or apostrophes. For genres: separators, case, `and`, and plurals (`sci-fi_fantasy` / `Sci-Fi and Fantasy`, `thriller` / `Thrillers`). Each update's fixes are one undoable batch. Undoing it means *no*: those spellings are kept apart from then on.
- **Waiting in `kb std`:** swapped names with no comma to tell the surname (`Henry James` / `James Henry`), initials (`S. R. Delany`), a missing middle name or patronymic (`Ursula Le Guin`, `Іванов, Іван`), a bare surname, a genre without its parent (`sci-fi` → `fiction/sci-fi`) and synonyms (`sf`, `science fiction` → `scifi`). **Accept N** takes them all as one undoable batch.
- **Which spelling becomes the standard:** for writers, the fullest name first, then proper capitalisation, then a name without `(ed.)`, then accents, then an existing author folder, then the `Surname, Given` form, then the most books. For genres, an existing vault folder wins, then the deeper path (`fiction/sci-fi` over `sci-fi`), then the folder or tag with more books.
- **Never merged:** different people (`Samuel` / `Sarah Delany`), and spellings in different scripts. `Zelazny, Roger` and `Желязни, Роджер` stay two spellings, so each book keeps the name in its own language. An ambiguous short form such as `A. Smith`, when both `Adam Smith` and `Alice Smith` exist, is left alone.

A standard sticks. Books that arrive later with a known variant are indexed under the standard, `kb fix` and `kb done` file them into the standard author folder under the standard file name, and a copy into the nook is named the same way. Genre variants disappear from the picker and from the model's choices, books tagged with a variant are retagged, and the next `kb fix` moves books from a variant genre folder into the standard one. Files themselves change only when they are filed or copied, as everywhere else in kobold.
