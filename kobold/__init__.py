from hoard.contract import Command, Kind, Storage, Verb, lazy

from kobold.places import DEVICE, NOOK, default_verb, removable
from kobold.roots import library_of, nook_of, parent_is_dir, vault_of

ROOT_SETTING = "KOBOLD_ROOT"
SOURCES_SETTING = "KOBOLD_SOURCES"

DEVICE_BOOK = lazy("kobold.reading", "read_device_book")
UNDO = lazy("kobold.verbs", "undo")

IMPORT = Command("Import", "to_nook", off=DEVICE)
FINISH = Command("Finish", "done", on=(NOOK,))
REMOVE = Command("Remove", "remove", keep=removable)

KIND = Kind(
    name="kobold",
    keyword="kb",
    storages=(
        Storage("nook", nook_of(ROOT_SETTING), DEVICE_BOOK, mounted=parent_is_dir),
        Storage("vault", vault_of(ROOT_SETTING), DEVICE_BOOK),
        Storage("library", library_of(SOURCES_SETTING), lazy("kobold.reading", "read_library_book")),
    ),
    fields=("authors", "series", "year", "format"),
    evidence=lazy("kobold.reading", "evidence"),
    labels={"one": "book", "many": "books"},
    nameable=("authors",),
    tags=lazy("kobold.genres", "known_genres"),
    default_verb=default_verb,
    verbs={
        "to_nook": Verb("To the nook", lazy("kobold.verbs", "to_nook"), UNDO),
        "done": Verb("Finish", lazy("kobold.verbs", "done"), UNDO),
        "remove": Verb("Remove", lazy("kobold.verbs", "remove"), UNDO),
    },
    commands={
        "nook": Command("Open", "open", on=(NOOK,)),
        "done": FINISH,
        "finish": FINISH,
        "lib": IMPORT,
        "import": IMPORT,
        "remove": REMOVE,
        "trash": REMOVE,
    },
)
