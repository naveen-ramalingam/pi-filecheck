import pytest

from pi_filecheck.multipart import group
from pi_filecheck.scanner import discover, scan_entries
from pi_filecheck.scanner import test_file as check_file


@pytest.mark.parametrize(
    "names",
    [
        ["game.part1.rar", "game.part3.rar"],
        ["game.part01.rar", "game.part03.rar"],
        ["game.7z.001", "game.7z.003"],
        ["game.zip.002"],
        ["game.r00", "game.r01"],
        ["game.rar", "game.r01"],
    ],
)
def test_missing_volumes_never_pass(root, config, names):
    for name in names:
        (root / name).write_bytes(b"x")
    assert all(check_file(root / name, config).status == "SKIP" for name in names)


def test_complete_name_sequence_is_not_itself_pass(root, config, monkeypatch):
    for name in ["game.part01.rar", "game.part02.rar"]:
        (root / name).write_bytes(b"x")
    monkeypatch.setattr("pi_filecheck.validators.shutil.which", lambda _: None)
    assert check_file(root / "game.part01.rar", config).status == "UNKNOWN"


def test_legacy_first_volume(root):
    for name in ("game.rar", "game.r00", "game.r01"):
        (root / name).touch()
    volumes = group(root / "game.r01")
    assert volumes.first.name == "game.rar"
    assert not volumes.reason


def test_huge_volume_number_does_not_allocate_large_range(root, config):
    name = "game.part99999999999999999999999999999.rar"
    (root / name).touch()
    assert check_file(root / name, config).status == "SKIP"


def test_duplicate_numbers_are_ambiguous(root, config):
    for name in ("game.part1.rar", "game.part01.rar"):
        (root / name).touch()
    assert check_file(root / "game.part1.rar", config).status == "SKIP"


def test_symlink_volume_never_reaches_tool(root, config, monkeypatch):
    first = root / "game.7z.001"
    first.write_bytes(b"7z\xbc\xaf\x27\x1c")
    (root / "game.7z.002").symlink_to(first)

    def must_not_run(*args, **kwargs):
        pytest.fail("Unsafe volume passed to validator")

    monkeypatch.setattr("pi_filecheck.scanner.validate", must_not_run)
    results = scan_entries(list(discover(root)), config)
    assert all(r.status == "SKIP" for r in results)
