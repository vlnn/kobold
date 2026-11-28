from __future__ import annotations

from pathlib import Path

from kobold.genres import folder_genres
from kobold.history import REMEMBERED, read_last_opened_id, read_opened
from kobold.places import NOOK
from kobold.progress import progress_label, read_at
from kobold.seen import Seen, remember


def nook_locators(founds) -> list[str]:
    return [locator for found in founds if (locator := found.locator_in(NOOK))]


def nook_progress(founds) -> dict[str, str]:
    return {locator: shown for locator in nook_locators(founds) if (shown := progress_label(Path(locator)))}


def nook_readings(founds) -> list[list]:
    # KOReader rewrites a book's sidecar as it is read, and its history may sit on storage kobold cannot see
    in_nook = ((found.entity.id, found.locator_in(NOOK)) for found in founds)
    return [[book, at] for book, locator in in_nook if locator and (at := read_at(Path(locator)))]


def latest_readings(pairs: list[list], limit: int = REMEMBERED) -> list[list]:
    latest: dict = {}
    for book, at in sorted(pairs, key=lambda pair: pair[1], reverse=True):
        latest.setdefault(book, at)
    return [[book, at] for book, at in latest.items()][:limit]


def survey(founds, ctx) -> None:
    opened = latest_readings(read_opened(founds, ctx) + nook_readings(founds))
    remember(Seen(nook_progress(founds), folder_genres(ctx), read_last_opened_id(ctx), opened), ctx)
