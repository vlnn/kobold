from hoard.contract import Kind, Storage, lazy

from kobold.roots import library_of, nook_of, parent_is_dir, vault_of

DEVICE = "KOBOLD_ROOT"
SOURCES = "KOBOLD_SOURCES"
DEVICE_BOOK = lazy("kobold.reading", "read_device_book")

KIND = Kind(
    name="kobold",
    keyword="kb",
    storages=(
        Storage("nook", nook_of(DEVICE), DEVICE_BOOK, mounted=parent_is_dir),
        Storage("vault", vault_of(DEVICE), DEVICE_BOOK),
        Storage("library", library_of(SOURCES), lazy("kobold.reading", "read_library_book")),
    ),
    fields=("authors", "series", "year", "format"),
    evidence=lazy("kobold.reading", "evidence"),
    labels={"one": "book", "many": "books"},
    nameable=("authors",),
    tags=lazy("kobold.genres", "known_genres"),
)
