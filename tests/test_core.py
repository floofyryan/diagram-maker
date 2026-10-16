import io

import numpy as np
import pandas as pd
import pytest

from hydrogel_diagrams import Axis, PlotSpec, Project, Region
from hydrogel_diagrams import io as hio
from hydrogel_diagrams import mpl_plots, plotly_plots
from hydrogel_diagrams.examples import example_plots, example_project
from hydrogel_diagrams.model import guess_role
from hydrogel_diagrams.prepare import convex_hull, prepare


@pytest.fixture
def proj():
    p = Project()
    p.add_component("water", "water")
    p.add_component("laponite", "filler")
    p.add_component("silica", "filler")
    p.add_component("bCD", "host")
    p.add_component("PEG", "guest")
    p.add_component("PAAm", "guest")
    p.add_sample("A", water=90, laponite=2, bCD=3, PEG=5,
                 properties={"G": 10.0, "gelled": True})
    p.add_sample("B", water=85, silica=3, laponite=1, bCD=5, PAAm=6,
                 properties={"G": 2.0, "gelled": False})
    return p


def test_resolve_roles_and_sums(proj):
    assert proj.resolve("role:filler").tolist() == [2, 4]
    assert proj.resolve("role:guest").tolist() == [5, 6]
    assert proj.resolve(["bCD", "PEG"]).tolist() == [8, 3 + 5 + 0 - 3]
    assert proj.resolve("PEG + PAAm").tolist() == [5, 6]
    assert proj.resolve("filler type").tolist() == ["laponite",
                                                    "silica + laponite"]
    assert proj.totals().tolist() == [100, 100]


def test_add_rename_remove_components(proj):
    proj.add_component("aCD", "host")            # a second host
    assert proj.components_by_role("host") == ["bCD", "aCD"]
    assert (proj.samples["aCD"] == 0).all()
    proj.rename_component("aCD", "alpha-CD")
    assert "alpha-CD" in proj.samples.columns
    proj.remove_component("alpha-CD")
    assert "alpha-CD" not in proj.samples.columns
    with pytest.raises(KeyError):
        proj.add_sample("C", nope=1)


def test_component_table_edit_keeps_data(proj):
    orig = proj.components_frame()
    edited = orig.copy()
    edited.loc[0, "name"] = "H2O"                 # rename
    edited = edited.drop(index=2)                 # remove silica
    edited.loc[99] = ["CB7", "host", "", ""]      # new
    proj.apply_component_table(orig, edited)
    assert proj.samples["H2O"].tolist() == [90, 85]
    assert "silica" not in proj.samples.columns
    assert proj.get_component("CB7").role == "host"


def test_ternary_normalised(proj):
    spec = PlotSpec("ternary", [Axis(["role:filler"]), Axis(["role:host"]),
                                Axis(["role:guest"])], size_by="G",
                    color_by="gelled", highlight="gelled == True")
    prep = prepare(proj, spec)
    sums = prep.data[["c0", "c1", "c2"]].sum(axis=1)
    assert np.allclose(sums, 1)
    assert prep.color_mode == "category"
    assert prep.data["hl"].tolist() == [True, False]
    assert prep.data["size01"].tolist() == [1.0, 0.0]


def test_highlight_error_is_readable(proj):
    spec = PlotSpec("ternary", [Axis("water"), Axis("bCD"), Axis("PEG")],
                    highlight="nonexistent > 1")
    with pytest.raises(ValueError, match="highlight"):
        prepare(proj, spec)


def test_hull():
    pts = np.array([[0, 0], [1, 0], [0, 1], [0.2, 0.2], [1, 1]])
    assert len(convex_hull(pts)) == 4


@pytest.mark.parametrize("name", list(example_plots()))
def test_examples_render(name):
    p = example_project()
    spec = example_plots()[name]
    for fmt in ("png", "svg"):
        assert mpl_plots.to_bytes(mpl_plots.plot(p, spec), fmt, dpi=50)
    assert "plotly" in plotly_plots.to_html(plotly_plots.plot(p, spec))


@pytest.mark.parametrize("kind", ["ternary", "scatter3d", "scatter2d"])
def test_all_kinds_with_regions(kind, proj):
    n = 2 if kind == "scatter2d" else 3
    axes = [Axis(["role:filler"]), Axis(["role:host"]), Axis(["role:guest"])][:n]
    verts = "1,1,1; 2,1,1; 1,2,1" if kind == "ternary" else "0,0; 1,0; 0,1"
    spec = PlotSpec(kind, axes, color_by="G", marker_by="filler type",
                    regions=[Region.parse("r", verts)], label_points=True,
                    highlight="G > 5", dim_others=False)
    mpl_plots.to_bytes(mpl_plots.plot(proj, spec), "png", dpi=40)
    plotly_plots.plot(proj, spec)


def test_spec_json_roundtrip():
    spec = example_plots()["Ternary: gel window highlighted"]
    again = PlotSpec.from_json(spec.to_json())
    assert again == spec


def test_excel_roundtrip(proj):
    plots = example_plots()
    data = hio.save(proj, plots=plots)
    p2, plots2 = hio.load(io.BytesIO(data), filename="x.xlsx")
    assert p2.component_names == proj.component_names
    assert p2.get_component("bCD").role == "host"
    assert set(plots2) == set(plots)
    pd.testing.assert_series_equal(p2.samples["G"], proj.samples["G"],
                                   check_dtype=False)


def test_csv_import_guesses_roles(tmp_path):
    f = tmp_path / "s.csv"
    f.write_text("name,Water,Laponite RD,beta-CD,PEG-Ad,G' (kPa)\n"
                 "a,90,2,3,5,10\nb,88,3,4,5,12\n")
    p, _ = hio.load(f)
    roles = {c.name: c.role for c in p.components}
    assert roles == {"Water": "water", "Laponite RD": "filler",
                     "beta-CD": "host", "PEG-Ad": "guest"}
    assert p.property_names == ["G' (kPa)"]
    assert p.samples["sample"].tolist() == ["a", "b"]


def test_guess_role():
    assert guess_role("α-CD") == "host"
    assert guess_role("CB[7]") == "host"
    assert guess_role("silica NP") == "filler"
    assert guess_role("swelling ratio") is None
