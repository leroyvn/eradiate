import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from eradiate.config import EradiateSettings, ProgressLevel, loaded_files, settings
from eradiate.frame import AzimuthConvention


def test_progress_level_conversion():
    # Conversion from string is supported
    assert ProgressLevel.convert("kernel") is ProgressLevel.KERNEL
    with pytest.raises(KeyError):
        ProgressLevel.convert("foo")

    # Conversion of integer is supported
    assert ProgressLevel.convert(2) is ProgressLevel.KERNEL

    # AzimuthConvention instances pass through
    assert ProgressLevel.convert(ProgressLevel.KERNEL) is ProgressLevel.KERNEL

    # Other types raise
    with pytest.raises(TypeError):
        ProgressLevel.convert(1.0)


def test_settings():
    """
    This test contains a few checks on settings.
    """
    assert isinstance(settings.azimuth_convention, AzimuthConvention)
    assert isinstance(settings.progress, ProgressLevel)


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """
    Neutralize ambient settings sources: unset 'ERADIATE_*' environment
    variables (except 'ERADIATE_SOURCE_DIR', required for validation) and move
    to an empty directory.
    """
    for var in list(os.environ):
        if var.startswith("ERADIATE_") and var != "ERADIATE_SOURCE_DIR":
            monkeypatch.delenv(var)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_settings_env(clean_env, monkeypatch):
    monkeypatch.setenv("ERADIATE_PROGRESS", "none")
    monkeypatch.setenv("ERADIATE_PATH", "/a:/b")
    monkeypatch.setenv("ERADIATE_RNG_SEED", "random")
    monkeypatch.setenv(
        "ERADIATE_ABSORPTION_DATABASE__ERROR_HANDLING__P__BOUNDS", "warn"
    )

    s = EradiateSettings()
    assert s.progress is ProgressLevel.NONE
    assert s.path == [Path("/a"), Path("/b")]
    assert s.rng_seed == "random"
    assert s.absorption_database.error_handling["p"]["bounds"] == "warn"


@pytest.mark.parametrize(
    "fname, content",
    [
        ("eradiate.toml", 'progress = "kernel"\noffline = true\n'),
        ("eradiate.yml", "progress: kernel\noffline: true\n"),
    ],
)
def test_settings_file(clean_env, monkeypatch, fname, content):
    (clean_env / fname).write_text(content)

    # Settings files are discovered by walking up from the current working
    # directory
    subdir = clean_env / "sub"
    subdir.mkdir()
    monkeypatch.chdir(subdir)

    s = EradiateSettings()
    assert s.progress is ProgressLevel.KERNEL
    assert s.offline is True
    assert loaded_files == [clean_env / fname]


def test_settings_env_overrides_file(clean_env, monkeypatch):
    (clean_env / "eradiate.toml").write_text('progress = "kernel"\n')
    monkeypatch.setenv("ERADIATE_PROGRESS", "none")

    s = EradiateSettings()
    assert s.progress is ProgressLevel.NONE


def test_settings_unknown_key_warns(clean_env):
    (clean_env / "eradiate.toml").write_text("unknown_key = 1\n")

    with pytest.warns(UserWarning, match="Unknown setting 'unknown_key'"):
        s = EradiateSettings()

    # The unknown key does not affect known settings
    assert s.progress is ProgressLevel.SPECTRAL_LOOP


@pytest.mark.parametrize("value", ["foo", "-1"])
def test_settings_rng_seed_invalid(clean_env, monkeypatch, value):
    monkeypatch.setenv("ERADIATE_RNG_SEED", value)

    with pytest.raises(ValidationError, match="rng_seed"):
        EradiateSettings()


def test_settings_dict_access():
    # Dict-style access with case-insensitive dotted keys is supported
    assert settings["data_path"] == settings.data_path
    assert (
        settings["ABSORPTION_DATABASE.ERROR_HANDLING"]
        == settings.absorption_database.error_handling
    )
    assert settings.get("azimuth_convention") is settings.azimuth_convention
    assert settings.get("unknown", "default") == "default"

    with pytest.raises(KeyError):
        settings["unknown"]


def test_settings_assignment():
    # Assignment triggers validation and conversion
    old = settings.progress
    try:
        settings.progress = 0
        assert settings.progress is ProgressLevel.NONE
        settings.progress = "kernel"
        assert settings.progress is ProgressLevel.KERNEL
    finally:
        settings.progress = old
