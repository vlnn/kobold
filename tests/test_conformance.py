from hoard.testing import Conformance, make_epub, make_fb2

from kobold import KIND


class TestConformance(Conformance):
    kind = KIND

    def make_samples(self, storage, root):
        if storage == "nook":
            make_epub(
                root / "Dick, Philip K. - Ubik (1969).epub",
                title="Ubik",
                authors=("Philip K. Dick",),
                date="1969",
                chapters=("Ubik text.",),
            )
            return
        if storage == "vault":
            make_fb2(root / "Lem, Stanislaw - Solaris.fb2", title="Solaris", authors=(("Stanislaw", "Lem"),))
            (root / "._junk.epub").write_bytes(b"\x00\x05\x16\x07")
            return
        make_epub(root / "dune.epub", title="Dune", authors=("Frank Herbert",), date="1965", chapters=("Dune text.",))
        (root / "Broken.epub").write_bytes(b"PK not a zip")
