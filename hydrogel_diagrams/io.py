"""Reading and writing projects as Excel workbooks or CSV files.

Workbook layout (what "Save project" writes, and the template):

* sheet ``samples``    - one row per sample: ``sample``, component wt %
                         columns, then any property columns
* sheet ``components`` - ``name``, ``role``, ``color``, ``notes``
* sheet ``plots``      - optional saved plot settings (``name``, ``json``)

A workbook may also hold several data tabs (e.g. one per hydrogel system,
each with different components). Pick one with ``sheet=...`` or combine them
all with ``sheet=ALL_SHEETS``; combined samples get a ``dataset`` column
naming the tab they came from. Tabs without numbers (instructions, notes)
are ignored.

A workbook (or CSV) without a components sheet also works: component roles
are guessed from the column names and can be fixed afterwards.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from .model import ROLES, SAMPLE_COL, Component, Project, guess_role
from .spec import PlotSpec

ALL_SHEETS = "(all tabs combined)"
DATASET_COL = "dataset"
# tabs that never hold samples (instructions, settings)
_SPECIAL_SHEETS = {"components", "plots", "how to use", "readme",
                   "instructions", "notes", "legend"}


def project_from_frames(samples: pd.DataFrame,
                        components: pd.DataFrame | None = None,
                        roles: dict[str, str] | None = None) -> Project:
    """Build a project from a samples table and (optionally) a components
    table. Only components that have a column in ``samples`` are kept;
    numeric columns not listed in ``components`` get a guessed role (or stay
    properties when nothing matches)."""
    samples = _clean(samples)
    listed: dict[str, Component] = {}
    if components is not None and not components.empty \
            and "name" in components.columns:
        for _, r in components.dropna(subset=["name"]).iterrows():
            name = str(r["name"]).strip()
            role = str(r.get("role", "other")).strip().lower()
            if name and name not in listed:
                listed[name] = Component(name, role if role in ROLES else "other",
                                         _str(r.get("color")),
                                         _str(r.get("notes")))
    roles = roles or {}
    proj = Project([], samples)
    blank_water = []
    for col in samples.columns:
        if col in (SAMPLE_COL, DATASET_COL):
            continue
        comp = listed.get(col)
        if comp is None:
            role = roles.get(col) or guess_role(col)
            numeric = pd.to_numeric(samples[col], errors="coerce").notna().any()
            # a water column may be all-blank (uncalculated formulas)
            if not role or not (numeric or role == "water"):
                continue
            comp = Component(col, role)
        values = pd.to_numeric(samples[col], errors="coerce")
        if comp.role == "water" and values.isna().all():
            blank_water.append(col)
        samples[col] = values.fillna(0.0)
        proj.components.append(comp)
    if len(blank_water) == 1 and len(samples):
        # e.g. "=100-SUM(...)" formulas saved without calculated values
        proj.fill_water_to_100()
    for col in samples.columns:  # blank text cells: "" rather than NaN
        if col in proj.component_names or col == SAMPLE_COL:
            continue
        vals = samples[col].dropna()
        if len(vals) and all(isinstance(v, str) for v in vals):
            samples[col] = samples[col].fillna("")
    # sample (and dataset) first, then components, then properties
    front = [c for c in (SAMPLE_COL, DATASET_COL) if c in samples.columns]
    proj.samples = samples[front + proj.component_names
                           + [c for c in samples.columns
                              if c not in front and c not in proj.component_names]]
    return proj


def _clean(samples: pd.DataFrame) -> pd.DataFrame:
    """Tidy a sheet as read by pandas: names, blank rows/columns, sample ids."""
    samples = samples.copy()
    samples.columns = [str(c).strip() for c in samples.columns]
    samples = samples.dropna(how="all")
    empty = [c for c in samples.columns
             if c.startswith("Unnamed:") and samples[c].isna().all()]
    samples = samples.drop(columns=empty).reset_index(drop=True)
    if SAMPLE_COL not in samples.columns:
        first = samples.columns[0] if len(samples.columns) else None
        if first is not None and \
                not pd.api.types.is_numeric_dtype(samples[first]):
            samples = samples.rename(columns={first: SAMPLE_COL})
        else:
            samples.insert(0, SAMPLE_COL, "")
    names = samples[SAMPLE_COL]
    missing = names.isna() | (names.astype(str).str.strip() == "")
    samples[SAMPLE_COL] = names.astype(str).str.strip()
    samples.loc[missing, SAMPLE_COL] = [f"S{i + 1}"
                                        for i in samples.index[missing]]
    return samples


def _str(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)


def data_sheets(sheets: dict[str, pd.DataFrame]) -> list[str]:
    """Names of the tabs that hold sample data (in workbook order)."""
    out = []
    for name, df in sheets.items():
        if name.strip().lower() in _SPECIAL_SHEETS or df.empty:
            continue
        if any(pd.api.types.is_numeric_dtype(df[c]) for c in df.columns):
            out.append(name)
    return out


def sheet_names(path_or_buffer) -> list[str]:
    """Data tabs of a workbook, for letting the user choose one."""
    return data_sheets(pd.read_excel(path_or_buffer, sheet_name=None))


def load(path_or_buffer, filename: str | None = None, sheet: str | None = None
         ) -> tuple[Project, dict[str, PlotSpec]]:
    """Load ``.xlsx`` / ``.xls`` / ``.csv``. Returns (project, saved plots).

    ``sheet`` picks a data tab; ``ALL_SHEETS`` stacks every data tab and adds
    a ``dataset`` column. By default the ``samples`` tab is used, or else the
    first data tab.
    """
    name = (filename or str(path_or_buffer)).lower()
    if name.endswith(".csv"):
        return project_from_frames(pd.read_csv(path_or_buffer)), {}
    sheets = pd.read_excel(path_or_buffer, sheet_name=None)
    lower = {k.strip().lower(): v for k, v in sheets.items()}
    data = data_sheets(sheets)
    if not data:
        raise ValueError("no tab with numbers found in this workbook")
    if sheet == ALL_SHEETS:
        frames = []
        for tab in data:
            df = _clean(sheets[tab])
            df.insert(1, DATASET_COL, tab)
            frames.append(df)
        samples = pd.concat(frames, ignore_index=True)
    else:
        if sheet is None:
            sheet = next((t for t in data if t.strip().lower() == "samples"),
                         data[0])
        if sheet not in sheets:
            raise KeyError(f"no tab named {sheet!r}")
        samples = sheets[sheet]
    # a component missing from a tab becomes 0 wt % there (see
    # project_from_frames), so combined tabs plot together cleanly
    proj = project_from_frames(samples, lower.get("components"))
    plots = {}
    if "plots" in lower:
        for _, r in lower["plots"].dropna().iterrows():
            try:
                plots[str(r["name"])] = PlotSpec.from_json(str(r["json"]))
            except Exception:  # noqa: BLE001 - skip unreadable presets
                pass
    return proj, plots


def save(project: Project, path_or_buffer=None,
         plots: dict[str, PlotSpec] | None = None) -> bytes | None:
    """Write the project workbook. With no path, returns the bytes."""
    target = path_or_buffer if path_or_buffer is not None else io.BytesIO()
    with pd.ExcelWriter(target, engine="openpyxl") as xw:
        project.samples.to_excel(xw, sheet_name="samples", index=False)
        project.components_frame().to_excel(xw, sheet_name="components",
                                            index=False)
        if plots:
            pd.DataFrame([{"name": k, "json": v.to_json()}
                          for k, v in plots.items()]
                         ).to_excel(xw, sheet_name="plots", index=False)
    if path_or_buffer is None:
        return target.getvalue()
    return None


def save_csv(project: Project, path: str | Path) -> None:
    project.samples.to_csv(path, index=False)
