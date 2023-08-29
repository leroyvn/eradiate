import mitsuba as mi
import pytest

from eradiate.scenes.bsdfs import LambertianBSDF
from eradiate.scenes.spectra import UniformSpectrum
from eradiate.test_tools.types import check_scene_element


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"reflectance": 0.5}],
    ids=["noargs", "args"],
)
def test_lambertian_construct(modes_all, kwargs):
    # Default constructor
    bsdf = LambertianBSDF(**kwargs)
    assert isinstance(bsdf.reflectance, UniformSpectrum)


def test_lambertian_kdict(modes_all_double):
    bsdf = LambertianBSDF(reflectance=0.75)
    mi_obj = check_scene_element(bsdf, mi.BSDF)
    assert mi_obj.parameters["reflectance.value"] == 0.75

    bsdf = LambertianBSDF(id="diffuse", reflectance=0.3)
    print(bsdf.kdict)
    print(bsdf)
    mi_obj = check_scene_element(bsdf, mi.BSDF)
    print(mi_obj.parameters)
    assert mi_obj.parameters["diffuse_reflectance.value"] == 0.3
