from __future__ import annotations

from pathlib import Path

from kobold.genres import folder_genres
from kobold.history import read_last_opened_id, read_opened
from kobold.places import NOOK
from kobold.progress import progress_label
from kobold.seen import Seen, remember


def nook_locators(founds) -> list[str]:
    return [locator for found in founds if (locator := found.locator_in(NOOK))]


def nook_progress(founds) -> dict[str, str]:
    return {locator: shown for locator in nook_locators(founds) if (shown := progress_label(Path(locator)))}


def survey(founds, ctx) -> None:
    remember(Seen(nook_progress(founds), folder_genres(ctx), read_last_opened_id(ctx), read_opened(founds, ctx)), ctx)
