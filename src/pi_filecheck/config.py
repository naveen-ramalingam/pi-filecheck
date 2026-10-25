"""Small TOML configuration with strict types and atomic writes."""

import json
import os
import tempfile
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .paths import absolute, directory, mountpoint, reject_symlinks


def config_path():
    return (
        absolute(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        / "pi-filecheck/config.toml"
    )


def state_dir():
    return (
        absolute(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
        / "pi-filecheck"
    )


@dataclass
class Config:
    scan_path: str = field(default_factory=lambda: str(Path.home() / "Downloads"))
    required_mount: str = ""
    recursive: bool = False
    sha256: bool = False
    timeout_seconds: int = 3600
    confirm_bytes: int = 10 * 1024**3
    max_expanded_bytes: int = 1024**4
    report_dir: str = field(default_factory=lambda: str(state_dir() / "reports"))

    def validate(self):
        for key, value in asdict(self).items():
            if key in ("recursive", "sha256"):
                if type(value) is not bool:
                    raise ValueError(f"{key} must be true or false")
            elif key in ("timeout_seconds", "confirm_bytes", "max_expanded_bytes"):
                if type(value) is not int or value <= 0:
                    raise ValueError(f"{key} must be a positive integer")
            elif not isinstance(value, str) or (
                not Path(value).is_absolute() and (value or key != "required_mount")
            ):
                raise ValueError(f"{key} must be an absolute path")
        if self.timeout_seconds > 86400:
            raise ValueError("timeout_seconds must be at most 86400")
        return self


def load():
    path = reject_symlinks(config_path())
    if not path.exists():
        return Config().validate()
    if path.stat().st_size > 65536:
        raise ValueError("Configuration exceeds 64 KiB")
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    unknown = set(values) - set(Config.__dataclass_fields__)
    if unknown:
        raise ValueError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
    return Config(**values).validate()


def save(config):
    config.validate()
    path = reject_symlinks(config_path())
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    body = "# Pi FileCheck user configuration\n" + "".join(
        f"{key} = {json.dumps(value, ensure_ascii=True)}\n" for key, value in asdict(config).items()
    )
    # json booleans/ASCII strings/integers are also valid TOML values here.
    fd, temp = tempfile.mkstemp(prefix=".config-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def set_value(config, key, value):
    if key not in Config.__dataclass_fields__:
        raise ValueError(f"Unknown configuration key: {key}")
    if key in ("recursive", "sha256"):
        if value.lower() not in ("true", "false"):
            raise ValueError("Use true or false")
        value = value.lower() == "true"
    elif key in ("timeout_seconds", "confirm_bytes", "max_expanded_bytes"):
        value = int(value)
    elif key == "scan_path":
        if not Path(value).expanduser().is_absolute():
            raise ValueError("Saved scan_path must be absolute")
        value = str(directory(value))
        mount = mountpoint(value)
        config.required_mount = str(mount) if mount != Path("/") else ""
    else:
        if value and not Path(value).expanduser().is_absolute():
            raise ValueError(f"{key} must be an absolute path")
        value = str(absolute(value)) if value else ""
    setattr(config, key, value)
    save(config)
    return config
