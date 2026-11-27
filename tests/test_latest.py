from kobold import latest


def test_the_last_to_claim_holds(tmp_path):
    first, second = latest.claim(str(tmp_path)), latest.claim(str(tmp_path))
    assert (latest.holds(first, str(tmp_path)), latest.holds(second, str(tmp_path))) == (False, True), "only the newest claim should hold"


def test_a_lone_claim_holds(tmp_path):
    assert latest.holds(latest.claim(str(tmp_path)), str(tmp_path)), "a search nobody overtook should be shown"


def test_claims_differ_even_within_one_process(tmp_path):
    assert latest.claim(str(tmp_path)) != latest.claim(str(tmp_path)), "two searches should never share a claim"


def test_a_claim_makes_its_folder(tmp_path):
    folder = str(tmp_path / "not" / "yet")
    assert latest.holds(latest.claim(folder), folder), "the first search after a cache clear should still work"


def test_a_lost_claim_file_does_not_silence_the_search(tmp_path):
    token = latest.claim(str(tmp_path))
    (tmp_path / latest.FILE).unlink()
    assert latest.holds(token, str(tmp_path)), "with no rival on record the answer should be shown"
