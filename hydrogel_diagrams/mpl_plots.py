"""Static figures (PNG / SVG / PDF) with matplotlib."""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Polygon  # noqa: E402

from .model import Project  # noqa: E402
from .prepare import (DIM_COLOR, MPL_MARKERS, Prepared, nice_size_ticks,  # noqa: E402
                      prepare)
from .spec import PlotSpec  # noqa: E402

H = np.sqrt(3) / 2


def tern_xy(a, b, c, mins=(0.0, 0.0, 0.0)):
    """Barycentric (a top, b bottom-left, c bottom-right) -> cartesian.

    ``mins`` are the axis minimums of a zoomed sub-triangle (fractions);
    the sub-triangle is stretched to fill the unit triangle.
    """
    a, b, c = (np.asarray(v, dtype=float) for v in (a, b, c))
    s = a + b + c
    span = 1 - sum(mins)
    a = (a / s - mins[0]) / span
    c = (c / s - mins[2]) / span
    return 0.5 * a + c, H * a


def plot(project: Project, spec: PlotSpec, figsize=(8, 6.5)) -> plt.Figure:
    prep = prepare(project, spec)
    fig = plt.figure(figsize=figsize)
    if spec.kind == "ternary":
        ax = fig.add_subplot(111)
        mins = prep.tern_min
        _ternary_frame(ax, prep.axis_labels, spec.show_grid, mins)
        to_xy = lambda d: tern_xy(d["c0"], d["c1"], d["c2"], mins)  # noqa: E731
        _draw_regions_2d(ax, spec, prep, ternary=True)
    elif spec.kind == "scatter3d":
        ax = fig.add_subplot(111, projection="3d")
        ax.set_xlabel(prep.axis_labels[0])
        ax.set_ylabel(prep.axis_labels[1])
        ax.set_zlabel(prep.axis_labels[2])
        to_xy = lambda d: (d["c0"], d["c1"], d["c2"])  # noqa: E731
    else:
        ax = fig.add_subplot(111)
        ax.set_xlabel(prep.axis_labels[0])
        ax.set_ylabel(prep.axis_labels[1])
        if spec.show_grid:
            ax.grid(alpha=0.3)
        to_xy = lambda d: (d["c0"], d["c1"])  # noqa: E731
        _draw_regions_2d(ax, spec, prep, ternary=False)

    mappable = _draw_points(ax, prep, spec, to_xy)
    if spec.label_points:
        for _, row in prep.data.iterrows():
            pos = to_xy(row)
            ax.text(*[float(p) for p in pos], " " + row["sample"], fontsize=7,
                    va="center")

    handles = _legend_handles(prep, spec)
    if mappable is not None:
        cb = fig.colorbar(mappable, ax=ax, shrink=0.7, pad=0.12
                          if spec.kind == "scatter3d" else 0.04)
        cb.set_label(prep.color_label)
    if handles:
        leg = ax.legend([h for h, _ in handles], [lbl for _, lbl in handles],
                        loc="upper left", bbox_to_anchor=(1.02 if mappable is None
                                                          else 1.25, 1.0),
                        frameon=False, fontsize=8, borderaxespad=0)
        for text, (h, _) in zip(leg.get_texts(), handles):
            if getattr(h, "_is_header", False):
                text.set_fontweight("bold")
    if spec.title:
        ax.set_title(spec.title)
    fig.tight_layout()
    return fig


def to_bytes(fig: plt.Figure, fmt: str = "png", dpi: int = 300) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def save(project: Project, spec: PlotSpec, path: str, dpi: int = 300) -> None:
    fig = plot(project, spec)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------- #
def _tick_step(span: float) -> float:
    for step in (0.01, 0.02, 0.025, 0.05, 0.1, 0.2):
        if span / step <= 10.5:
            return step
    return 0.25


def _ternary_frame(ax, labels, grid=True, mins=(0.0, 0.0, 0.0)):
    ax.set_aspect("equal")
    ax.axis("off")
    tri = np.array([[0, 0], [1, 0], [0.5, H], [0, 0]])
    ax.plot(tri[:, 0], tri[:, 1], color="black", lw=1.2, zorder=1)
    span = 1 - sum(mins)
    step = _tick_step(span)
    pct = lambda v: f"{v * 100:.4g}"  # noqa: E731
    # local coordinate f in (0, 1) of the drawn triangle <-> actual value
    for axis in range(3):
        m = mins[axis]
        first = np.ceil((m + 1e-9) / step) * step
        for v in np.arange(first, m + span - 1e-9, step):
            f = (v - m) / span
            if axis == 0:
                p, q = (f, 1 - f, 0), (f, 0, 1 - f)
                tick, off, ha, va = (f, 1 - f, 0), (-0.02, 0), "right", "center"
            elif axis == 1:
                p, q = (1 - f, f, 0), (0, f, 1 - f)
                tick, off, ha, va = (0, f, 1 - f), (0, -0.03), "center", "top"
            else:
                p, q = (1 - f, 0, f), (0, 1 - f, f)
                tick, off, ha, va = (1 - f, 0, f), (0.02, 0), "left", "center"
            if grid:
                x, y = tern_xy(*zip(p, q))
                ax.plot(x, y, color="#CCCCCC", lw=0.6, zorder=0)
            x, y = tern_xy(*tick)
            ax.text(x + off[0], y + off[1], pct(v), ha=ha, va=va, fontsize=7)
    zoomed = any(m > 0 for m in mins)

    def corner(i):
        if not zoomed:
            return labels[i]
        return f"{labels[i]}\n({pct(mins[i] + span)} %)"

    ax.text(0.5, H + 0.04, corner(0), ha="center", va="bottom", fontsize=10,
            fontweight="bold")
    ax.text(-0.04, -0.06, corner(1), ha="right", va="top", fontsize=10,
            fontweight="bold")
    ax.text(1.04, -0.06, corner(2), ha="left", va="top", fontsize=10,
            fontweight="bold")
    ax.set_xlim(-0.15, 1.15)
    ax.set_ylim(-0.15, H + 0.15)


def _draw_regions_2d(ax, spec, prep, ternary):
    polys = [(r.name, r.vertices, r.color, r.alpha) for r in spec.regions]
    if prep.hull:
        polys.append((spec.hull_label, prep.hull, "#F4A582", 0.3))
    for _, verts, color, alpha in polys:
        v = np.array(verts, dtype=float)
        if ternary:
            if v.shape[1] != 3:
                raise ValueError("ternary regions need (a, b, c) vertices")
            x, y = tern_xy(v[:, 0], v[:, 1], v[:, 2], prep.tern_min)
            xy = np.column_stack([x, y])
        else:
            xy = v[:, :2]
        patch = ax.add_patch(Polygon(xy, closed=True, facecolor=color,
                                     alpha=alpha, edgecolor=color, lw=1.0,
                                     zorder=0.5))
        if ternary:  # keep regions inside a (possibly zoomed) triangle
            clip = Polygon([[0, 0], [1, 0], [0.5, H]], closed=True,
                           transform=ax.transData)
            patch.set_clip_path(clip)


def _sizes(prep: Prepared, spec: PlotSpec, d):
    lo, hi = spec.size_range
    s = d["size01"]
    return np.where(s.isna(), spec.base_size, lo + s.fillna(0) * (hi - lo))


def _draw_points(ax, prep: Prepared, spec: PlotSpec, to_xy):
    d = prep.data
    if d.empty:
        return None
    norm = None
    cmap = plt.get_cmap(spec.colormap)
    if prep.color_mode == "continuous":
        vals = d["color"].astype(float)
        norm = Normalize(vals.min(), vals.max() if vals.max() > vals.min()
                         else vals.min() + 1)

    def colors_for(sub):
        if prep.color_mode == "category":
            return [prep.category_colors[c] for c in sub["color"]]
        if prep.color_mode == "continuous":
            return [cmap(norm(v)) if not np.isnan(v) else DIM_COLOR
                    for v in sub["color"].astype(float)]
        return ["#0072B2"] * len(sub)

    groups = prep.marker_categories or [""]
    mappable = None
    for mcat in groups:
        sub = d[d["marker"] == mcat] if prep.marker_categories else d
        marker = MPL_MARKERS[prep.marker_index(mcat)]
        if prep.has_highlight and spec.dim_others:
            off = sub[~sub["hl"]]
            if not off.empty:
                ax.scatter(*to_xy(off), s=_sizes(prep, spec, off), c=DIM_COLOR,
                           marker=marker, edgecolors="#999999", linewidths=0.5,
                           alpha=0.6, zorder=2)
            sub = sub[sub["hl"]]
        if sub.empty:
            continue
        edge = ["black" if (prep.has_highlight and h and not spec.dim_others)
                else "white" for h in sub["hl"]]
        lw = [1.6 if e == "black" else 0.6 for e in edge]
        ax.scatter(*to_xy(sub), s=_sizes(prep, spec, sub), c=colors_for(sub),
                   marker=marker, edgecolors=edge, linewidths=lw, alpha=0.9,
                   zorder=3)
    if prep.color_mode == "continuous":
        mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    return mappable


def _header(text):
    h = Line2D([], [], linestyle="none")
    h._is_header = True
    return h, text


def _legend_handles(prep: Prepared, spec: PlotSpec):
    out = []
    if prep.color_mode == "category":
        out.append(_header(prep.color_label))
        for c in prep.categories:
            out.append((Line2D([], [], marker="o", linestyle="none",
                               markerfacecolor=prep.category_colors[c],
                               markeredgecolor="white", markersize=8), c))
    if prep.marker_categories:
        out.append(_header(prep.marker_label))
        for c in prep.marker_categories:
            out.append((Line2D([], [], marker=MPL_MARKERS[prep.marker_index(c)],
                               linestyle="none", color="#555555",
                               markersize=7), c))
    if prep.size_minmax:
        out.append(_header(prep.size_label))
        lo, hi = prep.size_minmax
        lo_s, hi_s = spec.size_range
        for v in nice_size_ticks(lo, hi):
            frac = 0.5 if hi == lo else (v - lo) / (hi - lo)
            area = lo_s + frac * (hi_s - lo_s)
            out.append((Line2D([], [], marker="o", linestyle="none",
                               color="#888888", markersize=np.sqrt(area)),
                        f"{v:g}"))
    if prep.has_highlight:
        out.append(_header("highlight"))
        out.append((Line2D([], [], marker="o", linestyle="none",
                           color="#555555", markeredgecolor="black"),
                    spec.highlight))
        if spec.dim_others:
            out.append((Line2D([], [], marker="o", linestyle="none",
                               color=DIM_COLOR), "other samples"))
    if spec.regions or prep.hull:
        out.append(_header("regions"))
        for r in spec.regions:
            out.append((Patch(facecolor=r.color, alpha=r.alpha), r.name))
        if prep.hull:
            out.append((Patch(facecolor="#F4A582", alpha=0.3), spec.hull_label))
    return out
