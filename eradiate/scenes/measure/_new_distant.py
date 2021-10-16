import re
import typing as t

import attr
import numpy as np
import xarray as xr
from pinttr.util import always_iterable

import eradiate

from ._core import Measure
from ._pipeline import PipelineStep
from ..._mode import ModeFlags
from ...attrs import documented, parse_docs
from ...exceptions import UnsupportedModeError
from ...units import unit_context_config as ucc
from ...units import unit_context_kernel as uck

# ------------------------------------------------------------------------------
#                       Post-processing pipeline steps
# ------------------------------------------------------------------------------


def _spectral_dims():
    if eradiate.mode().has_flags(ModeFlags.ANY_MONO):
        return (
            (
                "w",
                {
                    "standard_name": "wavelength",
                    "long_name": "wavelength",
                    "units": ucc.get("wavelength"),
                },
            ),
        )
    elif eradiate.mode().has_flags(ModeFlags.ANY_CKD):
        return (
            ("bin", {"standard_name": "ckd_name", "long_name": "CKD bin"}),
            ("index", {"standard_name": "ckd_index", "long_name": "CKD index"}),
        )
    else:
        raise UnsupportedModeError


@parse_docs
@attr.s
class Assemble(PipelineStep):
    """
    Assemble raw kernel results (output as nested dictionaries) into an xarray
    dataset.

    This pipeline step takes a nested dictionary produced by the spectral loop
    of an :class:`.Experiment` and repackages it as a :class:`~xarray.Dataset`.
    The top-level spectral index is mapped to mode-dependent spectral
    coordinates. Results from the sensors part of a single measurement are
    mapped to specified sensor dimensions, which can then be further processed
    by aggregation steps. Film dimensions are left unmodified and retain their
    metadata.

    An ``img`` variable hold sensor results; a ``spp`` variable holds sample
    count if ``"spp"`` is part of the requested sensor dimensions.
    """

    prefix: str = documented(
        attr.ib(default=r".*"),
        default="r'.*'",
        type="str",
        init_type="str, optional",
        doc="Prefix string used to match sensor IDs. The default value will "
        "match anything.",
    )

    sensor_dims: t.Sequence = documented(
        attr.ib(
            factory=list,
            validator=attr.validators.instance_of((list, tuple)),
        ),
        default="[]",
        type="list of (str or tuple)",
        init_type="list of (str or tuple), optional",
        doc="List of sensor dimensions. Each list item can be a string or a "
        "(dimension, metadata) pair.",
    )

    img_var: t.Union[str, t.Tuple[str, t.Dict]] = documented(
        attr.ib(default="img"),
        default="img",
        type="str or tuple[str, dict]",
        init_type="str or tuple[str, dict], optional",
        doc="Name of the variable containing sensor data. Optionally, a "
        "(name, metadata) pair can be passed.",
    )

    def transform(self, x: t.Dict) -> xr.Dataset:
        # Basic preparation
        prefix = self.prefix

        sensor_dims = []
        sensor_dim_metadata = {}

        for y in self.sensor_dims:
            if isinstance(y, str):
                sensor_dims.append(y)
                sensor_dim_metadata[y] = {}
            else:
                sensor_dims.append(y[0])
                sensor_dim_metadata[y[0]] = y[1]

        spectral_dims = []
        spectral_dim_metadata = {}

        for y in _spectral_dims():
            if isinstance(y, str):
                spectral_dims.append(y)
                spectral_dim_metadata[y] = {}
            else:
                spectral_dims.append(y[0])
                spectral_dim_metadata[y[0]] = y[1]

        sensor_datasets = []

        regex = re.compile(
            r"\_".join(
                [prefix]
                + [rf"{sensor_dim}(?P<{sensor_dim}>\d*)" for sensor_dim in sensor_dims]
            )
        )

        # Loop on spectral indexes
        for spectral_index in x.keys():
            # Loop on sensors
            for sensor_id, sensor_data in x[spectral_index]["values"].items():
                # Collect data
                ds = sensor_data.copy(deep=False)
                spp = x[spectral_index]["spp"][sensor_id]

                # Set spectral coordinates
                spectral_coords = {
                    spectral_dim: [spectral_coord]
                    for spectral_dim, spectral_coord in zip(
                        spectral_dims, always_iterable(spectral_index)
                    )
                }

                # Detect sensor coordinates
                match = regex.match(sensor_id)

                if match is None:
                    raise RuntimeError(
                        "could not detect requested sensor dimensions in "
                        f"sensor ID '{sensor_id}' using regex '{regex.pattern}'; "
                        "this could be due to incorrect values or order of "
                        "'sensor_dims'"
                    )

                sensor_coords = {
                    f"{sensor_dim}_index": [int(match.group(sensor_dim))]
                    for sensor_dim in sensor_dims
                }

                # Add spp dimension even though sample count split did not
                # produce any extra sensor
                if "spp" not in sensor_dims:
                    spectral_coords["spp_index"] = [0]

                # Add spectral and sensor dimensions to img array
                ds["img"] = ds.img.expand_dims(dim={**spectral_coords, **sensor_coords})

                # Package spp in a data array
                ds["spp"] = ("spp_index", [spp])

                sensor_datasets.append(ds)

        # Combine all the data
        with xr.set_options(keep_attrs=True):
            result = xr.merge(sensor_datasets)

        # Apply metadata to new dimensions
        for sensor_dim in sensor_dims:
            result[f"{sensor_dim}_index"].attrs = sensor_dim_metadata[sensor_dim]

        if "spp" not in sensor_dims:
            result["spp_index"].attrs = {
                "standard_name": "spp_index",
                "long_name": "SPP index",
            }

        for spectral_dim in spectral_dims:
            result[spectral_dim].attrs = spectral_dim_metadata[spectral_dim]

        # Apply metadata to data variables
        if isinstance(self.img_var, str):
            img_var = self.img_var
            img_var_metadata = {}
        else:
            img_var = self.img_var[0]
            img_var_metadata = self.img_var[1]

        result = result.rename({"img": img_var})
        result[img_var].attrs.update(img_var_metadata)

        result["spp"].attrs = {
            "standard_name": "sample_count",
            "long_name": "sample count",
        }

        return result


@attr.s
class AggregateSampleCount(PipelineStep):
    """
    Aggregate sample count.

    This post-processing pipeline step aggregates sample counts:

    * it computes the average of sensor values weighted by the sample count;
    * it sums the ``spp`` dimension.

    No dimension is dropped during this step.
    """

    def transform(self, x: t.Any) -> t.Any:
        with xr.set_options(keep_attrs=True):
            result = x.weighted(x.spp).mean(dim="spp_index")
            result["spp"] = x.spp.sum()

        return result


@parse_docs
@attr.s
class MultiDistantMeasure(Measure):
    directions: np.ndarray = documented(
        attr.ib(
            default=np.array([[0.0, 0.0, -1.0]]),
            converter=np.array,
        ),
        doc="A sequence of 3-vectors specifying distant sensing directions.",
        type="ndarray",
        init_type="array-like",
        default="[[0, 0, -1]]",
    )

    post_processing_pipeline = attr.ib(
        factory=lambda: [
            (
                "assemble",
                Assemble(
                    sensor_dims=("spp",),
                    img_var=(
                        "lo",
                        {
                            "units": uck.get("radiance"),
                            "standard_name": "leaving_radiance",
                            "long_name": "leaving radiance",
                        },
                    ),
                ),
            ),
            ("aggregate_sample_count", AggregateSampleCount()),
            # ("map_viewing_angles", MapViewingAngles()),
            # ("add_illumination", AddIllumination()),
            # ("compute_reflectance", ComputeReflectance()),
        ]
    )

    def sensor_coords(self):
        """
        Compute sensor coordinates.
        """
        return {"spp": ("spp", self._split_spps(), {"long_name": "sample count"})}

    def sensor_id(self, i_spp=None):
        """
        Assemble a sensor ID from indexes on sensor coordinates.
        """
        components = [self.id]

        if i_spp is not None:
            components.append(f"spp{i_spp}")

        return "_".join(components)
