"""Hydrogel Diagram Maker - point-and-click app.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import ast
import io
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from hydrogel_diagrams import io as hio
from hydrogel_diagrams import mpl_plots, plotly_plots
from hydrogel_diagrams.examples import (blank_template, example_plots,
                                        example_project, quick_plots)
from hydrogel_diagrams.model import (ROLE_PREFIX, ROLES, SAMPLE_COL,
                                     TOTAL_COL, Project)
from hydrogel_diagrams.prepare import is_categorical, prepare, query_frame
from hydrogel_diagrams.spec import Axis, PlotSpec, Region

st.set_page_config(page_title="Hydrogel Diagram Maker", layout="wide")

KIND_LABELS = {"ternary": "Ternary diagram", "scatter3d": "3D scatter",
               "scatter2d": "2D scatter"}
NONE = "(none)"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MOCK_FILE = Path(__file__).parent / "examples" / "mock_hydrogel_data.xlsx"
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
    st.sidebar.caption("Plot water / filler / host / guest formulations")

    st.sidebar.subheader("Open your data")
    up = st.sidebar.file_uploader(
        "Drop an Excel (.xlsx) or CSV file here", type=["xlsx", "xls", "csv"],
        help="One row per sample, one column per ingredient (wt %). "
             "See 'Spreadsheets to fill in' below for the layout.")
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
                                   f"{len(proj.components)} ingredients"
                                   f"{where}. Check the roles on the "
                                   "Ingredients tab.")
            except Exception as exc:  # noqa: BLE001
                st.sidebar.error(f"Could not read file: {exc}")
            ss.loaded_file = (up.file_id, sheet)

    st.sidebar.caption("...or start from:")
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Example data", width="stretch",
                 help="30 made-up samples to play with"):
        ss.project = example_project()
        bump_editors()
        st.rerun()
    if c2.button("Empty project", width="stretch",
                 help="Start typing your own data. Comes with one water, "
                      "filler, host and guest to rename."):
        ss.project = blank_template()
        bump_editors()
        st.rerun()

    with st.sidebar.expander("Spreadsheets to fill in"):
        st.caption("Fill one in with Excel, then drop it in the box above.")
        st.download_button(
            "Blank template (.xlsx)", lambda: hio.save(blank_template()),
            file_name="hydrogel_template.xlsx", mime=XLSX, width="stretch")
        if MOCK_FILE.exists():
            st.download_button(
                "Practice workbook (.xlsx)", MOCK_FILE.read_bytes(),
                file_name=MOCK_FILE.name, mime=XLSX, width="stretch",
                help="Four made-up hydrogel systems, one per tab")

    st.sidebar.subheader("Save your work")
    # files are built when clicked; the callables can't read session_state
    # then, so bind what they need now
    proj, presets = project(), dict(ss.presets)
    st.sidebar.download_button(
        "Download project (.xlsx)",
        lambda: hio.save(proj, plots=presets),
        file_name="hydrogel_project.xlsx", mime=XLSX, type="primary",
        width="stretch")
    st.sidebar.caption("Keeps your ingredients, samples and saved plot "
                       "settings. Drop it in the box above next time to carry "
                       "on, or open it in Excel.")
    st.sidebar.download_button(
        "Samples only (.csv)",
        lambda: proj.samples.to_csv(index=False).encode(),
        file_name="hydrogel_samples.csv", mime="text/csv",
        width="stretch")


# ---------------------------------------------------------------------- #
# tab 1: components
# ---------------------------------------------------------------------- #
def components_tab():
    p = project()
    st.markdown(
        "**List every ingredient and say what it is.** The *role* tells the "
        "program how to group things: `water`, `filler` (clay, "
        "nanoparticles...), `host` (cyclodextrins, cucurbiturils...), "
        "`guest` (the guest polymer) or `other`.")
    st.caption(
        "To add one, click the empty row at the bottom of the table. To "
        "rename one, click its name; its data is kept. To remove one, tick "
        "the box at the left of its row and press Delete. Color is optional "
        "(e.g. #E69F00). **Press Apply when you're done.**")
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
        submitted = st.form_submit_button("Apply", type="primary")
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
        with st.expander("Turn a numeric column into an ingredient"):
            st.caption("Imported columns that weren't recognised as "
                       "ingredients are treated as measured properties.")
            col = st.selectbox("Column", unassigned)
            role = st.selectbox("Role", ROLES, index=1)
            if st.button("Make it an ingredient"):
                p.add_component(col, role)
                bump_editors()
                st.rerun()


# ---------------------------------------------------------------------- #
# tab 2: samples
# ---------------------------------------------------------------------- #
def samples_tab():
    p = project()
    st.markdown(
        "**One row per sample.** Ingredient columns are amounts in **wt %**; "
        "the columns after them are things you measured (stiffness, "
        "swelling, did it gel?...).")
    st.caption(
        "Click a cell to change it. Add a sample with the empty row at the "
        "bottom. To remove samples, tick the box at the left of the row and "
        "press Delete. You can also paste from Excel. **Press Save when "
        "you're done** - changes aren't kept until you do.")
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
        submitted = st.form_submit_button("Save", type="primary")
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

    st.subheader("Measured properties")
    st.caption("Add a column for anything you measured. 'yes/no' gives a "
               "tick box (e.g. gelled?).")
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
HL_OPS = {"is": "==", "is not": "!=", "greater than": ">",
          "at least": ">=", "less than": "<", "at most": "<="}
HL_MODES = ["Nothing", "Samples where...", "Type a condition"]
_HL_PATTERN = re.compile(r"^\s*(`[^`]+`|[A-Za-z_]\w*)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$")


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
    load_highlight_into_widgets(spec.highlight)
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


def load_highlight_into_widgets(expr: str):
    """Show a simple 'column op value' condition in the point-and-click
    builder; anything fancier goes in the free-text box."""
    ss = st.session_state
    ss.w_highlight = expr
    ss.w_hl_mode = HL_MODES[0] if not expr.strip() else HL_MODES[2]
    m = _HL_PATTERN.match(expr)
    if not m:
        return
    col, op, raw = m.groups()
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return
    ss.w_hl_mode = HL_MODES[1]
    ss.w_hl_col = col.strip("`")
    ss.w_hl_op = next(k for k, v in HL_OPS.items() if v == op)
    ss.w_hl_val = value


def highlight_expr(p: Project) -> str:
    """The highlight condition the widgets describe ('' for none)."""
    ss = st.session_state
    mode = ss.get("w_hl_mode", HL_MODES[0])
    if mode == HL_MODES[2]:
        return ss.get("w_highlight", "")
    if mode != HL_MODES[1] or "w_hl_col" not in ss:
        return ""
    col, value = ss.w_hl_col, ss.get("w_hl_val")
    if col not in query_frame(p).columns or value is None:
        return ""
    name = col if col.isidentifier() else f"`{col}`"
    if isinstance(value, (bool, np.bool_)):
        lit = "True" if value else "False"
    elif isinstance(value, str):
        lit = json.dumps(value)
    else:
        lit = repr(float(value))
    return f"{name} {HL_OPS.get(ss.get('w_hl_op'), '==')} {lit}"


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
            raise ValueError(f"region line needs 'name | points': {line!r}")
        color = parts[2] if len(parts) > 2 and parts[2] else "#7fb3d5"
        regions.append(Region.parse(parts[0], parts[1], color))
    pick = lambda v: "" if v == NONE else v  # noqa: E731
    return PlotSpec(kind=kind, axes=axes, size_by=pick(ss.w_size),
                    color_by=pick(ss.w_color), marker_by=pick(ss.w_marker),
                    highlight=highlight_expr(project()), dim_others=ss.w_dim,
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
        quick = quick_plots(p)
        if quick:
            st.markdown("**Start from a ready-made plot**")
            for name, spec in quick.items():
                if st.button(name, width="stretch", key=f"quick_{name}"):
                    load_spec_into_widgets(spec)
                    st.rerun()
            st.caption("Then change anything below.")
            st.divider()

        st.radio("Plot type", list(KIND_LABELS), key="w_kind",
                 format_func=KIND_LABELS.get, horizontal=True)
        kind = ss.w_kind
        n = 2 if kind == "scatter2d" else 3

        term_opts = opts["roles"] + opts["components"]
        if kind != "ternary":
            term_opts += opts["properties"] + [TOTAL_COL]
        names = (["Top corner", "Bottom-left corner", "Bottom-right corner"]
                 if kind == "ternary" else ["X axis", "Y axis", "Z axis"])
        st.markdown("**What goes on each axis**")
        st.caption("Pick one or more ingredients per axis. Several are added "
                   "together; *All fillers (sum)* adds up every filler.")
        for i in range(n):
            key = f"w_ax{i}"
            ss[key] = [t for t in ss.get(key, []) if t in term_opts]
            st.multiselect(names[i], term_opts, key=key,
                           format_func=pretty_term,
                           placeholder="Choose ingredients")
        if kind == "ternary":
            st.checkbox("Zoom in on my samples", key="w_zoom",
                        help="Shows only the part of the triangle where your "
                             "samples are. Turn this on when water is a "
                             "corner and everything sits near the top.")
            st.caption("The three corners always add up to 100 %. Leave "
                       "water out to compare just the solids.")

        st.markdown("**What the dots show**")
        enc_opts = ([NONE] + opts["properties"] + opts["derived"]
                    + opts["components"] + opts["roles"])
        shape_opts = [NONE] + opts["derived"][:-1] + opts["properties"]
        for key, choices in (("w_size", enc_opts), ("w_color", enc_opts),
                             ("w_marker", shape_opts)):
            if ss.get(key) not in choices:
                ss[key] = NONE
        st.selectbox("Dot size", enc_opts, key="w_size",
                     format_func=pretty_term,
                     help="Bigger dot = bigger number, e.g. stiffer gel.")
        st.selectbox("Dot color", enc_opts, key="w_color",
                     format_func=pretty_term,
                     help="Words and yes/no columns get one color per value; "
                          "numbers get a color scale.")
        st.selectbox("Dot shape", shape_opts, key="w_marker",
                     help="One shape per value, e.g. a different shape for "
                          "each host.")

        st.markdown("**Highlight samples**")
        st.radio("Highlight", HL_MODES, key="w_hl_mode", horizontal=True,
                 label_visibility="collapsed")
        if ss.w_hl_mode == HL_MODES[1]:
            highlight_builder(p)
        elif ss.w_hl_mode == HL_MODES[2]:
            st.text_input(
                "Condition", key="w_highlight",
                placeholder="gelled == True and all_host > 2",
                help="Uses column names; put names with spaces or symbols "
                     "in back-ticks: `G' (kPa)` > 10. Combine with and / "
                     "or. Extra columns: all_filler, all_host, all_guest "
                     "and 'filler type', 'host type', ...")
        if ss.w_hl_mode != HL_MODES[0]:
            st.checkbox("Grey out the other samples", key="w_dim")
            st.checkbox("Shade the area around them", key="w_hull",
                        disabled=kind == "scatter3d",
                        help="Not available for 3D plots")

        with st.expander("More options"):
            st.text_input("Title", key="w_title")
            st.caption("Axis names (leave blank for automatic)")
            for i in range(n):
                st.text_input(names[i], key=f"w_ax{i}_label",
                              placeholder="automatic")
            if ss.w_hull:
                st.text_input("Name of the shaded area", key="w_hull_label")
            st.text_area(
                "Draw your own shaded areas (one per line)", key="w_regions",
                height=80,
                placeholder="gel window | 20,30,50; 40,30,30; 30,10,60",
                help="name | corner points | color (optional). In a triangle "
                     "each point is top,left,right amounts; in 2D it is "
                     "x,y. Separate points with ';'.")
            if kind == "ternary" and not ss.w_zoom:
                st.caption("Manual zoom: lowest value shown on each axis (%)")
                mc = st.columns(3)
                for i in range(3):
                    mc[i].number_input(names[i].split()[0], 0.0, 99.0,
                                       step=5.0, key=f"w_tmin{i}")
            if kind != "ternary":
                st.checkbox("Show axes as fractions of their total",
                            key="w_norm")
            st.slider("Dot size range", 5, 900, key="w_size_range")
            st.selectbox("Color scale (for numbers)", COLORMAPS, key="w_cmap")
            st.checkbox("Write sample names next to dots", key="w_labels")
            st.checkbox("Grid lines", key="w_grid")

        with st.expander("Saved plot settings"):
            names_saved = list(ss.presets)
            choice = (st.selectbox("Saved settings", names_saved)
                      if names_saved else None)
            c1, c2 = st.columns(2)
            if choice and c1.button("Load"):
                load_spec_into_widgets(ss.presets[choice])
                st.rerun()
            if choice and c2.button("Delete"):
                del ss.presets[choice]
                st.rerun()
            new_name = st.text_input("Save the current plot settings as")
            if st.button("Save") and new_name:
                try:
                    ss.presets[new_name] = spec_from_widgets()
                    st.success("Saved. They're kept in the project file "
                               "when you download it.")
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))

    with right:
        try:
            spec = spec_from_widgets()
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return
        if any(not a.terms for a in spec.axes):
            st.info("Choose ingredients for every axis on the left, or click "
                    "one of the ready-made plots.")
            return
        try:
            prep = prepare(p, spec)
            fig = plotly_plots.plot(p, spec)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not draw the plot: {exc}")
            return
        view = st.radio(
            "View", ["Interactive", "As it will look in a paper"],
            horizontal=True, label_visibility="collapsed",
            help="Interactive: hover over dots to see the sample, drag to "
                 "rotate 3D plots.")
        if view == "Interactive":
            st.plotly_chart(fig, width="stretch")
        else:
            static = mpl_plots.plot(p, spec)
            st.pyplot(static, width="stretch")
            plt.close(static)

        st.markdown("**Download this plot**")
        cols = st.columns(4)
        for col, fmt, tip in zip(
                cols[:3], ("png", "svg", "pdf"),
                ("Picture for slides and documents",
                 "Editable vector picture (Illustrator, Inkscape)",
                 "Vector picture for papers")):
            # files are only rendered when the button is clicked
            col.download_button(
                fmt.upper(),
                lambda fmt=fmt: mpl_plots.to_bytes(mpl_plots.plot(p, spec),
                                                   fmt),
                file_name=f"hydrogel_{spec.kind}.{fmt}", help=tip,
                width="stretch")
        cols[3].download_button(
            "Interactive (HTML)", lambda: plotly_plots.to_html(fig),
            file_name=f"hydrogel_{spec.kind}.html", mime="text/html",
            help="Opens in any web browser; hover and rotate",
            width="stretch")
        if prep.dropped:
            st.caption("Not shown (no data for these axes): "
                       + ", ".join(prep.dropped))
        if prep.outside:
            st.caption("Outside the zoomed area: " + ", ".join(prep.outside))


def highlight_builder(p: Project):
    """Point-and-click 'column  is / greater than ...  value'."""
    ss = st.session_state
    qf = query_frame(p)
    cols = [c for c in qf.columns if c != SAMPLE_COL] + [SAMPLE_COL]
    if ss.get("w_hl_col") not in cols:
        ss.w_hl_col = next((c for c in cols if is_categorical(qf[c])), cols[0])
    c1, c2, c3 = st.columns([3, 2, 3])
    col = c1.selectbox("Column", cols, key="w_hl_col")
    series = qf[col]
    if is_categorical(series):
        ops = ["is", "is not"]
        values = list(dict.fromkeys(v for v in series.tolist()
                                    if not pd.isna(v)))
        if ss.get("w_hl_op") not in ops:
            ss.w_hl_op = ops[0]
        if ss.get("w_hl_val") not in values:
            ss.w_hl_val = values[0] if values else None
        c2.selectbox("is", ops, key="w_hl_op", label_visibility="hidden")
        c3.selectbox("Value", values, key="w_hl_val",
                     format_func=lambda v: ("yes" if v else "no")
                     if isinstance(v, (bool, np.bool_)) else str(v))
    else:
        ops = ["greater than", "at least", "less than", "at most", "is"]
        if ss.get("w_hl_op") not in ops:
            ss.w_hl_op = ops[0]
        if not isinstance(ss.get("w_hl_val"), (int, float)) \
                or isinstance(ss.get("w_hl_val"), bool):
            med = pd.to_numeric(series, errors="coerce").median()
            ss.w_hl_val = float(0 if pd.isna(med) else round(med, 2))
        c2.selectbox("is", ops, key="w_hl_op", label_visibility="hidden")
        c3.number_input("Value", key="w_hl_val")
    st.caption(f"Condition: `{highlight_expr(p) or '-'}`")


@st.cache_data(show_spinner=False)
def _data_tabs(data: bytes) -> list[str]:
    return hio.sheet_names(io.BytesIO(data))


def help_tab():
    st.markdown("""
### How to make a diagram

1. **Get your data in.** Drop an Excel file in the box on the left, or click
   *Empty project* and type it in. Don't have a spreadsheet yet? Open
   *Spreadsheets to fill in* on the left and download the blank template or
   the practice workbook.
2. **① Ingredients:** check each ingredient has the right role (water,
   filler, host, guest or other). To add a second guest polymer or another
   host, just add a row. Press **Apply**.
3. **② Samples:** one row per sample, amounts in wt %. Add columns for what
   you measured (stiffness, swelling, gelled yes/no...). Press **Save**.
4. **③ Make a plot:** click a ready-made plot, then change what you like.
   Download it as PNG / SVG / PDF, or as an interactive HTML page.
5. **Save your work** with *Download project (.xlsx)* on the left. Next time,
   drop that file in the box to carry on.

### Words used here
* **Role:** what an ingredient is: water, filler, host, guest or other.
* **All hosts (sum):** the total of every host in a sample, so two
  cyclodextrins count together.
* **Filler type / host type:** the name of the filler (or host) in each
  sample, e.g. for coloring dots by clay type.
* **Triangle (ternary) plot:** each corner is 100 % of one thing; the three
  always add up to 100 %. Leave water out to compare just the solids, or
  tick *Zoom in on my samples* if water is a corner.

### Spreadsheet layout
* A tab with a `sample` column, one column per ingredient (wt %), then your
  measured columns.
* Optional `components` tab listing `name` and `role` for each ingredient.
  Without one, roles are guessed from the names (laponite → filler, β-CD →
  host, PEG → guest); check them on the Ingredients tab.
* Several tabs (e.g. one per hydrogel system) are fine: pick one under
  **Which tab?**, or *all tabs combined* to compare them.
* Water can be an Excel formula such as `=100-SUM(C2:E2)`.

### Something looks wrong?
* **A dot is missing:** the caption under the plot lists samples that have
  nothing on the chosen axes, or that sit outside the zoomed area.
* **The samples don't add up to 100 %:** press *Fill water to 100 %* on the
  Samples tab.
* **An ingredient is listed as a measured column:** open *Turn a numeric
  column into an ingredient* on the Ingredients tab.
""")


def progress():
    """One line telling the user where they are and what to do next."""
    p = project()
    roles = {c.role for c in p.components}
    n = len(p.samples)
    step1 = f"{len(p.components)} ingredients" if p.components else "none yet"
    step2 = f"{n} samples" if n else "none yet"
    missing = [r for r in ("filler", "host", "guest") if r not in roles]
    if not p.components or missing:
        nxt = ("Next: add your ingredients on the **① Ingredients** tab"
               + (f" (no {', '.join(missing)} yet)" if p.components else ""))
    elif not n:
        nxt = "Next: type your samples on the **② Samples** tab"
    else:
        nxt = "Ready: go to **③ Make a plot**"
    st.info(f"**① Ingredients:** {step1}  ·  **② Samples:** {step2}  ·  "
            f"{nxt}", icon="👉")


def main():
    init_state()
    # Streamlit forgets the value of a widget that isn't drawn in a run
    # (e.g. the Z axis while in 2D mode); re-store them so nothing is lost.
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith("w_"):
            st.session_state[k] = st.session_state[k]
    sidebar()
    progress()
    t1, t2, t3, t4 = st.tabs(["① Ingredients", "② Samples", "③ Make a plot",
                              "❓ Help"])
    with t1:
        components_tab()
    with t2:
        samples_tab()
    with t3:
        plot_tab()
    with t4:
        help_tab()


main()
