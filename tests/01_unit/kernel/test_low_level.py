# TODO: Move these tests to more appropriate locations once prototyping is over

import mitsuba as mi
import pytest

from eradiate.kernel._kernel_dict_new import mi_traverse

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
