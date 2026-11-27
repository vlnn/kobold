from hoard.testing import Conformance, make_epub, make_fb2
from hoard.testing.conformance import module_defining, private_hoard_imports, source_files

from kobold import KIND

WINDOW_SEAM = {"followup.py": ["hoard._requery"]}


def seam_of(path) -> list:
    return next((allowed for name, allowed in WINDOW_SEAM.items() if str(path).endswith(name)), [])


class TestConformance(Conformance):
    kind = KIND

    def test_kind_imports_no_private_hoard_module(self):
        for path in source_files(module_defining(self.kind)):
            assert private_hoard_imports(path) == seam_of(path), (
                f"{path} should import only hoard's public surface, bar the window's one seam"
            )

    def make_samples(self, storage, root):
        if storage == "nook":
            make_epub(
                root / "Dick, Philip K. - Ubik (1969).epub",
                title="Ubik",
                authors=("Philip K. Dick",),
                date="1969",
                chapters=("Ubik text.",),
            )
            (root / "Dick, Philip K. - Ubik (1969).sdr").mkdir()
            (root / "Dick, Philip K. - Ubik (1969).sdr" / "metadata.epub.lua").write_text("return { percent_finished = 0.4 }")
            return
        if storage == "vault":
            make_fb2(root / "Lem, Stanislaw - Solaris.fb2", title="Solaris", authors=(("Stanislaw", "Lem"),))
            (root / "._junk.epub").write_bytes(b"\x00\x05\x16\x07")
            return
        make_epub(root / "dune.epub", title="Dune", authors=("Frank Herbert",), date="1965", chapters=("Dune text.",))
        (root / "Broken.epub").write_bytes(b"PK not a zip")
