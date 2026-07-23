import mitsuba as mi
import pytest

from eradiate.two.kernel import Scene, SceneObject


@pytest.fixture
def mi_log_level_info():
    log_level = mi.log_level()
    mi.set_log_level(mi.LogLevel.Info)
    yield
    mi.set_log_level(log_level)


@pytest.fixture
def mi_log_print():
    # Temporarily install a custom print-based appender to allow logger output capture

    logger = mi.logger()

    appenders = []
    while logger.appender_count() > 0:
        app = logger.appender(0)
        appenders.append(app)
        logger.remove_appender(app)

    class MyAppender(mi.Appender):
        def append(self, level, text):
            print(text)

    logger.add_appender(MyAppender())

    yield

    logger.clear_appenders()
    for app in appenders:
        logger.add_appender(app)


class TestScene:
    def test_classvar(self, mode_mono):
        assert list(Scene._OBJECT_TYPES_TO_SECTIONS.keys()) == list(
            Scene._SECTIONS_TO_OBJECT_TYPES.values()
        )
        assert list(Scene._OBJECT_TYPES_TO_SECTIONS.values()) == list(
            Scene._SECTIONS_TO_OBJECT_TYPES.keys()
        )

    def test_construct(self, mode_mono):
        diffuse = SceneObject({"type": "diffuse", "id": "diffuse"})
        # IMPORTANT: IDs are unreliable, they will be mutated if the object is
        # included in a scene dict (id is set here to prove the point!)

        scene = Scene(
            materials={"diffuse": diffuse},
            shapes={"sphere": SceneObject({"type": "sphere", "bsdf": diffuse()})},
        )
        scene.init()

        # Object ID is mutated and set to a scene-controlled value
        assert scene.materials["diffuse"].id() == "02_bsdf_diffuse"
        assert diffuse.id() == "02_bsdf_diffuse"

        # SceneObjects behave as pointers
        assert scene.materials["diffuse"]() is diffuse()

        # Updates to a referenced object propagate
        params = mi.traverse(scene.mi_scene)
        diffuse.scene_parameters().update({"reflectance.value": 1.0})
        assert scene.materials["diffuse"].scene_parameters()["reflectance.value"] == 1.0
        assert params["02_bsdf_diffuse.reflectance.value"] == 1.0

    def test_rebuild(self, mode_mono, mi_log_level_info, mi_log_print, capsys):
        if mi.MI_ENABLE_EMBREE:
            pytest.skip("Embree-based Mitsuba builds cannot be tested")

        def rebuilt():
            captured = capsys.readouterr()
            return "Building a SAH kd-tree" in captured.out

        cube = SceneObject({"type": "cube"})
        scene = Scene(shapes={"cube": cube})
        scene.init()
        assert rebuilt()

        # Changing scene parameters from within the scene parameter tree triggers a
        # BVH / kd-tree rebuild
        params = mi.traverse(scene.mi_scene)
        params["03_shape_cube.vertex_positions"] = (
            params["03_shape_cube.vertex_positions"] + 1.0
        )
        params.update()
        assert rebuilt()

        # Changing scene parameters from a "floating" object does not trigger a
        # BVH / kd-tree rebuild
        cube_params = cube.scene_parameters()
        cube_params["vertex_positions"] = cube_params["vertex_positions"] - 1.0
        cube_params.update()
        assert not rebuilt()

        # Changing scene parameters in-place does not trigger a BVH / kd-tree
        # rebuild: this is an issue, but we expect it
        params = mi.traverse(scene.mi_scene)
        params["03_shape_cube.vertex_positions"] += 1.0
        params.update()
        assert not rebuilt()

        # A manual scene parameter update does trigger a BVH / kd-tree rebuild
        scene.mi_scene.parameters_changed()
        assert rebuilt()
