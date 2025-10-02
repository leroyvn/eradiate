import numpy as np

from eradiate import unit_registry as ureg
from eradiate.experiments import AtmosphereExperiment, CanopyAtmosphereExperiment


def create_rami4atm_hom00_bla_sd2s_m03_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_BLA_SD2S_M03*

    This scenario is based on the ``HOM00_BLA_SD2S_M03_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, scattering only
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-desert``
    - Surface: Black
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 550 nm
    """
    config = {
        "surface": {
            "reflectance": {"value": 0.0, "type": "uniform"},
            "type": "lambertian",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": False,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-desert",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-3",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_whi_s00s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_WHI_S00S_M04*

    This scenario is based on the ``HOM00_WHI_S00S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, scattering only
    - Surface: White
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "reflectance": {"value": 1.0, "type": "uniform"},
            "type": "lambertian",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": False,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_bla_a00s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_BLA_S00S_M04*

    This scenario is based on the ``HOM00_BLA_S00S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, absorption only
    - Surface: Black
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "reflectance": {"value": 0.0, "type": "uniform"},
            "type": "lambertian",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": False,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_e00s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_E00S_M04*

    This scenario is based on the ``HOM00_RPV_E00S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_0c2s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_0C2S_M04*

    This scenario is based on the ``HOM00_RPV_0C2S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-continental``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": False,
                "has_scattering": False,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-continental",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_0c6s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_0C6S_M04*

    This scenario is based on the ``HOM00_RPV_0C6S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.6; aerosol dataset ``govaerts_2021-continental``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": False,
                "has_scattering": False,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.6,
                    "dataset": "govaerts_2021-continental",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_0d2s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_0D2S_M04*

    This scenario is based on the ``HOM00_RPV_0D2S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-desert``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": False,
                "has_scattering": False,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-desert",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_0d6s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_0D6S_M04*

    This scenario is based on the ``HOM00_RPV_0D6S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.6; aerosol dataset ``govaerts_2021-desert``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": False,
                "has_scattering": False,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.6,
                    "dataset": "govaerts_2021-desert",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_sc2s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_SC2S_M04*

    This scenario is based on the ``HOM00_RPV_SC2S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, scattering only
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-continental``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": False,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-continental",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_sc6s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_SC6S_M04*

    This scenario is based on the ``HOM00_RPV_SC6S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, scattering only
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.6; aerosol dataset ``govaerts_2021-continental``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": False,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.6,
                    "dataset": "govaerts_2021-continental",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_sd2s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_SD2S_M04*

    This scenario is based on the ``HOM00_RPV_SD2S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, scattering only
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-desert``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": False,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-desert",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_sd6s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_SD6S_M04*

    This scenario is based on the ``HOM00_RPV_SD6S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, scattering only
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.6; aerosol dataset ``govaerts_2021-desert``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": False,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.6,
                    "dataset": "govaerts_2021-desert",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_ac2s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_AC2S_M04*

    This scenario is based on the ``HOM00_RPV_AC2S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, absorption only
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-continental``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": False,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-continental",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_ac6s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_AC6S_M04*

    This scenario is based on the ``HOM00_RPV_AC6S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, absorption only
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.6; aerosol dataset ``govaerts_2021-continental``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": False,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.6,
                    "dataset": "govaerts_2021-continental",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_ad2s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_AD2S_M04*

    This scenario is based on the ``HOM00_RPV_AD2S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, absorption only
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-desert``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": False,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-desert",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_ad6s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_AD2S_M04*

    This scenario is based on the ``HOM00_RPV_AD6S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, absorption only
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.6; aerosol dataset ``govaerts_2021-desert``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": False,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.6,
                    "dataset": "govaerts_2021-desert",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_lam_ec2s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_LAM_EC2S_M04*

    This scenario is based on the ``HOM00_LAM_EC2S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-continental``
    - Surface: Lambertian
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "reflectance": {"value": 0.02806, "type": "uniform"},
            "type": "lambertian",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-continental",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_ec2s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_EC2S_M04*

    This scenario is based on the ``HOM00_RPV_EC2S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-continental``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-continental",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rli_ec2s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RLI_EC2S_M04*

    This scenario is based on the ``HOM00_RLI_EC2S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-continental``
    - Surface: Ross-thick Li-sparse
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "f_iso": {"value": 0.032171, "type": "uniform"},
            "f_vol": {"value": -0.002886, "type": "uniform"},
            "f_geo": {"value": 0.001949, "type": "uniform"},
            "type": "rossli",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-continental",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_ec6s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_EC6S_M04*

    This scenario is based on the ``HOM00_RPV_EC6S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.6; aerosol dataset ``govaerts_2021-continental``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.6,
                    "dataset": "govaerts_2021-continental",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_ed2s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_ED2S_M04*

    This scenario is based on the ``HOM00_RPV_ED2S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-desert``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-desert",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom00_rpv_ed6s_m04_z30a000_brfpp():
    r"""
    *RAMI4ATM HOM00_RPV_ED6S_M04*

    This scenario is based on the ``HOM00_RPV_ED6S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.6; aerosol dataset ``govaerts_2021-desert``
    - Surface: RPV
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.6,
                    "dataset": "govaerts_2021-desert",
                }
            ],
            "type": "heterogeneous",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": 1000,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return AtmosphereExperiment(**config)


def create_rami4atm_hom45_lam_ec2s_m04_z30a000_brfpp(spp=1000):
    r"""
    *RAMI4ATM HOM45_LAM_EC2S_M04*

    This scenario is based on the ``HOM45_LAM_EC2S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile
    - Aerosol layer: Uniform layer ranging from 0 km to 2 km, with AOT at 550 nm = 0.2; aerosol dataset ``govaerts_2021-continental``
    - Surface: Lambertian
    - Canopy: Homogeneous discrete canopy composed of disks of 5cm radius with a uniform orientation angle. The size of the canopy has been adjusted to avoid large computation times
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    - Uniform discrete canopy
    """
    config = {
        "surface": {
            "reflectance": {"value": 0.02806, "type": "uniform"},
            "type": "lambertian",
        },
        "atmosphere": {
            "molecular_atmosphere": {
                "has_absorption": True,
                "has_scattering": True,
                "type": "molecular",
                "thermoprops": {
                    "identifier": "afgl_1986-us_standard",
                    "z": np.arange(0, 120.05, 0.05) * ureg.km,
                },
                "absorption_data": "monotropa",
            },
            "particle_layers": [
                {
                    "bottom": 0,
                    "bottom_units": "meter",
                    "top": 2000,
                    "top_units": "meter",
                    "distribution": {"type": "uniform"},
                    "tau_ref": 0.2,
                    "dataset": "govaerts_2021-continental",
                }
            ],
            "type": "heterogeneous",
        },
        "canopy": {
            "padding": 20,
            "lai": 3.0,
            "leaf_radius": 0.05,
            "leaf_radius_units": "meter",
            "l_horizontal": 5,
            "l_horizontal_units": "meter",
            "l_vertical": 2.0,
            "l_vertical_units": "meter",
            "nu": 1.0,
            "mu": 1.0,
            "leaf_reflectance": 0.05653,
            "leaf_transmittance": 0.01692,
            "construct": "homogeneous",
            "type": "discrete_canopy",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-75, 76, 2),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": spp,
                "target": {
                    "type": "rectangle",
                    "xmin": -2.5,
                    "xmax": 2.5,
                    "ymin": -2.5,
                    "ymax": 2.5,
                    "z": 2.0,
                },
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "piecewise_volpath", "moment": True},
    }

    return CanopyAtmosphereExperiment(**config)


registry = {
    "hom00_whi_s00s_m04_z30a000_brfpp": create_rami4atm_hom00_whi_s00s_m04_z30a000_brfpp,
    "hom00_bla_a00s_m04_z30a000_brfpp": create_rami4atm_hom00_bla_a00s_m04_z30a000_brfpp,
    "hom00_rpv_e00s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_e00s_m04_z30a000_brfpp,
    "hom00_rpv_0c2s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_0c2s_m04_z30a000_brfpp,
    "hom00_rpv_0c6s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_0c6s_m04_z30a000_brfpp,
    "hom00_rpv_0d2s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_0d2s_m04_z30a000_brfpp,
    "hom00_rpv_0d6s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_0d6s_m04_z30a000_brfpp,
    "hom00_rpv_sc2s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_sc2s_m04_z30a000_brfpp,
    "hom00_rpv_sc6s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_sc6s_m04_z30a000_brfpp,
    "hom00_rpv_sd2s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_sd2s_m04_z30a000_brfpp,
    "hom00_rpv_sd6s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_sd6s_m04_z30a000_brfpp,
    "hom00_rpv_ac2s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_ac2s_m04_z30a000_brfpp,
    "hom00_rpv_ac6s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_ac6s_m04_z30a000_brfpp,
    "hom00_rpv_ad2s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_ad2s_m04_z30a000_brfpp,
    "hom00_rpv_ad6s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_ad6s_m04_z30a000_brfpp,
    "hom00_lam_ec2s_m04_z30a000_brfpp": create_rami4atm_hom00_lam_ec2s_m04_z30a000_brfpp,
    "hom00_rpv_ec2s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_ec2s_m04_z30a000_brfpp,
    "hom00_rli_ec2s_m04_z30a000_brfpp": create_rami4atm_hom00_rli_ec2s_m04_z30a000_brfpp,
    "hom00_rpv_ec6s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_ec6s_m04_z30a000_brfpp,
    "hom00_rpv_ed2s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_ed2s_m04_z30a000_brfpp,
    "hom00_rpv_ed6s_m04_z30a000_brfpp": create_rami4atm_hom00_rpv_ed6s_m04_z30a000_brfpp,
    "hom45_lam_ec2s_m04_z30a000_brfpp": create_rami4atm_hom45_lam_ec2s_m04_z30a000_brfpp,
}
