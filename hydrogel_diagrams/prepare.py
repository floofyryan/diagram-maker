"""Backend-independent preparation of plot data.

Both the matplotlib and plotly renderers call :func:`prepare` so the two
outputs always show the same thing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .model import ROLES, SAMPLE_COL, TYPE_SUFFIX, Project
from .spec import PlotSpec

# Okabe-Ito colour-blind-safe palette, then a few extras.
CATEGORY_PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9",
                    "#D55E00", "#F0E442", "#000000", "#8C564B", "#7F7F7F",
                    "#17BECF", "#BCBD22"]
NONE_COLOR = "#B0B0B0"
DIM_COLOR = "#D9D9D9"
MPL_MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*", "h", "<", ">"]
PLOTLY_MARKERS = ["circle", "square", "triangle-up", "diamond",
                  "triangle-down", "cross", "x", "star", "hexagon",
                  "triangle-left", "triangle-right"]
PLOTLY_MARKERS_3D = ["circle", "square", "diamond", "cross", "x",
                     "circle-open", "square-open", "diamond-open"]


@dataclass
class Prepared:
    kind: str
    data: pd.DataFrame            # sample, c0..c2, size01, color, marker, hl
    axis_labels: list[str]
    title: str
    color_mode: str = "none"      # none | category | continuous
    color_label: str = ""
    categories: list = field(default_factory=list)
    category_colors: dict = field(default_factory=dict)
    size_label: str = ""
    size_minmax: tuple[float, float] | None = None
    marker_label: str = ""
    marker_categories: list = field(default_factory=list)
    hull: list[tuple[float, ...]] | None = None
    has_highlight: bool = False
    tern_min: tuple[float, float, float] = (0.0, 0.0, 0.0)  # fractions
    dropped: list[str] = field(default_factory=list)   # no data on the axes
    outside: list[str] = field(default_factory=list)   # outside ternary zoom

    def marker_index(self, value) -> int:
        if not self.marker_categories:
            return 0
        return self.marker_categories.index(value) % len(MPL_MARKERS)


def as_float(s: pd.Series) -> pd.Series:
    """Numbers as floats; yes/no values become 1/0; anything else NaN."""
    s = s.map(lambda v: float(v) if isinstance(v, (bool, np.bool_)) else v)
    return pd.to_numeric(s, errors="coerce").astype(float)


def is_categorical(s: pd.Series) -> bool:
    if pd.api.types.is_bool_dtype(s) or not pd.api.types.is_numeric_dtype(s):
        return True
    vals = pd.to_numeric(s, errors="coerce").dropna().unique()
    return len(vals) <= 2


def query_frame(project: Project) -> pd.DataFrame:
    """Samples plus derived columns, for use in highlight queries."""
    df = project.samples.copy()
    for role in ROLES:
        if role != "water" and project.components_by_role(role):
            df[role + TYPE_SUFFIX] = project.dominant(role)
        if project.components_by_role(role):
            df["all_" + role] = project.resolve("role:" + role)
    return df


def apply_highlight(project: Project, expr: str) -> pd.Series:
    """Boolean mask of samples matching a pandas query expression.

    Column names with spaces need back-ticks: ```filler type` == "laponite"``.
    """
    df = query_frame(project)
    if not expr.strip():
        return pd.Series(True, index=df.index)
    # Older pandas can't parse some back-ticked names (e.g. "G' (kPa)"), so
    # give such columns plain stand-in names for the query.
    renames = {c: f"_col{i}" for i, c in enumerate(df.columns)
               if not str(c).isidentifier()}
    for col, safe in renames.items():
        expr = expr.replace(f"`{col}`", safe)
    try:
        idx = df.rename(columns=renames).query(expr, engine="python").index
    except Exception as exc:  # noqa: BLE001 - surface any query error
        raise ValueError(f"could not apply highlight {expr!r}: {exc}") from exc
    return pd.Series(df.index.isin(idx), index=df.index)


def convex_hull(points: np.ndarray) -> np.ndarray:
    """Monotone-chain convex hull of 2-D points (returns hull vertices)."""
    pts = np.unique(points, axis=0)
    if len(pts) < 3:
        return pts
    pts = pts[np.lexsort((pts[:, 1], pts[:, 0]))]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in pts[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.array(lower[:-1] + upper[:-1])


def prepare(project: Project, spec: PlotSpec) -> Prepared:
    if len(spec.axes) != spec.n_axes:
        raise ValueError(f"{spec.kind} needs {spec.n_axes} axes, "
                         f"got {len(spec.axes)}")
    samples = project.samples
    df = pd.DataFrame({"sample": samples[SAMPLE_COL].astype(str)},
                      index=samples.index)
    labels = []
    for i, ax in enumerate(spec.axes):
        if not ax.terms:
            raise ValueError(f"axis {i + 1} has nothing selected")
        df[f"c{i}"] = as_float(project.resolve(ax.terms))
        labels.append(ax.label or project.label_for(ax.terms))

    coords = [f"c{i}" for i in range(spec.n_axes)]
    raw = df[coords].copy()
    for c in coords:
        df[f"raw{c[1]}"] = raw[c]
    if spec.kind == "ternary" or spec.normalize_3d:
        total = raw.sum(axis=1)
        keep = total > 0
        df.loc[keep, coords] = raw.loc[keep].div(total[keep], axis=0)
    else:
        keep = raw.notna().all(axis=1)
    dropped = df.loc[~keep, "sample"].tolist()

    prep = Prepared(spec.kind, df, labels, spec.title, dropped=dropped)

    # -- size --------------------------------------------------------------
    if spec.size_by:
        v = as_float(project.resolve(spec.size_by))
        lo, hi = v.min(), v.max()
        if pd.isna(lo):
            df["size01"] = 0.0
        elif hi == lo:
            df["size01"] = 0.5
        else:
            df["size01"] = ((v - lo) / (hi - lo)).fillna(0.0)
        df["size_raw"] = v
        prep.size_label = project.label_for(spec.size_by)
        prep.size_minmax = (lo, hi) if not pd.isna(lo) else None
    else:
        df["size01"] = np.nan

    # -- colour --------------------------------------------------------------
    if spec.color_by:
        v = project.resolve(spec.color_by)
        prep.color_label = project.label_for(spec.color_by)
        if is_categorical(v):
            v = v.map(_category_text)
            prep.color_mode = "category"
            cats = _ordered_categories(v)
            prep.categories = cats
            prep.category_colors = _category_colors(project, cats)
            df["color"] = v
        else:
            prep.color_mode = "continuous"
            df["color"] = as_float(v)
    else:
        df["color"] = None

    # -- marker ------------------------------------------------------------
    if spec.marker_by:
        v = project.resolve(spec.marker_by).map(_category_text)
        prep.marker_label = project.label_for(spec.marker_by)
        prep.marker_categories = _ordered_categories(v)
        df["marker"] = v
    else:
        df["marker"] = ""

    # -- highlight -----------------------------------------------------------
    if spec.highlight.strip():
        df["hl"] = apply_highlight(project, spec.highlight)
        prep.has_highlight = True
    else:
        df["hl"] = True

    prep.data = df.loc[keep].copy()
    if spec.kind == "ternary":
        prep.tern_min = ternary_window(prep.data, spec)
        inside = np.ones(len(prep.data), dtype=bool)
        for c, m in zip(coords, prep.tern_min):
            inside &= (prep.data[c] >= m - 1e-9).to_numpy()
        prep.outside = prep.data.loc[~inside, "sample"].tolist()
        prep.data = prep.data.loc[inside]

    # -- hull of highlighted points -------------------------------------------
    if spec.hull_of_highlight and prep.has_highlight and spec.kind != "scatter3d":
        sel = prep.data.loc[prep.data["hl"], coords].to_numpy(dtype=float)
        if len(sel) >= 3:
            h = convex_hull(sel[:, :2])
            if spec.kind == "ternary":
                prep.hull = [(a, b, 1 - a - b) for a, b in h]
            else:
                prep.hull = [tuple(p) for p in h]
    return prep


def ternary_window(data: pd.DataFrame, spec: PlotSpec
                   ) -> tuple[float, float, float]:
    """Minimum of each ternary axis (fractions) for a zoomed sub-triangle.

    With ``spec.zoom`` the window hugs the data (rounded to 5 % steps);
    otherwise ``spec.ternary_min`` (percent) is used, (0, 0, 0) = full plot.
    """
    if spec.zoom and not data.empty:
        mins = []
        for c in ("c0", "c1", "c2"):
            lo = float(data[c].min()) - 0.02
            mins.append(max(0.0, np.floor(lo / 0.05) * 0.05))
    else:
        mins = [v / 100 for v in spec.ternary_min]
    if sum(mins) >= 0.99 or min(mins) < 0:
        raise ValueError("ternary axis minimums must be >= 0 and add up to "
                         "less than 100 %")
    return tuple(round(m, 6) for m in mins)


def _category_text(v) -> str:
    if isinstance(v, (bool, np.bool_)):
        return "yes" if v else "no"
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _ordered_categories(v: pd.Series) -> list[str]:
    cats = list(dict.fromkeys(v.tolist()))
    # put "none"/"n/a" last so the real categories get the first colours
    return [c for c in cats if c not in ("none", "n/a")] + \
           [c for c in cats if c in ("none", "n/a")]


def _category_colors(project: Project, cats: list[str]) -> dict[str, str]:
    out, i = {}, 0
    for c in cats:
        if c in ("none", "n/a"):
            out[c] = NONE_COLOR
        elif project.color_of(c):
            out[c] = project.color_of(c)
        else:
            out[c] = CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)]
            i += 1
    return out


def nice_size_ticks(lo: float, hi: float, n: int = 3) -> list[float]:
    """A few representative values for a size legend (min, middle, max)."""
    if hi == lo:
        return [lo]
    return [float(f"{v:.3g}") for v in np.linspace(lo, hi, n)]
