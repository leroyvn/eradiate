import re

import pytest

from eradiate.kernel import (
    KernelDictionary,
    KernelSceneParameterFlag,
    KernelSceneParameterMap,
    dict_parameter,
    scene_parameter,
)


def test_kernel_dict_template_init():
    template = KernelDictionary({"foo": {"bar": 0}, "bar": {"baz": {"qux": 0}}})
    assert template.data == {"foo.bar": 0, "bar.baz.qux": 0}


def test_kernel_dict_template_setitem():
    template = KernelDictionary()
    template["foo"] = {"bar": 0}
    template["bar"] = {"baz": {"qux": 0}}
    template["baz"] = 0
    assert template.data == {"foo.bar": 0, "bar.baz.qux": 0, "baz": 0}


def test_kernel_dict_template_render():
    template = KernelDictionary(
        {
            "foo.bar": 0,
            "bar": dict_parameter(lambda ctx: ctx),
            "baz": dict_parameter(lambda ctx: ctx),
        }
    )

    assert template.render(ctx=1, nested=True) == {
        "foo": {"bar": 0},
        "bar": 1,
        "baz": 1,
    }

    assert template.render(ctx=1, nested=False) == {"foo.bar": 0, "bar": 1, "baz": 1}


def test_kpmap_render():
    kpmap = KernelSceneParameterMap(
        {
            "foo": 0,
            "bar": scene_parameter(lambda ctx: ctx, KernelSceneParameterFlag.GEOMETRIC),
            "baz": scene_parameter(lambda ctx: ctx, KernelSceneParameterFlag.SPECTRAL),
        }
    )

    # If no flags are passed, all params are rendered
    result = kpmap.render(ctx=1, flags=KernelSceneParameterFlag.ALL)
    assert result["bar"] == 1 and result["baz"] == 1

    # If a flag is passed, only the corresponding params are rendered
    with pytest.raises(ValueError, match=re.escape("Unevaluated parameters: ['bar']")):
        kpmap.render(ctx=1, flags=KernelSceneParameterFlag.SPECTRAL, strict=True)

    # If strict is set to False, unused parameters are dropped
    result = kpmap.render(ctx=1, flags=KernelSceneParameterFlag.SPECTRAL, strict=False)
    assert result["baz"] == 1
    assert "bar" not in result


def test_kpmap_keep_remove():
    template = KernelSceneParameterMap(
        {
            "foo": 0,
            "foo.bar": 1,
            "bar": scene_parameter(lambda ctx: ctx, KernelSceneParameterFlag.GEOMETRIC),
            "baz": scene_parameter(lambda ctx: ctx, KernelSceneParameterFlag.SPECTRAL),
        }
    )

    # We can remove or keep selected parameters
    pmap = template.copy()
    pmap.remove(r"foo.*")
    assert pmap.keys() == {"bar", "baz"}

    pmap = template.copy()
    pmap.keep(r"foo.*")
    assert pmap.keys() == {"foo", "foo.bar"}
