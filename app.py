"""Hydrogel Diagram Maker - point-and-click app.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import io

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from hydrogel_diagrams import io as hio
from hydrogel_diagrams import mpl_plots, plotly_plots
from hydrogel_diagrams.examples import example_plots, example_project
from hydrogel_diagrams.model import (ROLE_PREFIX, ROLES, SAMPLE_COL,
                                     TOTAL_COL, Project)
from hydrogel_diagrams.prepare import prepare, query_frame
from hydrogel_diagrams.spec import Axis, PlotSpec, Region

st.set_page_config(page_title="Hydrogel Diagram Maker", layout="wide")

KIND_LABELS = {"ternary": "Ternary diagram", "scatter3d": "3D scatter",
               "scatter2d": "2D scatter"}
NONE = "(none)"
COLORMAPS = ["viridis", "plasma", "cividis", "magma", "Blues", "Reds",
             "RdBu_r", "coolwarm"]


# ---------------------------------------------------------------------- #
# state
# ---------------------------------------------------------------------- #
def init_state():
    ss = st.session_state
    if "project" not in ss:
        ss.project = example_project()
        ss.presets = example_plots()
        ss.editor_version = 0
        ss.loaded_file = None
        load_spec_into_widgets(next(iter(ss.presets.values())))


def project() -> Project:
    return st.session_state.project


def bump_editors():
    st.session_state.editor_version += 1


def pretty_term(t: str) -> str:
    if t.startswith(ROLE_PREFIX):
        role = t[len(ROLE_PREFIX):]
        return "All water" if role == "water" else f"All {role}s (sum)"
    return t


# ---------------------------------------------------------------------- #
# sidebar: open / save
# ---------------------------------------------------------------------- #
def sidebar():
    ss = st.session_state
    st.sidebar.title("Hydrogel Diagram Maker")
    st.sidebar.caption("Water + filler + host + guest polymer formulations")

    st.sidebar.subheader("Open")
    up = st.sidebar.file_uploader("Excel (.xlsx) or CSV", type=["xlsx", "xls",
                                                               "csv"])
    if up is not None:
        data = up.getvalue()
        sheet = None
        if not up.name.lower().endswith(".csv"):
            try:
                tabs = _data_tabs(data)
            except Exception as exc:  # noqa: BLE001
                st.sidebar.error(f"Could not read file: {exc}")
                tabs = []
            if len(tabs) > 1:
                options = tabs + [hio.ALL_SHEETS]
                if ss.get("sheet_pick") not in options:
                    ss.sheet_pick = options[0]
                sheet = st.sidebar.selectbox(
                    "Which tab?", options, key="sheet_pick",
                    help="Each tab is loaded as its own set of samples. "
                         "'All tabs combined' stacks them and adds a "
                         "'dataset' column you can color or highlight by.")
        if ss.loaded_file != (up.file_id, sheet):
            try:
                proj, plots = hio.load(io.BytesIO(data), filename=up.name,
                                       sheet=sheet)
                ss.project = proj
                ss.presets.update(plots)
                bump_editors()
                where = f" from '{sheet}'" if sheet else ""
                st.sidebar.success(f"Loaded {len(proj.samples)} samples and "
                                   f"{len(proj.components)} components"
                                   f"{where}. Check the roles on the "
                                   "Components tab.")
            except Exception as exc:  # noqa: BLE001
                st.sidebar.error(f"Could not read file: {exc}")
            ss.loaded_file = (up.file_id, sheet)

    c1, c2 = st.sidebar.columns(2)
    if c1.button("Demo data", width="stretch"):
        ss.project = example_project()
        bump_editors()
        st.rerun()
    if c2.button("Blank project", width="stretch"):
        p = Project()
        p.add_component("water", "water")
        ss.project = p
        bump_editors()
        st.rerun()

    st.sidebar.subheader("Save")
    # files are built when clicked; the callables can't read session_state
    # then, so bind what they need now
    proj, presets = project(), dict(ss.presets)
    st.sidebar.download_button(
        "Download project (.xlsx)",
        lambda: hio.save(proj, plots=presets),
        file_name="hydrogel_project.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch")
    st.sidebar.download_button(
        "Download samples (.csv)",
        lambda: proj.samples.to_csv(index=False).encode(),
        file_name="hydrogel_samples.csv", mime="text/csv",
        width="stretch")
    st.sidebar.caption("The .xlsx keeps components, samples and saved plot "
                       "settings, so you can reopen it here later or edit it "
                       "in Excel.")


# ---------------------------------------------------------------------- #
# tab 1: components
# ---------------------------------------------------------------------- #
def components_tab():
    p = project()
    st.markdown(
        "Every ingredient is a **component** with a **role**. Add as many "
        "fillers, hosts or guest polymers as you like; plots can use single "
        "components or the sum of a whole role (e.g. *all hosts*). "
        "Color is optional (hex like `#E69F00`) and is used when points are "
        "colored by that component's type.")
    original = p.components_frame()
    with st.form(f"components_form_{st.session_state.editor_version}"):
        edited = st.data_editor(
            original, num_rows="dynamic", width="stretch",
            column_config={
                "name": st.column_config.TextColumn("name", required=True),
                "role": st.column_config.SelectboxColumn(
                    "role", options=list(ROLES), required=True,
                    default="other"),
                "color": st.column_config.TextColumn("color (optional)"),
                "notes": st.column_config.TextColumn("notes"),
            }, key=f"comp_editor_{st.session_state.editor_version}")
        submitted = st.form_submit_button("Apply component changes",
                                          type="primary")
    if submitted:
        try:
            p.apply_component_table(original, edited)
            bump_editors()
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))

    unassigned = [c for c in p.property_names
                  if pd.api.types.is_numeric_dtype(p.samples[c])]
    if unassigned:
        with st.expander("Turn a numeric column into a component"):
            st.caption("Imported columns that weren't recognised as "
                       "ingredients are treated as measured properties.")
            col = st.selectbox("Column", unassigned)
            role = st.selectbox("Role", ROLES, index=1)
            if st.button("Make component"):
                p.add_component(col, role)
                bump_editors()
                st.rerun()


# ---------------------------------------------------------------------- #
# tab 2: samples
# ---------------------------------------------------------------------- #
def samples_tab():
    p = project()
    st.markdown(
        "One row per formulation. Component columns are **wt %**. Extra "
        "columns are measured **properties** (modulus, swelling, gelled?...). "
        "Click a cell to edit, use the **+** row at the bottom to add "
        "samples, select rows and press Delete to remove them. "
        "Press **Save table** when done.")
    col_cfg = {SAMPLE_COL: st.column_config.TextColumn("sample",
                                                       required=True)}
    for c in p.component_names:
        role = p.get_component(c).role
        col_cfg[c] = st.column_config.NumberColumn(
            f"{c} [{role}]", min_value=0.0, max_value=100.0, format="%.2f",
            default=0.0)
    for c in p.property_names:
        if pd.api.types.is_bool_dtype(p.samples[c]):
            col_cfg[c] = st.column_config.CheckboxColumn(c, default=False)

    with st.form(f"samples_form_{st.session_state.editor_version}"):
        edited = st.data_editor(
            p.samples, num_rows="dynamic", width="stretch",
            column_config=col_cfg, height=420,
            key=f"samples_editor_{st.session_state.editor_version}")
        submitted = st.form_submit_button("Save table", type="primary")
    if submitted:
        edited = edited.reset_index(drop=True)
        missing = edited[SAMPLE_COL].isna() | (edited[SAMPLE_COL] == "")
        edited.loc[missing, SAMPLE_COL] = [f"S{i + 1}" for i in
                                           edited.index[missing]]
        for c in p.component_names:
            edited[c] = pd.to_numeric(edited[c], errors="coerce").fillna(0.0)
        p.samples = edited
        bump_editors()
        st.rerun()

    totals = p.totals()
    off = p.samples.loc[(totals - 100).abs() > 0.5, SAMPLE_COL]
    c1, c2 = st.columns([3, 1])
    if len(off):
        c1.warning(f"{len(off)} sample(s) don't add up to 100 wt %: "
                   + ", ".join(off.astype(str).head(12)))
    else:
        c1.success("All samples add up to 100 wt %.")
    if p.components_by_role("water") and c2.button(
            "Fill water to 100 %", help="Water = 100 - everything else"):
        p.fill_water_to_100()
        bump_editors()
        st.rerun()

    st.subheader("Property columns")
    a, b, c, d = st.columns([2, 1, 1, 2])
    new = a.text_input("New property name", placeholder="e.g. G' (kPa)")
    kind = b.selectbox("Type", ["number", "yes/no", "text"])
    c.write("")
    c.write("")
    if c.button("Add column") and new:
        try:
            p.add_property(new, kind)
            bump_editors()
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if p.property_names:
        rm = d.selectbox("Remove property", [NONE] + p.property_names)
        if rm != NONE and d.button(f"Remove '{rm}'"):
            p.remove_property(rm)
            bump_editors()
            st.rerun()


# ---------------------------------------------------------------------- #
# tab 3: plot
# ---------------------------------------------------------------------- #
def load_spec_into_widgets(spec: PlotSpec):
    ss = st.session_state
    ss.w_kind = spec.kind
    for i in range(3):
        ax = spec.axes[i] if i < len(spec.axes) else Axis([])
        ss[f"w_ax{i}"] = list(ax.terms)
        ss[f"w_ax{i}_label"] = ax.label
    ss.w_size = spec.size_by or NONE
    ss.w_color = spec.color_by or NONE
    ss.w_marker = spec.marker_by or NONE
    ss.w_highlight = spec.highlight
    ss.w_dim = spec.dim_others
    ss.w_hull = spec.hull_of_highlight
    ss.w_hull_label = spec.hull_label
    ss.w_regions = "\n".join(f"{r.name} | {r.vertices_text()} | {r.color}"
                             for r in spec.regions)
    ss.w_title = spec.title
    ss.w_labels = spec.label_points
    ss.w_size_range = (int(spec.size_range[0]), int(spec.size_range[1]))
    ss.w_cmap = spec.colormap
    ss.w_norm = spec.normalize_3d
    ss.w_zoom = spec.zoom
    for i in range(3):
        ss[f"w_tmin{i}"] = float(spec.ternary_min[i])
    ss.w_grid = spec.show_grid


def spec_from_widgets() -> PlotSpec:
    ss = st.session_state
    kind = ss.w_kind
    n = 2 if kind == "scatter2d" else 3
    axes = [Axis(list(ss[f"w_ax{i}"]), ss[f"w_ax{i}_label"]) for i in range(n)]
    regions = []
    for line in ss.w_regions.splitlines():
        if not line.strip():
            continue
        parts = [x.strip() for x in line.split("|")]
        if len(parts) < 2:
            raise ValueError(f"region line needs 'name | vertices': {line!r}")
        color = parts[2] if len(parts) > 2 and parts[2] else "#7fb3d5"
        regions.append(Region.parse(parts[0], parts[1], color))
    pick = lambda v: "" if v == NONE else v  # noqa: E731
    return PlotSpec(kind=kind, axes=axes, size_by=pick(ss.w_size),
                    color_by=pick(ss.w_color), marker_by=pick(ss.w_marker),
                    highlight=ss.w_highlight, dim_others=ss.w_dim,
                    hull_of_highlight=ss.w_hull, hull_label=ss.w_hull_label,
                    regions=regions, title=ss.w_title,
                    label_points=ss.w_labels,
                    size_range=tuple(float(v) for v in ss.w_size_range),
                    colormap=ss.w_cmap, normalize_3d=ss.w_norm,
                    zoom=ss.w_zoom,
                    ternary_min=tuple(ss[f"w_tmin{i}"] for i in range(3)),
                    show_grid=ss.w_grid)


def plot_tab():
    ss = st.session_state
    p = project()
    opts = p.plot_options()
    left, right = st.columns([1, 2.2], gap="large")

    with left:
        with st.expander("Saved plot settings", expanded=False):
            names = list(ss.presets)
            choice = st.selectbox("Preset", names) if names else None
            c1, c2 = st.columns(2)
            if choice and c1.button("Load"):
                load_spec_into_widgets(ss.presets[choice])
                st.rerun()
            if choice and c2.button("Delete"):
                del ss.presets[choice]
                st.rerun()
            new_name = st.text_input("Save current settings as")
            if st.button("Save settings") and new_name:
                try:
                    ss.presets[new_name] = spec_from_widgets()
                    st.success("Saved (included in the project .xlsx).")
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))

        st.radio("Plot type", list(KIND_LABELS), key="w_kind",
                 format_func=KIND_LABELS.get, horizontal=True)
        kind = ss.w_kind
        n = 2 if kind == "scatter2d" else 3

        term_opts = opts["roles"] + opts["components"]
        if kind != "ternary":
            term_opts += opts["properties"] + [TOTAL_COL]
        names = (["Top corner", "Bottom-left corner", "Bottom-right corner"]
                 if kind == "ternary" else ["X axis", "Y axis", "Z axis"])
        st.markdown("**Axes** - pick one or more items per axis; "
                    "several items are added together.")
        for i in range(n):
            key = f"w_ax{i}"
            ss[key] = [t for t in ss.get(key, []) if t in term_opts]
            c1, c2 = st.columns([3, 2])
            c1.multiselect(names[i], term_opts, key=key,
                           format_func=pretty_term)
            c2.text_input("label", key=f"{key}_label",
                          placeholder="auto")
        if kind == "ternary":
            st.caption("Ternary axes are renormalised to 100 % of the three "
                       "groups you chose (e.g. leave water out to show the "
                       "solids composition).")
            st.checkbox("Zoom in on the data", key="w_zoom",
                        help="Draws only the part of the triangle that holds "
                             "your samples - useful when water is an axis "
                             "and everything sits near one corner.")
            if not ss.w_zoom:
                with st.expander("Manual zoom: axis minimums (%)"):
                    mc = st.columns(3)
                    for i in range(3):
                        mc[i].number_input(names[i].split()[0], 0.0, 99.0,
                                           step=5.0, key=f"w_tmin{i}")
        else:
            st.checkbox("Normalise axes to fractions of their sum",
                        key="w_norm")

        st.markdown("**Encoding**")
        enc_opts = ([NONE] + opts["properties"] + opts["derived"]
                    + opts["components"] + opts["roles"])
        for key in ("w_size", "w_color", "w_marker"):
            if ss.get(key) not in enc_opts:
                ss[key] = NONE
        st.selectbox("Dot size", enc_opts, key="w_size",
                     format_func=pretty_term)
        st.selectbox("Color", enc_opts, key="w_color",
                     format_func=pretty_term,
                     help="Text / yes-no columns become categories; numbers "
                          "get a color scale.")
        st.selectbox("Marker shape (categories)",
                      [NONE] + opts["derived"][:-1] + opts["properties"],
                      key="w_marker")

        st.markdown("**Highlight**")
        st.text_input(
            "Highlight samples where...", key="w_highlight",
            placeholder="gelled == True",
            help="A condition on any column, e.g. `gelled == True`, "
                 "`laponite > 1 and all_host >= 3`, "
                 "``` `filler type` == \"laponite\" ```. "
                 "Wrap names with spaces or symbols in back-ticks.")
        with st.popover("Columns you can use"):
            st.write(", ".join(f"`{c}`" for c in query_frame(p).columns))
        c1, c2 = st.columns(2)
        c1.checkbox("Grey out the others", key="w_dim")
        c2.checkbox("Shade region around them", key="w_hull",
                    disabled=kind == "scatter3d")
        if ss.w_hull:
            st.text_input("Region label", key="w_hull_label")
        st.text_area(
            "Shaded regions (one per line)", key="w_regions", height=80,
            placeholder="gel window | 20,30,50; 40,30,30; 30,10,60 | #7fb3d5",
            help="name | vertices | color. Ternary vertices are "
                 "top,left,right values (any units, normalised); 2D vertices "
                 "are x,y. Separate vertices with ';'.")

        with st.expander("Style"):
            st.text_input("Title", key="w_title")
            st.slider("Dot size range", 5, 900, key="w_size_range")
            st.selectbox("Color scale", COLORMAPS, key="w_cmap")
            st.checkbox("Label points with sample names", key="w_labels")
            st.checkbox("Grid", key="w_grid")

    with right:
        try:
            spec = spec_from_widgets()
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return
        if any(not a.terms for a in spec.axes):
            st.info("Choose something for every axis to draw the plot.")
            return
        try:
            prep = prepare(p, spec)
            fig = plotly_plots.plot(p, spec)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not draw the plot: {exc}")
            return
        view = st.radio("View", ["Interactive", "Static (publication)"],
                        horizontal=True, label_visibility="collapsed")
        if view == "Interactive":
            st.plotly_chart(fig, width="stretch")
        else:
            static = mpl_plots.plot(p, spec)
            st.pyplot(static, width="stretch")
            plt.close(static)

        st.markdown("**Download**")
        cols = st.columns(5)
        for col, fmt in zip(cols[:3], ("png", "svg", "pdf")):
            # files are only rendered when the button is clicked
            col.download_button(
                fmt.upper(),
                lambda fmt=fmt: mpl_plots.to_bytes(mpl_plots.plot(p, spec),
                                                   fmt),
                file_name=f"hydrogel_{spec.kind}.{fmt}",
                width="stretch")
        cols[3].download_button("HTML", lambda: plotly_plots.to_html(fig),
                                file_name=f"hydrogel_{spec.kind}.html",
                                mime="text/html", width="stretch")
        cols[4].download_button("Settings", spec.to_json(),
                                file_name="plot_settings.json",
                                mime="application/json",
                                width="stretch")
        if prep.dropped:
            st.caption("Not shown (no data for these axes): "
                       + ", ".join(prep.dropped))
        if prep.outside:
            st.caption("Outside the zoomed area: " + ", ".join(prep.outside))


@st.cache_data(show_spinner=False)
def _data_tabs(data: bytes) -> list[str]:
    return hio.sheet_names(io.BytesIO(data))


def help_tab():
    st.markdown("""
### Quick start
1. **Components** - list every ingredient with its role
   (`water`, `filler`, `host`, `guest`, `other`). Add a second guest polymer
   or a third host just by adding a row.
2. **Samples** - type in wt % for each formulation (or upload an Excel
   sheet in the sidebar) and add property columns for what you measured.
3. **Plot** - choose a plot type, what goes on each axis, and what dot
   size / color / marker shape mean. Download PNG/SVG/PDF for papers or
   HTML for an interactive version.

### Excel format
Sheet `samples`: a `sample` column, one column per component (wt %), then
property columns. Sheet `components`: `name`, `role`, `color`, `notes`.
A workbook can have several data tabs (e.g. one per hydrogel system); after
uploading, pick one under **Which tab?** or choose *all tabs combined* to
compare them (a `dataset` column tells you which tab each sample came from).
Try `examples/mock_hydrogel_data.xlsx`.
If there is no `components` sheet, roles are guessed from the column names
(e.g. *laponite* → filler, *beta-CD* → host, *PEG* → guest) and can be fixed
on the Components tab. *Download project* in the sidebar gives you a
ready-made template.

### Axis ideas
* Ternary of **all fillers / all hosts / all guests** = solids composition.
* Ternary of **water / all fillers / host + guest** = whole formulation.
* 3D of **filler wt% / host wt% / guest wt%** with dot size = modulus.
* 2D of **all hosts** vs a property such as **G'**.

### Highlight examples
* `gelled == True`
* `` `G' (kPa)` > 10 ``
* `` `filler type` == "laponite" and all_host > 2 ``
""")


# ---------------------------------------------------------------------- #
def main():
    init_state()
    # Streamlit forgets the value of a widget that isn't drawn in a run
    # (e.g. the Z axis while in 2D mode); re-store them so nothing is lost.
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith("w_"):
            st.session_state[k] = st.session_state[k]
    sidebar()
    t1, t2, t3, t4 = st.tabs(["1 · Components", "2 · Samples", "3 · Plot",
                              "Help"])
    with t1:
        components_tab()
    with t2:
        samples_tab()
    with t3:
        plot_tab()
    with t4:
        help_tab()


main()
