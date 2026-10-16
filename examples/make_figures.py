"""Make figures from a script instead of the app.

    python examples/make_figures.py                       # demo data
    python examples/make_figures.py my_project.xlsx       # your workbook

Figures are written to ./output/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hydrogel_diagrams import Axis, PlotSpec, Region  # noqa: E402
from hydrogel_diagrams import io as hio  # noqa: E402
from hydrogel_diagrams import mpl_plots, plotly_plots  # noqa: E402
from hydrogel_diagrams.examples import example_project  # noqa: E402

if len(sys.argv) > 1:
    project, saved_plots = hio.load(sys.argv[1])
else:
    project, saved_plots = example_project(), {}

# Adding things in code works too:
# project.add_component("CB[7]", "host")
# project.add_sample("new-1", water=90, laponite=2, **{"CB[7]": 3},
#                    properties={"G' (kPa)": 12.0, "gelled": True})

plots = {
    "ternary_solids": PlotSpec(
        kind="ternary",
        axes=[Axis(["role:filler"]), Axis(["role:host"]), Axis(["role:guest"])],
        size_by="G' (kPa)", color_by="filler type", marker_by="host type",
        title="Solids composition"),
    "ternary_whole": PlotSpec(
        kind="ternary",
        axes=[Axis(["role:water"]), Axis(["role:filler"]),
              Axis(["role:host", "role:guest"], label="host + guest")],
        color_by="gelled", highlight="gelled == True", hull_of_highlight=True,
        zoom=True),  # water-rich samples: zoom to the corner they sit in
    "ternary_regions": PlotSpec(
        kind="ternary",
        axes=[Axis(["role:filler"]), Axis(["role:host"]), Axis(["role:guest"])],
        color_by="G' (kPa)",
        regions=[Region("target", [(10, 40, 50), (30, 30, 40), (20, 20, 60)])]),
    "scatter3d": PlotSpec(
        kind="scatter3d",
        axes=[Axis(["role:filler"]), Axis(["role:host"]), Axis(["role:guest"])],
        size_by="G' (kPa)", color_by="swelling ratio"),
}
plots.update(saved_plots)

out = Path("output")
out.mkdir(exist_ok=True)
for name, spec in plots.items():
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    mpl_plots.save(project, spec, out / f"{safe}.png")
    plotly_plots.save_html(project, spec, out / f"{safe}.html")
    print("wrote", out / f"{safe}.png", "and .html")
