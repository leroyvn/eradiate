import mitsuba as mi

from eradiate.two import Scene, SceneObject


def test_scene_classvar(mode_mono):
    assert list(Scene._OBJECT_TYPES_TO_SECTIONS.keys()) == list(
        Scene._SECTIONS_TO_OBJECT_TYPES.values()
    )
    assert list(Scene._OBJECT_TYPES_TO_SECTIONS.values()) == list(
        Scene._SECTIONS_TO_OBJECT_TYPES.keys()
    )


def test_scene_construct(mode_mono):
    diffuse = SceneObject({"type": "diffuse", "id": "diffuse"})
    # IMPORTANT: IDs are unreliable, they will be mutated if the object is
    # included in a scene dict (id is set here to prove the point!)

    scene = Scene(
        bsdfs={"diffuse": diffuse},
        shapes={"sphere": SceneObject({"type": "sphere", "bsdf": diffuse()})},
    )
    scene.init()

    # Object ID is mutated and set to a scene-controlled value
    assert scene.bsdfs["diffuse"].id() == "02_bsdf_diffuse"
    assert diffuse.id() == "02_bsdf_diffuse"

    # SceneObjects behave as pointers
    assert scene.bsdfs["diffuse"]() is diffuse()

    # Updates to a referenced object propagate
    params = mi.traverse(scene.mi_scene)
    diffuse.scene_parameters.update({"reflectance.value": 1.0})
    assert scene.bsdfs["diffuse"].scene_parameters["reflectance.value"] == 1.0
    assert params["02_bsdf_diffuse.reflectance.value"] == 1.0


def test_scene_rebuild(mode_mono):
    mi.set_log_level(mi.LogLevel.Trace)
    scene = Scene(
        shapes={"sphere": SceneObject({"type": "cube"})},
    )
    scene.init()
    print(scene.mi_scene)
    i = mi.load_dict({"type": "path"})
    s = mi.load_dict({"type": "perspective"})
    mi.render(scene.mi_scene, sensor=s, integrator=i, spp=256)
