"""Interactive figures (HTML) with plotly: hover, zoom, rotate in 3D."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from .model import Project
from .prepare import (DIM_COLOR, PLOTLY_MARKERS, PLOTLY_MARKERS_3D, Prepared,
                      nice_size_ticks, prepare)
from .spec import PlotSpec


def _px(area):
    """matplotlib marker area (pt^2) -> plotly diameter (px)."""
    return np.sqrt(np.asarray(area, dtype=float))


def plot(project: Project, spec: PlotSpec) -> go.Figure:
    prep = prepare(project, spec)
    fig = go.Figure()
    kind = spec.kind
    symbols = PLOTLY_MARKERS_3D if kind == "scatter3d" else PLOTLY_MARKERS

    if kind != "scatter3d":
        _add_regions(fig, prep, spec)

    d = prep.data
    lo_s, hi_s = spec.size_range
    d = d.assign(px=_px(np.where(d["size01"].isna(), spec.base_size,
                                 lo_s + d["size01"].fillna(0) * (hi_s - lo_s))))
    d = d.assign(hover=[_hover(prep, row) for _, row in d.iterrows()])

    cmin = cmax = None
    if prep.color_mode == "continuous":
        cmin, cmax = d["color"].min(), d["color"].max()
    first_scale = [True]

    def add(sub, name, color, symbol, legend=True, group=None, dim=False,
            ring=False):
        if sub.empty:
            return
        marker = dict(size=sub["px"], symbol=symbol, opacity=0.6 if dim else 0.9,
                      line=dict(width=2 if ring else 0.5,
                                color="black" if ring else "white"))
        if color == "continuous" and not dim:
            marker.update(color=sub["color"], colorscale=spec.colormap,
                          cmin=cmin, cmax=cmax,
                          showscale=first_scale[0],
                          colorbar=dict(title=prep.color_label, x=1.0))
            first_scale[0] = False
        else:
            marker["color"] = color
        common = dict(mode="markers+text" if spec.label_points else "markers",
                      text=sub["sample"] if spec.label_points else None,
                      textposition="top center", name=name, marker=marker,
                      hovertext=sub["hover"], hoverinfo="text",
                      showlegend=legend, legendgroup=group)
        fig.add_trace(_trace(kind, sub, common))

    mgroups = prep.marker_categories or [""]
    for mcat in mgroups:
        sub = d[d["marker"] == mcat] if prep.marker_categories else d
        symbol = symbols[prep.marker_index(mcat) % len(symbols)]
        mname = f" / {mcat}" if prep.marker_categories else ""
        if prep.has_highlight and spec.dim_others:
            add(sub[~sub["hl"]], "other samples" + mname, DIM_COLOR, symbol,
                group="dim", dim=True)
            sub = sub[sub["hl"]]
        ring_mask = sub["hl"] if (prep.has_highlight and not spec.dim_others) \
            else None
        parts = [(sub[ring_mask], True), (sub[~ring_mask], False)] \
            if ring_mask is not None else [(sub, False)]
        for part, ring in parts:
            suffix = " (highlighted)" if ring else ""
            if prep.color_mode == "category":
                for cat in prep.categories:
                    add(part[part["color"] == cat], f"{cat}{mname}{suffix}",
                        prep.category_colors[cat], symbol, group=cat, ring=ring)
            elif prep.color_mode == "continuous":
                add(part, (mcat or "samples") + suffix, "continuous", symbol,
                    legend=bool(prep.marker_categories) or ring, ring=ring)
            else:
                add(part, (mcat or "samples") + suffix, "#0072B2", symbol,
                    legend=bool(prep.marker_categories) or ring, ring=ring)

    _add_size_legend(fig, prep, spec, kind)
    _layout(fig, prep, spec)
    return fig


def to_html(fig: go.Figure) -> str:
    return fig.to_html(include_plotlyjs="cdn", full_html=True)


def save_html(project: Project, spec: PlotSpec, path: str) -> None:
    plot(project, spec).write_html(path, include_plotlyjs="cdn")


# ---------------------------------------------------------------------- #
def _trace(kind, sub, common, coords=None):
    c = coords if coords is not None else [sub["c0"], sub["c1"],
                                            sub.get("c2")]
    if kind == "ternary":
        a, b, cc = (np.asarray(v, dtype=float) * 100 for v in c)
        return go.Scatterternary(a=a, b=b, c=cc, **common)
    if kind == "scatter3d":
        return go.Scatter3d(x=c[0], y=c[1], z=c[2], **common)
    return go.Scatter(x=c[0], y=c[1], **common)


def _hover(prep: Prepared, row) -> str:
    lines = [f"<b>{row['sample']}</b>"]
    for i, lbl in enumerate(prep.axis_labels):
        lines.append(f"{lbl}: {row[f'raw{i}']:.3g}")
    if prep.size_label and "size_raw" in row:
        lines.append(f"{prep.size_label}: {row['size_raw']}")
    if prep.color_label:
        lines.append(f"{prep.color_label}: {row['color']}")
    if prep.marker_label:
        lines.append(f"{prep.marker_label}: {row['marker']}")
    return "<br>".join(lines)


def _add_regions(fig, prep, spec):
    polys = [(r.name, r.vertices, r.color, r.alpha) for r in spec.regions]
    if prep.hull:
        polys.append((spec.hull_label, prep.hull, "#F4A582", 0.3))
    for name, verts, color, alpha in polys:
        v = np.array(list(verts) + [verts[0]], dtype=float)
        if spec.kind == "ternary":
            v = v / v.sum(axis=1, keepdims=True)
            coords = [v[:, 0], v[:, 1], v[:, 2]]
        else:
            coords = [v[:, 0], v[:, 1], None]
        common = dict(mode="lines", fill="toself", name=name, opacity=alpha,
                      line=dict(color=color, width=1), fillcolor=color,
                      hoverinfo="name")
        fig.add_trace(_trace(spec.kind, None, common, coords))


def _add_size_legend(fig, prep, spec, kind):
    if not prep.size_minmax:
        return
    lo, hi = prep.size_minmax
    lo_s, hi_s = spec.size_range
    for v in nice_size_ticks(lo, hi):
        frac = 0.5 if hi == lo else (v - lo) / (hi - lo)
        size = float(_px(lo_s + frac * (hi_s - lo_s)))
        common = dict(mode="markers", name=f"{prep.size_label} = {v:g}",
                      marker=dict(size=size, color="#999999"),
                      legendgroup="size", hoverinfo="skip")
        fig.add_trace(_trace(kind, None, common, [[None], [None], [None]]))


def _layout(fig, prep, spec):
    labels = prep.axis_labels
    fig.update_layout(title=spec.title or None, template="plotly_white",
                      legend=dict(itemsizing="trace", x=1.12 if
                                  prep.color_mode == "continuous" else 1.02),
                      margin=dict(l=60, r=60, t=60 if spec.title else 30, b=40),
                      height=650)
    if spec.kind == "ternary":
        axis = dict(ticksuffix="%", showgrid=spec.show_grid, linewidth=1.5)
        mins = [m * 100 for m in prep.tern_min]
        fig.update_layout(ternary=dict(
            sum=100,
            aaxis=dict(title=labels[0], min=mins[0], **axis),
            baxis=dict(title=labels[1], min=mins[1], **axis),
            caxis=dict(title=labels[2], min=mins[2], **axis)))
    elif spec.kind == "scatter3d":
        fig.update_layout(scene=dict(xaxis_title=labels[0],
                                     yaxis_title=labels[1],
                                     zaxis_title=labels[2]))
    else:
        fig.update_layout(xaxis_title=labels[0], yaxis_title=labels[1])
