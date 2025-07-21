import mitsuba as mi
import pytest

from eradiate.contexts import KernelContext
from eradiate.two import SceneObject


def f(ctx: KernelContext):
    if ctx.si.w.m_as("nm") == 440.0:
        return 0.5
    elif ctx.si.w.m_as("nm") == 550.0:
        return 1.0
    elif ctx.si.w.m_as("nm") == 660.0:
        return 0.5
    else:
        raise ValueError


def test_01_scene_object_construct(mode_mono):
    d = {"type": "sphere"}
    for mi_obj in [mi.load_dict(d), d]:
        obj = SceneObject(mi_obj)
        assert obj.scene_parameters is not None
        assert repr(obj) == "SceneObject(_object=<mi.Shape object [Sphere]>)"


def test_02_scene_object_register_updater(mode_mono):
    obj = SceneObject({"type": "uniform", "value": 0.5})

    # Regular method call form
    obj.register_updater(f, "value")
    assert "value" in obj._updaters

    with pytest.raises(ValueError, match="Parameter '' not found"):
        obj.register_updater(f)

    with pytest.raises(ValueError, match="Parameter 'doesnt_exist' not found"):
        obj.register_updater(f, "doesnt_exist")

    # Decorator form
    obj._updaters.clear()

    @obj.register_updater(param="value")
    def _f(ctx: KernelContext):
        return f(ctx)

    assert "value" in obj._updaters


def test_03_scene_object_update(mode_mono):
    obj = SceneObject({"type": "uniform", "value": 0.5})
    obj.register_updater(f, "value")
    ctx = KernelContext({"w": 550.0})
    assert obj.update(ctx, return_dict=True) == {"value": 1.0}
    obj.update(ctx)
    assert obj.scene_parameters["value"] == 1.0


def test_04_scene_object_id(mode_mono):
    obj = SceneObject({"type": "uniform", "value": 0.5})
    assert obj.id() == "__root__"
    obj.set_id("my_spectrum")
    assert obj.id() == "my_spectrum"
