from itertools import product

import mitsuba as mi
import numpy as np

from eradiate import KernelContext
from eradiate.kernel import (
    MitsubaObject,
    UpdateMapTemplate,
    UpdateParameter,
    mi_render,
)
from eradiate.spectral.index import SpectralIndex
from eradiate.units import unit_registry as ureg


def test_mi_render(mode_mono):
    kdict = {
        "type": "scene",
        "rectangle": {
            "type": "rectangle",
            "bsdf": {
                "type": "diffuse",
                "reflectance": {
                    "type": "uniform",
                    "id": "diffuse_reflectance",
                    "value": 1.0,
                },
            },
        },
        "sensor": {
            "type": "distant",
            "film": {"type": "hdrfilm", "width": 1, "height": 1},
            "direction": [0, 0, -1],
            "target": [0, 0, 0],
        },
        "illumination": {
            "type": "directional",
            "direction": [0, 0, -1],
            "irradiance": 1.0,
        },
        "integrator": {"type": "path"},
    }

    umap_template = UpdateMapTemplate(
        {
            "diffuse_reflectance.value": UpdateParameter(
                evaluator=lambda ctx: ctx.kwargs["r"],
                flags=UpdateParameter.Flags.ALL,
            )
        }
    )

    mi_scene = MitsubaObject.from_kdict_template(kdict, umap_template)

    reflectances = [0.0, 0.5, 1.0]
    wavelengths = [400.0, 500.0, 600.0] * ureg.nm

    result = mi_render(
        mi_scene,
        ctxs=[
            KernelContext(si=SpectralIndex.new(w=w), kwargs={"r": r})
            for (r, w) in zip(reflectances, wavelengths)
        ],
    )

    assert isinstance(result, dict)

    expected = []
    actual = []
    for _, (r, w) in enumerate(zip(reflectances, wavelengths)):
        si_hashable = SpectralIndex.new(w=w).as_hashable
        assert isinstance(result[si_hashable]["sensor"], mi.Bitmap)
        expected.append(r / np.pi)
        actual.append(np.squeeze(result[si_hashable]["sensor"]))

    np.testing.assert_allclose(actual, expected)


def test_mi_render_multisensor(mode_mono):
    kdict = {
        "type": "scene",
        "rectangle": {
            "type": "rectangle",
            "bsdf": {
                "type": "diffuse",
                "reflectance": {
                    "type": "uniform",
                    "id": "diffuse_reflectance",
                    "value": 1.0,
                },
            },
        },
        "sensor1": {
            "type": "distant",
            "film": {"type": "hdrfilm", "width": 1, "height": 1},
            "direction": [0, 0, -1],
            "target": [0, 0, 0],
        },
        "sensor2": {
            "type": "distant",
            "film": {"type": "hdrfilm", "width": 1, "height": 1},
            "direction": [0, 0, -1],
            "target": [0, 0, 0],
        },
        "illumination": {
            "type": "directional",
            "direction": [0, 0, -1],
            "irradiance": 1.0,
        },
        "integrator": {"type": "path"},
    }

    umap_template = UpdateMapTemplate(
        {
            "diffuse_reflectance.value": UpdateParameter(
                evaluator=lambda ctx: ctx.kwargs["r"],
                flags=UpdateParameter.Flags.ALL,
            )
        }
    )

    scene = MitsubaObject(mi.load_dict(kdict), umap_template)

    reflectances = [0.0, 0.5, 1.0]
    wavelengths = [400.0, 500.0, 600.0] * ureg.nm

    result = mi_render(
        scene,
        ctxs=[
            KernelContext(si=SpectralIndex.new(w=w), kwargs={"r": r})
            for (r, w) in zip(reflectances, wavelengths)
        ],
    )

    # The result must be a nested dict with one level-one element per wavelength,
    # and one level-two elements per sensor
    assert isinstance(result, dict)
    assert np.allclose(list(result.keys()), wavelengths.m)

    sensors_keys = set()
    for spectral_key in result.keys():
        sensors_keys.update(set(result[spectral_key].keys()))
    assert sensors_keys == {"sensor1", "sensor2"}
    assert all(
        isinstance(result[spectral_key][sensor_key], mi.Bitmap)
        for (spectral_key, sensor_key) in product(result.keys(), sensors_keys)
    )
