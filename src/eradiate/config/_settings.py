"""
This module defines Eradiate's global settings, backed by
`pydantic-settings <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>`__.

Settings are loaded, in decreasing priority, from environment variables
(prefixed with ``ERADIATE_``, using ``__`` as the hierarchical separator) and
from an ``eradiate.toml``, ``eradiate.yaml`` or ``eradiate.yml`` file located
in the current working directory or any of its parents.
"""

from __future__ import annotations

import enum
import os
import warnings
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Mapping, Optional, Union

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

import platformdirs
import ruamel.yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from ..frame import AzimuthConvention


class ProgressLevel(enum.IntEnum):
    """
    An enumeration defining valid progress levels.

    This is an integer enumeration, meaning that levels can be compared to
    numerics.
    """

    @staticmethod
    def convert(value: Any) -> ProgressLevel:
        """
        Attempt conversion of a value to an :class:`.ProgressLevel`
        instance. The conversion protocol is as follows:

        * If ``value`` is a string, it is converted to upper case and passed to
          the indexing operator of :class:`.ProgressLevel`.
        * If ``value`` is an integer, it is passed to the call operator of
          :class:`.ProgressLevel`.
        * If ``value`` is a :class:`.ProgressLevel` instance, it is returned
          without change.
        * Otherwise, the method raises an exception.

        Parameters
        ----------
        value
            Value to attempt conversion of.

        Returns
        -------
        Converted value

        Raises
        ------
        TypeError
            If no conversion protocol exists for ``value``.
        """
        if isinstance(value, ProgressLevel):
            return value
        elif isinstance(value, str):
            return ProgressLevel[value.upper()]
        elif isinstance(value, int):
            return ProgressLevel(value)
        else:
            raise TypeError(f"Cannot convert a {type(value)} instance to ProgressLevel")

    NONE = 0  #: No progress
    SPECTRAL_LOOP = enum.auto()  #: Up to spectral loop level progress
    KERNEL = enum.auto()  #: Up to kernel level progress


def _check_source_dir(value: Optional[Path]) -> None:
    if value is None:
        # Although ``eradiate.kernel._version`` provides
        # :func:`kernel_installed`, we don't use it
        # here: doing so would run ``kernel/__init__.py``, which under
        # ``EAGER_IMPORT=1`` eagerly loads the whole kernel subtree
        # and closes a circular import (kernel -> converters -> data ->
        # _file_resolver -> config). Since kernel detection only relies on
        # package metadata, we inline the lookup performed by
        # :func:`eradiate.kernel._versions.kernel_installed`.
        from importlib.metadata import PackageNotFoundError, version

        try:
            version("eradiate-mitsuba")
            kernel_is_installed = True
        except PackageNotFoundError:
            kernel_is_installed = False

        # Detect Read the Docs build
        rtd = os.environ.get("READTHEDOCS", "") == "True"

        if not kernel_is_installed and not rtd:
            raise RuntimeError(
                "Could not find a suitable production installation for the "
                "Eradiate kernel. This is either because you are using Eradiate "
                "in a production environment without having the eradiate-mitsuba "
                "package installed, or because you are using Eradiate directly "
                "from the sources. In the latter case, please make sure the "
                "'ERADIATE_SOURCE_DIR' environment variable is correctly set to "
                "the Eradiate installation directory. If you are using Eradiate "
                "directly from the sources, you can alternatively source the "
                "provided setpath.sh script. You can install the eradiate-mitsuba "
                "package using 'pip install eradiate-mitsuba'."
            )

    else:
        eradiate_init = value / "src" / "eradiate" / "__init__.py"

        if not eradiate_init.is_file():
            raise RuntimeError(
                f"While configuring Eradiate: could not find {eradiate_init} file. "
                "Please make sure the 'ERADIATE_SOURCE_DIR' environment variable is "
                "correctly set to the Eradiate installation directory. If you are "
                "using Eradiate directly from the sources, you can alternatively "
                "source the provided setpath.sh script. If you wish to use Eradiate "
                "in a production environment, you can install the eradiate-mitsuba "
                "package using 'pip install eradiate-mitsuba' and unset the "
                "'ERADIATE_SOURCE_DIR' environment variable."
            ) from FileNotFoundError(eradiate_init)


def _warn_extra_keys(model: BaseModel) -> BaseModel:
    for key in model.model_extra or ():
        warnings.warn(
            f"Unknown setting {key!r} will be ignored. Check your settings "
            "files and 'ERADIATE_*' environment variables.",
            UserWarning,
        )
    return model


def _find_settings_files() -> List[Path]:
    """
    Search the current working directory, then its parents, for settings files.
    The returned list is sorted by decreasing priority.
    """
    result = []
    cwd = Path.cwd()

    for name in ("eradiate.toml", "eradiate.yaml", "eradiate.yml"):
        for directory in (cwd, *cwd.parents):
            candidate = directory / name
            if candidate.is_file():
                result.append(candidate)
                break

    return result


#: Settings files loaded upon settings initialization.
loaded_files: List[Path] = []


class _FileSettingsSource(PydanticBaseSettingsSource):
    """
    A settings source that reads a TOML or YAML file. Top-level keys are
    lowercased so that file contents are effectively case-insensitive at the
    top level.
    """

    def __init__(self, settings_cls, path: Path):
        super().__init__(settings_cls)
        self._path = path

    def get_field_value(self, field, field_name):  # pragma: no cover
        # Unused: __call__ is overridden
        raise NotImplementedError

    def __call__(self) -> Dict[str, Any]:
        if self._path.suffix == ".toml":
            with open(self._path, "rb") as f:
                data = tomllib.load(f)
        else:
            with open(self._path) as f:
                data = ruamel.yaml.YAML(typ="safe").load(f) or {}

        return {str(k).lower(): v for k, v in data.items()}


def _getattr_nested(obj: Any, key: str) -> Any:
    for part in key.split("."):
        name = part.lower()

        if isinstance(obj, BaseModel):
            if name in type(obj).model_fields or name in (obj.model_extra or ()):
                obj = getattr(obj, name)
            else:
                raise KeyError(key)

        elif isinstance(obj, Mapping):
            if name in obj:
                obj = obj[name]
            elif part in obj:
                obj = obj[part]
            else:
                raise KeyError(key)

        else:
            raise KeyError(key)

    return obj


class AbsorptionDatabaseSettings(BaseModel):
    """
    Settings related to absorption databases.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    error_handling: Dict[str, Dict[str, str]] = Field(
        default_factory=lambda: {
            # Ignore bound errors on pressure and temperature because this
            # usually occurs at high altitude, where the absorption coefficient
            # is very low and can be safely forced to 0
            "p": {"missing": "raise", "scalar": "raise", "bounds": "ignore"},
            "t": {"missing": "raise", "scalar": "raise", "bounds": "ignore"},
            # Ignore missing molecule coordinates, raise on bound error
            "x": {"missing": "ignore", "scalar": "ignore", "bounds": "raise"},
        },
        description="Default error handling configuration applied to absorption "
        "databases instantiated from the factory. Each coordinate (pressure ``p``, "
        "temperature ``t``, concentration ``x``) is associated an error handling "
        "policy for each issue (``missing``, ``scalar``, ``bounds``), which is one "
        'of ``"raise"``, ``"warn"`` or ``"ignore"``.',
    )

    _warn_extras = model_validator(mode="after")(_warn_extra_keys)


class EradiateSettings(BaseSettings):
    """
    Main settings data structure. Fields can be accessed as attributes; the
    dict-style ``settings["some.key"]`` and ``settings.get("some.key")``
    idioms are also supported, with case-insensitive dotted keys.
    """

    model_config = SettingsConfigDict(
        env_prefix="ERADIATE_",
        env_nested_delimiter="__",
        extra="allow",
        validate_assignment=True,
    )

    source_dir: Optional[Path] = Field(
        default=None,
        description="Path to the Eradiate source code directory, if relevant. Takes "
        "the value of the ``ERADIATE_SOURCE_DIR`` environment variable if it is set; "
        "otherwise defaults to ``None``.",
    )

    absorption_database: AbsorptionDatabaseSettings = Field(
        default_factory=AbsorptionDatabaseSettings,
        description="Absorption database settings (see "
        ":class:`.AbsorptionDatabaseSettings`).",
    )

    azimuth_convention: AzimuthConvention = Field(
        default=AzimuthConvention.EAST_RIGHT,
        description="Default azimuth convention.",
    )

    data_url: str = Field(
        default="https://eradiate-data-registry.s3.eu-west-3.amazonaws.com/registry-v1/",
        description="URL of the data registry.",
    )

    data_path: Path = Field(
        default_factory=lambda: Path(platformdirs.user_cache_dir(appname="eradiate")),
        description="Absolute path to the downloaded data folder.",
    )

    offline: bool = Field(
        default=False,
        description="Offline mode switch: if ``True``, data download attempts are "
        "suppressed.",
    )

    path: Annotated[List[Path], NoDecode] = Field(
        default_factory=list,
        description="List of paths prepended to the file resolver (searched first). "
        "The corresponding environment variable uses ``:`` as a separator.",
    )

    progress: ProgressLevel = Field(
        default=ProgressLevel.SPECTRAL_LOOP,
        description="Progress display level.",
    )

    rng_seed: Union[int, Literal["random"]] = Field(
        default=0,
        description="Seed for the RNG seeding sequence (a positive integer or "
        '``"random"``).',
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        files = _find_settings_files()
        loaded_files[:] = files
        return (
            init_settings,
            env_settings,
            *(_FileSettingsSource(settings_cls, f) for f in files),
        )

    @field_validator("source_dir", mode="after")
    @classmethod
    def _resolve_source_dir(cls, value: Optional[Path]) -> Optional[Path]:
        return value.resolve() if value is not None else None

    @field_validator("azimuth_convention", mode="before")
    @classmethod
    def _convert_azimuth_convention(cls, value: Any) -> Any:
        return AzimuthConvention.convert(value)

    @field_validator("path", mode="before")
    @classmethod
    def _convert_path(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.split(":")
        if isinstance(value, Path):
            return [value]
        return value

    @field_validator("progress", mode="before")
    @classmethod
    def _convert_progress(cls, value: Any) -> Any:
        return ProgressLevel.convert(value)

    @field_validator("rng_seed", mode="before")
    @classmethod
    def _convert_rng_seed(cls, value: Any) -> Any:
        if value == "random" or isinstance(value, int):
            pass
        else:
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"While converting rng_seed: cannot convert value "
                    f"({value!r}) to int"
                )

        if isinstance(value, int) and value < 0:
            raise ValueError(
                f"While converting rng_seed: value must be a positive integer "
                f"(got {value})"
            )

        return value

    @model_validator(mode="after")
    def _validate_source_dir(self):
        _check_source_dir(self.source_dir)
        return self

    _warn_extras = model_validator(mode="after")(_warn_extra_keys)

    def __getitem__(self, key: str) -> Any:
        return _getattr_nested(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Return the value of the setting ``key`` (a case-insensitive dotted
        path), or ``default`` if it does not exist.
        """
        try:
            return self[key]
        except KeyError:
            return default


#: Main settings data structure (an :class:`.EradiateSettings` instance).
settings = EradiateSettings()

#: Path to the Eradiate source code directory, if relevant (alias to
#: ``settings.source_dir``, evaluated at import time).
SOURCE_DIR: Optional[Path] = settings.source_dir
