from hoard.contract import TAGS, Command, Kind, LocalVectors, Standardize, Storage, Verb, lazy

from kobold.places import DEVICE, NOOK, default_verb, has_home, removable, stampable
from kobold.roots import ROOT_SETTING, SOURCES_SETTING, ground, library_of, nook_of, parent_is_dir, vault_of

DEVICE_BOOK = lazy("kobold.reading", "read_device_book")
UNDO = lazy("kobold.verbs", "undo")
LIKENESS = "kobold-hashed-v1"

IMPORT = Command("Import", "to_nook", off=DEVICE)
FINISH = Command("Finish", "done", keep=has_home)
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
        "stamp": Verb("Stamp", lazy("kobold.stamp", "stamp"), lazy("kobold.stamp", "undo")),
    },
    lint=lazy("kobold.verbs", "lint"),
    ground=ground,
    escort=lazy("kobold.sidecars", "escort"),
    last_opened=lazy("kobold.history", "last_opened_id"),
    like=LocalVectors(LIKENESS, lazy("kobold.likeness", "vector")),
    pictured_first=True,
    subtitle=lazy("kobold.subtitle", "subtitle"),
    standards={
        "authors": Standardize(lazy("kobold.standards", "authors"), "; "),
        TAGS: Standardize(lazy("kobold.standards", "genres")),
    },
    commands={
        "nook": Command("Open", "open", on=(NOOK,)),
        "done": FINISH,
        "finish": FINISH,
        "lib": IMPORT,
        "import": IMPORT,
        "remove": REMOVE,
        "trash": REMOVE,
        "stamp": Command("Stamp", "stamp", keep=stampable),
    },
)
