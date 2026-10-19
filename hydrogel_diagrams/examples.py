"""A made-up demo dataset and a few ready-made plot settings.

The numbers are synthetic and only meant to show what the plots look like.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .model import Project
from .spec import Axis, PlotSpec, Region


def example_project(seed: int = 7) -> Project:
    rng = np.random.default_rng(seed)
    p = Project()
    p.add_component("water", "water", "#56B4E9")
    p.add_component("laponite", "filler", "#E69F00")
    p.add_component("silica NP", "filler", "#D55E00")
    p.add_component("beta-CD", "host", "#009E73")
    p.add_component("alpha-CD", "host", "#CC79A7")
    p.add_component("PAAm-Ad", "guest", "#0072B2")

    for i in range(30):
        filler = ["laponite", "silica NP"][i % 2]
        host = ["beta-CD", "alpha-CD"][(i // 2) % 2]
        f = rng.uniform(0.2, 4.0)
        h = rng.uniform(0.5, 6.0)
        g = rng.uniform(1.0, 9.0)
        # a toy "rule": enough host + guest and some filler -> gel
        gelled = bool(h + g > 6 and f > 0.8)
        modulus = (0.4 * f * (h + g) + rng.normal(0, 0.8)) * (3 if gelled else 0.3)
        p.add_sample(
            f"HG{i + 1:02d}",
            **{filler: round(f, 2), host: round(h, 2), "PAAm-Ad": round(g, 2)},
            properties={
                "G' (kPa)": round(max(modulus, 0.05), 2),
                "swelling ratio": round(rng.uniform(5, 40) / (1 + f), 1),
                "gelled": gelled,
            },
        )
    p.fill_water_to_100()
    return p


def example_plots() -> dict[str, PlotSpec]:
    return {
        "Ternary: filler / host / guest, size = G'": PlotSpec(
            kind="ternary",
            axes=[Axis(["role:filler"]), Axis(["role:host"]), Axis(["role:guest"])],
            size_by="G' (kPa)",
            color_by="filler type",
            marker_by="host type",
            title="Solids composition (water excluded)",
        ),
        "Ternary: gel window highlighted": PlotSpec(
            kind="ternary",
            axes=[Axis(["role:filler"]), Axis(["role:host"]), Axis(["role:guest"])],
            color_by="G' (kPa)",
            highlight="gelled == True",
            hull_of_highlight=True,
            hull_label="gel region (hull of gelled samples)",
            regions=[Region("target window", [(10, 40, 50), (30, 30, 40),
                                              (20, 20, 60)], "#7fb3d5", 0.3)],
            title="Which formulations gel?",
        ),
        "Ternary: whole formulation, zoomed": PlotSpec(
            kind="ternary",
            axes=[Axis(["role:water"]), Axis(["role:filler"]),
                  Axis(["role:host", "role:guest"], label="host + guest")],
            color_by="gelled",
            size_by="swelling ratio",
            zoom=True,
            title="Including water (zoomed to the data)",
        ),
        "3D: wt% of filler, host, guest": PlotSpec(
            kind="scatter3d",
            axes=[Axis(["role:filler"]), Axis(["role:host"]), Axis(["role:guest"])],
            size_by="G' (kPa)",
            color_by="gelled",
            marker_by="filler type",
            title="Raw wt% (size = G')",
        ),
    }


def quick_plots(project: Project) -> dict[str, PlotSpec]:
    """Ready-made plots that work with whatever data is loaded.

    They only use roles (all fillers, all hosts, ...) and pick the first
    yes/no and numeric property columns for color and dot size.
    """
    has = {r: bool(project.components_by_role(r))
           for r in ("water", "filler", "host", "guest")}
    props = project.property_names
    yes_no = [c for c in props
              if project.samples[c].dropna().map(type).isin([bool]).all()
              and project.samples[c].notna().any()]
    numeric = [c for c in props if c not in yes_no
               and pd.api.types.is_numeric_dtype(project.samples[c])
               and project.samples[c].notna().any()]
    size = numeric[0] if numeric else ""
    flag = yes_no[0] if yes_no else ""
    out = {}
    if has["filler"] and has["host"] and has["guest"]:
        out["Triangle: fillers / hosts / guests"] = PlotSpec(
            kind="ternary",
            axes=[Axis(["role:filler"]), Axis(["role:host"]),
                  Axis(["role:guest"])],
            size_by=size, color_by="filler type", marker_by="host type",
            title="Solids composition (water left out)")
        if has["water"]:
            out["Triangle with water (zoomed in)"] = PlotSpec(
                kind="ternary",
                axes=[Axis(["role:water"]), Axis(["role:filler"]),
                      Axis(["role:host", "role:guest"], label="host + guest")],
                size_by=size, color_by=flag or "filler type", zoom=True,
                title="Whole formulation")
        out["3D: amount of filler, host, guest"] = PlotSpec(
            kind="scatter3d",
            axes=[Axis(["role:filler"]), Axis(["role:host"]),
                  Axis(["role:guest"])],
            size_by=size, color_by=flag or "filler type",
            marker_by="filler type", title="Amounts (wt %)")
    if has["host"] and numeric:
        out[f"2D: hosts vs {numeric[0]}"] = PlotSpec(
            kind="scatter2d", axes=[Axis(["role:host"]), Axis([numeric[0]])],
            color_by=flag or "filler type", title="")
    return out


def blank_template() -> Project:
    """A starter project: one ingredient per role and one example row."""
    p = Project()
    p.add_component("water", "water", "", "the solvent")
    p.add_component("my filler", "filler", "", "rename me, e.g. Laponite")
    p.add_component("my host", "host", "", "rename me, e.g. beta-CD")
    p.add_component("my guest polymer", "guest", "", "rename me, e.g. PEG-Ad")
    p.add_sample("example-1", **{"water": 92, "my filler": 2, "my host": 3,
                                 "my guest polymer": 3},
                 properties={"G' (kPa)": 10.0, "gelled": True})
    return p
