import csv
import io
import json
import os

import pytest

from pi_filecheck.models import Result, exit_code
from pi_filecheck.reporting import csv_text, exclusive_write, human, json_text, report, save_bundle


def test_csv_and_json_validity(root):
    results = [Result(str(root / '日本語, "quote".pkg'), reason="=CMD()", diagnostics="x\ny")]
    document = report(results, root)
    assert json.loads(json_text(document))["results"][0]["path"] == results[0].path
    rows = list(csv.DictReader(io.StringIO(csv_text(document))))
    assert len(rows) == 1
    assert rows[0]["reason"].startswith("'=")
    assert rows[0]["path"] == results[0].path
    assert rows[0]["status"] == "UNKNOWN"


def test_terminal_escape_sequences_are_escaped():
    output = human([Result("evil\x1b[2J\nname.pkg", reason="\u202e")])
    assert "\x1b" not in output
    assert "\\u001b" in output
    assert "\\u202e" in output


def test_existing_and_hardlinked_file_not_overwritten(root):
    source = root / "source"
    source.write_text("original", encoding="utf-8")
    alias = root / "report.json"
    os.link(source, alias)
    with pytest.raises(FileExistsError):
        exclusive_write(alias, "new")
    assert source.read_text() == "original"


def test_report_directory_symlink_refused(root):
    alias = root / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError):
        save_bundle(report([], root), alias)


def test_reports_are_unique_and_private(root):
    first = save_bundle(report([], root), root / "reports")
    second = save_bundle(report([], root), root / "reports")
    assert first != second
    assert first.stat().st_mode & 0o777 == 0o700
    assert (first / "report.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert (first / "report.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "states,expected",
    [
        ([], 0),
        (["PASS"], 0),
        (["PASS", "UNKNOWN"], 1),
        (["FAIL"], 1),
        (["SKIP"], 1),
        (["FAIL", "ERROR"], 2),
    ],
)
def test_exit_policy(states, expected):
    assert exit_code([Result("x", status=s) for s in states]) == expected
