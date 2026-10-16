"""Reading and writing projects as Excel workbooks or CSV files.

Workbook layout (what "Save project" writes, and the template):

* sheet ``samples``    - one row per sample: ``sample``, component wt %
                         columns, then any property columns
* sheet ``components`` - ``name``, ``role``, ``color``, ``notes``
* sheet ``plots``      - optional saved plot settings (``name``, ``json``)

A workbook (or CSV) with only a samples table also works: component roles
are guessed from the column names and can be fixed afterwards.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from .model import ROLES, SAMPLE_COL, Component, Project, guess_role
from .spec import PlotSpec


def project_from_frames(samples: pd.DataFrame,
                        components: pd.DataFrame | None = None,
                        roles: dict[str, str] | None = None) -> Project:
    samples = samples.copy()
    samples.columns = [str(c).strip() for c in samples.columns]
    samples = samples.dropna(how="all")
    if SAMPLE_COL not in samples.columns:
        first = samples.columns[0]
        if not pd.api.types.is_numeric_dtype(samples[first]):
            samples = samples.rename(columns={first: SAMPLE_COL})
        else:
            samples.insert(0, SAMPLE_COL,
                           [f"S{i + 1}" for i in range(len(samples))])
    samples[SAMPLE_COL] = samples[SAMPLE_COL].astype(str)
    samples = samples.reset_index(drop=True)

    comps: list[Component] = []
    if components is not None and not components.empty:
        for _, r in components.dropna(subset=["name"]).iterrows():
            role = str(r.get("role", "other")).strip().lower()
            comps.append(Component(str(r["name"]).strip(),
                                   role if role in ROLES else "other",
                                   _str(r.get("color")), _str(r.get("notes"))))
    else:
        roles = roles or {}
        for col in samples.columns:
            if col == SAMPLE_COL:
                continue
            role = roles.get(col) or guess_role(col)
            numeric = pd.to_numeric(samples[col], errors="coerce").notna().any()
            if role and numeric:
                comps.append(Component(col, role))

    proj = Project([], samples)
    for c in comps:
        if c.name in samples.columns:
            samples[c.name] = pd.to_numeric(samples[c.name],
                                            errors="coerce").fillna(0.0)
            proj.components.append(c)
        else:
            proj.add_component(c.name, c.role, c.color, c.notes)
    return proj


def _str(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)


def load(path_or_buffer, filename: str | None = None
         ) -> tuple[Project, dict[str, PlotSpec]]:
    """Load ``.xlsx`` / ``.xls`` / ``.csv``. Returns (project, saved plots)."""
    name = (filename or str(path_or_buffer)).lower()
    if name.endswith(".csv"):
        return project_from_frames(pd.read_csv(path_or_buffer)), {}
    sheets = pd.read_excel(path_or_buffer, sheet_name=None)
    lower = {k.lower(): v for k, v in sheets.items()}
    samples = lower.get("samples", next(iter(sheets.values())))
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
