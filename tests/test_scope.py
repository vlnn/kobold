import pytest

from kobold import scope


@pytest.mark.parametrize(
    ("uid", "expected"),
    [
        ("head:stats", "all"),
        ("head:stats:nook", "nook"),
        ("head:stats:vault", "vault"),
        ("head:stats:library", "library"),
        ("head:stats:hoard", "all"),
        ("some-book", "all"),
        ("", "all"),
    ],
)
def test_a_row_names_the_scope_of_its_stats(uid, expected):
    assert scope.scope_of(uid) == expected, f"{uid!r} should show the {expected} stats"


@pytest.mark.parametrize("uid", ["head:stats", "head:stats:nook", "head:stats:hoard"])
def test_a_row_hides_every_panel_but_its_own(uid):
    shown = [name for name in scope.SCOPES if not scope.hidden_panels(uid)[scope.key(name)]]
    assert shown == [scope.scope_of(uid)], "exactly the panel of the row's scope should be shown"
