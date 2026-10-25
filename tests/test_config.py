import json
from dataclasses import asdict

import pytest

from pi_filecheck import config as cfg
from pi_filecheck.cli import main
from pi_filecheck.paths import directory


def test_config_roundtrip_unicode(config, root):
    folder = root / 'Sp ace 日本語 "quoted"'
    folder.mkdir()
    cfg.set_value(config, "scan_path", str(folder))
    cfg.set_value(config, "recursive", "true")
    cfg.set_value(config, "sha256", "false")
    assert asdict(cfg.load()) == asdict(config)
    assert cfg.config_path().stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "key,value",
    [
        ("scan_path", "relative"),
        ("recursive", "yes"),
        ("sha256", "1"),
        ("timeout_seconds", "0"),
        ("timeout_seconds", "86401"),
        ("report_dir", "relative"),
        ("not_a_key", "hello"),
    ],
)
def test_invalid_config(config, key, value):
    with pytest.raises(ValueError):
        cfg.set_value(config, key, value)


def test_unknown_config_rejected(config):
    cfg.save(config)
    cfg.config_path().write_text('unknown = "bad"', encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown"):
        cfg.load()


def test_malformed_config(config):
    cfg.save(config)
    cfg.config_path().write_text("not valid TOML", encoding="utf-8")
    with pytest.raises(ValueError):
        cfg.load()


@pytest.mark.parametrize("value", ["0", "false", '""'])
def test_invalid_falsy_scan_path_is_not_silently_defaulted(config, value):
    cfg.save(config)
    cfg.config_path().write_text(f"scan_path = {value}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        cfg.load()


def test_missing_and_unmounted(root, monkeypatch):
    with pytest.raises(ValueError, match="missing"):
        directory(root / "gone")
    monkeypatch.setattr("pi_filecheck.paths.os.path.ismount", lambda p: False)
    with pytest.raises(ValueError, match="not mounted"):
        directory(root, str(root))


def test_one_time_override_preserves_default(config, root, capsys):
    cfg.save(config)
    other = root.parent / "override"
    other.mkdir()
    (other / "game.pkg").write_bytes(b"not a package")
    assert main(["scan", "--path", str(other), "--format", "json", "--no-report"]) == 1
    document = json.loads(capsys.readouterr().out)
    assert document["scan_path"] == str(other)
    assert cfg.load().scan_path == str(root)


def test_override_does_not_require_saved_mount(config, root, capsys):
    config.required_mount = str(root / "disconnected")
    cfg.save(config)
    assert main(["scan", str(root), "--no-report"]) == 0
    capsys.readouterr()
    assert main(["scan", "--no-report"]) == 2


def test_interactive_absolute_folder_selection(config, root, monkeypatch):
    from pi_filecheck.cli import choose_directory

    other = root.parent / "another 日本語 folder"
    other.mkdir()
    answers = iter(["p", str(other), "s"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    choose_directory(config)
    assert cfg.load().scan_path == str(other)
