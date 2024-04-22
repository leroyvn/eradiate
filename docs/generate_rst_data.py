from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import attrs

import eradiate
from eradiate.plot import dashboard_particle_dataset

eradiate.plot.set_style()

# Auto-generation disclaimer text
HEADER = dedent(
    """
    ..
      This file was automatically generated by docs/generate_rst_data.py. The

          make docs-rst-data

      target automates this process.
    """
).strip()


@attrs.define
class ParticleRadpropsInfo:
    keyword: str
    fname: str
    description: str | None = attrs.field(default=None)
    aliases: list[str] = attrs.field(factory=list)


PARTICLE_RADPROPS = [
    ParticleRadpropsInfo(
        "govaerts_2021-continental-extrapolated",
        "spectra/particles/govaerts_2021-continental-extrapolated.nc",
    ),
    ParticleRadpropsInfo(
        "govaerts_2021-desert-extrapolated",
        "spectra/particles/govaerts_2021-desert-extrapolated.nc",
    ),
]


def write_if_modified(filename, content):
    filename.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(filename, "r") as f:
            existing = f.read()
    except OSError:
        existing = None

    if existing == content:
        print(f"Skipping unchanged '{filename.name}'")

    else:
        print(f"Generating '{filename.name}'")
        with open(filename, "w") as f:
            f.write(content)


def savefig(fig, filename: Path, **kwargs):
    filename.parent.mkdir(exist_ok=True, parents=True)
    fig.savefig(filename, **kwargs)


def generate_particle_radprops_visual(
    info: ParticleRadpropsInfo, outfile: Path, force=False
):
    # Create dashboards for a dataset
    if outfile.is_file() and not force:  # Skip if file exists
        return

    with eradiate.data.open_dataset(info.fname) as ds:
        print(f"Generating particle radiative property visual in '{outfile}'")
        fig, _ = dashboard_particle_dataset(ds)
        savefig(fig, outfile, dpi=150)


def generate_particle_radprops_summary():
    # Write a table with the list of particle radiative property datasets
    outdir_visuals = Path(__file__).parent.absolute() / "rst/data/fig"
    outfile_rst = (
        Path(__file__).parent.absolute() / "rst/data/generated/aerosols_particles.rst"
    )
    print(f"Generating particle radiative property index in '{outfile_rst}'")

    sections = [
        dedent(
            """
Aerosol / particle single-scattering radiative properties
=========================================================

A particle radiative single-scattering property dataset provides collision 
coefficients and scattering phase matrix data for a given particle type. 
Eradiate's built-in particle radiative property datasets are managed by the 
data store (see :ref:`sec-data-intro` for details).

Format
------

* **Format** ``xarray.Dataset`` (in-memory), NetCDF (storage)
* **Dimensions**

  * ``w``: radiation wavelength
  * ``mu``: scattering angle cosine
  * ``i``: scattering phase matrix row index
  * ``j``: scattering phase matrix column index

* **Coordinates** (all dimension coordinates; when relevant, ``units`` are 
  required and specified in the units metadata field)

  * ``w`` float [length]
  * ``mu`` float [dimensionless]
  * ``i``,  ``j`` int

* **Data variables** (when relevant, units are required and  specified in the 
  units metadata field)

  * ``sigma_t`` (``w``): volume extinction coefficient [length^-1]
  * ``albedo`` (``w``): single-scattering albedo [dimensionless]
  * ``phase`` (``w``, ``mu``, ``i``, ``j``): scattering phase matrix 
    [steradian^-1]

* **Conventions**

  * Phase matrix components use C-style indexing (from 0).

.. dropdown:: Full validation schema

   .. literalinclude:: /resources/data_schemas/particle_dataset_v1.yml
"""
        ).strip()
    ]

    lst = ["\n".join(["Dataset index", "-------------"])]

    for info in PARTICLE_RADPROPS:
        outfile_visual = outdir_visuals / f"{info.keyword}.png"

        generate_particle_radprops_visual(info, outfile_visual)
        title = f"``{info.keyword}``"
        item = "\n".join(
            [
                title,
                "^" * len(title),
                "",
                f"Filename: ``{info.fname}``",
                "",
                f"{info.description if info.description else '*No description available.*'}",
                "",
                f".. image:: ../fig/{info.keyword}.png",
            ]
        )
        lst.append(item)

    sections.append("\n\n".join(lst))
    result = "\n\n".join([HEADER] + sections) + "\n"
    write_if_modified(outfile_rst, result)


if __name__ == "__main__":
    generate_particle_radprops_summary()
