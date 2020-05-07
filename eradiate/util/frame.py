import attr
import numpy as np


def cos_angle_to_direction(cos_theta, phi):
    """Convert a zenith cosine and azimuth angle pair to a direction.

    :param (float) theta: Zenith angle cosine [dimensionless].
        Convention: 1 corresponds to zenith, -1 corresponds to nadir.
    :param (float) phi: Azimuth angle [radian].
        Convention: :math:`2 \pi` corresponds to the X axis.

    :return (np.ndarray): Direction corresponding to the angular parameters.
    """
    sin_theta = np.sqrt(1.0 - cos_theta * cos_theta)
    sin_phi, cos_phi = np.sin(phi), np.cos(phi)
    return np.array([sin_theta * cos_phi, sin_theta * sin_phi, cos_theta])


def angles_to_direction(theta, phi):
    """Convert a zenith and azimuth angle pair to a direction.

    :param (float) theta: Zenith angle [radian].
        Convention: 0 corresponds to zenith, :math:`\pi` corresponds to nadir.
    :param (float) phi: Azimuth angle [radian].
        Convention: :math:`2 \pi` corresponds to the X axis.

    :return (np.ndarray): Direction corresponding to the angular parameters.
    """
    return cos_angle_to_direction(np.cos(theta), phi)


def degree_to_radians(wi):
    """Convert a pair of angles in degrees to radians
    """
    return [wi[0]/180.*np.pi, wi[1]/180.*np.pi]