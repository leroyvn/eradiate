"""
Measured quasi-diffuse material.
"""

import typing as t
from pathlib import Path

import numpy as np
import numpy.typing as npt


def write_binary(data: npt.ArrayLike, filename: t.Union[str, Path]) -> None:
    data = np.array(data)
    with open(filename, "wb") as f:
        # Bytes 1-3: ASCII bytes 'M', 'Q' and 'D'
        f.write(b"M")
        f.write(b"Q")
        f.write(b"D")

        # Byte 4: file format version
        f.write(np.uint8(1).tobytes())

        # Bytes 5-8: encoding information
        f.write(np.int32(1).tobytes())

        # Bytes 8-24: axis lengths
        f.write(np.array(data.shape, dtype="int32").tobytes())

        # Bytes 25+: data
        f.write(data.astype(np.float32).tobytes())


def read_binary(filename: t.Union[str, Path]) -> np.ndarray:
    with open(filename, "rb") as f:
        metadata = {}

        metadata["fmt"] = f.read(3).decode("ascii")
        metadata["version"] = np.squeeze(np.frombuffer(f.read(1), dtype="int8"))
        metadata["enc"] = np.squeeze(np.frombuffer(f.read(4), dtype="int32"))

        shape = np.fromfile(f, dtype="int32", count=4)
        data = np.reshape(np.fromfile(f, dtype="float32"), shape)

        return data, metadata


def test_round_trip(filename):
    n_theta_i = 4
    n_theta_o = 8
    n_phi_d = 16
    n_wavelengths = 3
    shape = (n_theta_i, n_theta_o, n_phi_d, n_wavelengths)
    values = np.random.random(shape).astype("float32")

    write_binary(values, filename)
    data, metadata = read_binary(filename)

    assert metadata["fmt"] == "MQD"
    assert metadata["version"] == 1
    assert metadata["enc"] == 1

    assert np.all(data.shape == shape)
    assert np.all(data == values)


def main():
    test_round_trip("test.bsdf")


if __name__ == "__main__":
    main()
