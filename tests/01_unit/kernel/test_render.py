from itertools import product

import mitsuba as mi
import numpy as np
import pytest

from eradiate import KernelContext
from eradiate.kernel import (
    KernelSceneParameterFlag,
    KernelSceneParameterMap,
    mi_render,
    mi_traverse,
    scene_parameter,
)
from eradiate.spectral.index import SpectralIndex
from eradiate.units import unit_registry as ureg

SCENE_DICTS = {
    "referenced_bsdf": {
        "type": "scene",
        "bsdf": {"type": "diffuse", "id": "my_bsdf"},
        # Leading underscores ensures that shapes will be traverse first
        "_rectangle_1": {
            "type": "rectangle",
            "bsdf": {"type": "ref", "id": "my_bsdf"},
        },
        "_rectangle_2": {
            "type": "rectangle",
            "bsdf": {"type": "ref", "id": "my_bsdf"},
        },
        "_disk_1": {
            "type": "disk",
            "bsdf": {"type": "ref", "id": "my_bsdf"},
        },
        "_disk_2": {
            "type": "disk",
            "bsdf": {"type": "diffuse"},
        },
    }
}


@pytest.mark.parametrize(
    "scene_dict, name_id_override, expected",
    [
        (
            "referenced_bsdf",
            False,
            {
                "_disk_1.bsdf.reflectance.value",
                "_disk_1.to_world",
                "_disk_1.silhouette_sampling_weight",
                "_disk_2.bsdf.reflectance.value",
                "_disk_2.to_world",
                "_disk_2.silhouette_sampling_weight",
                "_rectangle_1.to_world",
                "_rectangle_1.silhouette_sampling_weight",
                "_rectangle_2.to_world",
                "_rectangle_2.silhouette_sampling_weight",
            },
        ),
        (
            "referenced_bsdf",
            "my_bsdf",
            {
                "my_bsdf.reflectance.value",
                "_disk_1.silhouette_sampling_weight",
                "_disk_1.to_world",
                "_disk_2.bsdf.reflectance.value",
                "_disk_2.silhouette_sampling_weight",
                "_disk_2.to_world",
                "_rectangle_1.silhouette_sampling_weight",
                "_rectangle_1.to_world",
                "_rectangle_2.silhouette_sampling_weight",
                "_rectangle_2.to_world",
            },
        ),
    ],
    ids=["referenced_bsdf-no_override", "referenced_bsdf-selected_override"],
)
def test_mi_traverse(mode_mono, scene_dict, name_id_override, expected):
    mi_scene = mi.load_dict(SCENE_DICTS[scene_dict])

    params = mi_traverse(mi_scene, name_id_override=name_id_override)
    assert isinstance(params, mi.SceneParameters)
    assert set(params.keys()) == expected


@pytest.mark.parametrize(
    "scene_dict, name_id_override, expected",
    [
        (
            "referenced_bsdf",
            False,
            {
                "_disk_1.bsdf.reflectance.value",
                "_disk_1.to_world",
                "_disk_1.silhouette_sampling_weight",
                "_disk_2.bsdf.reflectance.value",
                "_disk_2.to_world",
                "_disk_2.silhouette_sampling_weight",
                "_rectangle_1.to_world",
                "_rectangle_1.silhouette_sampling_weight",
                "_rectangle_2.to_world",
                "_rectangle_2.silhouette_sampling_weight",
            },
        ),
        (
            "referenced_bsdf",
            "my_bsdf",
            {
                "_disk_1.silhouette_sampling_weight",
                "_disk_1.to_world",
                "_disk_2.bsdf.reflectance.value",
                "_disk_2.silhouette_sampling_weight",
                "_disk_2.to_world",
                "_rectangle_1.silhouette_sampling_weight",
                "_rectangle_1.to_world",
                "_rectangle_2.silhouette_sampling_weight",
                "_rectangle_2.to_world",
                "my_bsdf.reflectance.value",
            },
        ),
    ],
    ids=["referenced_bsdf-no_override", "referenced_bsdf-selected_override"],
)
def test_mi_traverse_name_id_override(
    mode_mono, scene_dict, name_id_override, expected
):
    mi_scene = mi.load_dict(SCENE_DICTS[scene_dict])
    params = mi_traverse(mi_scene, name_id_override=name_id_override)
    assert isinstance(params, mi.SceneParameters)
    assert set(params.keys()) == expected


def test_mi_render(mode_mono):
    mi_scene = mi.load_dict(
        {
            "type": "scene",
            "rectangle": {
                "type": "rectangle",
                "bsdf": {"type": "diffuse", "id": "my_bsdf"},
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
    )

    mi_params = mi_traverse(mi_scene, name_id_override=True)

    kpmap = KernelSceneParameterMap(
        {
            "my_bsdf.reflectance.value": scene_parameter(
                lambda ctx: ctx.kwargs["r"], flags=KernelSceneParameterFlag.ALL
            )
        }
    )

    reflectances = [0.0, 0.5, 1.0]
    wavelengths = [400.0, 500.0, 600.0] * ureg.nm

    result = mi_render(
        mi_scene,
        mi_params,
        kpmap,
        ctxs=[
            KernelContext(si=SpectralIndex.new(w=w), kwargs={"r": r})
            for (r, w) in zip(reflectances, wavelengths)
        ],
    )

    assert isinstance(result, dict)

    expected = []
    actual = []
    for _, (r, w) in enumerate(zip(reflectances, wavelengths)):
        siah = SpectralIndex.new(w=w).as_hashable
        assert isinstance(result[siah]["sensor"], mi.Bitmap)
        expected.append(r / np.pi)
        actual.append(np.squeeze(result[siah]["sensor"]))

    np.testing.assert_allclose(actual, expected)


def test_mi_render_multisensor(mode_mono):
    mi_scene = mi.load_dict(
        {
            "type": "scene",
            "rectangle": {
                "type": "rectangle",
                "bsdf": {"type": "diffuse", "id": "my_bsdf"},
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
    )

    mi_params = mi_traverse(mi_scene, name_id_override=True)

    kpmap = KernelSceneParameterMap(
        {"my_bsdf.reflectance.value": scene_parameter(lambda ctx: ctx.kwargs["r"])}
    )

    reflectances = [0.0, 0.5, 1.0]
    wavelengths = [400.0, 500.0, 600.0] * ureg.nm

    result = mi_render(
        mi_scene,
        mi_params,
        kpmap,
        ctxs=[
            KernelContext(si=SpectralIndex.new(w=w), kwargs={"r": r})
            for (r, w) in zip(reflectances, wavelengths)
        ],
    )

    # The result must be a nested dict with one level-one element per wavelength,
    # and one level-two element per sensor
    assert isinstance(result, dict)
    assert np.allclose(
        list(result.keys()),
        [w.m for w in wavelengths],
    )

    sensors_keys = set()
    for spectral_key in result.keys():
        sensors_keys.update(set(result[spectral_key].keys()))
    assert sensors_keys == {"sensor1", "sensor2"}
    assert all(
        isinstance(result[spectral_key][sensor_key], mi.Bitmap)
        for (spectral_key, sensor_key) in product(result.keys(), sensors_keys)
    )
