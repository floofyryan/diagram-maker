"""Plot settings, kept separate from the data so they can be saved/reused."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

PLOT_KINDS = ("ternary", "scatter3d", "scatter2d")


@dataclass
class Axis:
    """One axis: a list of terms that are summed (see Project.resolve)."""
    terms: list[str]
    label: str = ""        # empty -> generated from the terms

    def __post_init__(self):
        if isinstance(self.terms, str):
            self.terms = [t.strip() for t in self.terms.split("+") if t.strip()]


@dataclass
class Region:
    """A shaded polygon.

    For ternary plots vertices are (a, b, c) in the same units as the axes
    (they are normalised, so percent or fractions both work). For 2D/3D
    scatter plots vertices are (x, y) and only drawn on 2D plots.
    """
    name: str
    vertices: list[tuple[float, ...]]
    color: str = "#7fb3d5"
    alpha: float = 0.25

    def __post_init__(self):
        self.vertices = [tuple(float(x) for x in v) for v in self.vertices]

    @classmethod
    def parse(cls, name: str, text: str, color: str = "#7fb3d5",
              alpha: float = 0.25) -> "Region":
        """Parse ``"80,10,10; 60,30,10; 60,10,30"`` into a Region."""
        verts = []
        for chunk in text.replace("\n", ";").split(";"):
            chunk = chunk.strip()
            if chunk:
                verts.append(tuple(float(v) for v in chunk.split(",")))
        if len(verts) < 3:
            raise ValueError("a region needs at least 3 vertices")
        return cls(name, verts, color, alpha)

    def vertices_text(self) -> str:
        return "; ".join(",".join(f"{v:g}" for v in p) for p in self.vertices)


@dataclass
class PlotSpec:
    kind: str = "ternary"
    axes: list[Axis] = field(default_factory=list)
    size_by: str = ""            # column/spec mapped to dot size
    color_by: str = ""           # column/spec mapped to colour
    marker_by: str = ""          # categorical column mapped to marker shape
    highlight: str = ""          # pandas query, e.g. "gelled == True"
    dim_others: bool = True      # grey out samples not matching highlight
    hull_of_highlight: bool = False  # shade convex hull of highlighted points
    hull_label: str = "highlighted region"
    regions: list[Region] = field(default_factory=list)
    title: str = ""
    label_points: bool = False
    size_range: tuple[float, float] = (40.0, 400.0)  # matplotlib points^2
    base_size: float = 80.0      # used when size_by is empty
    colormap: str = "viridis"
    normalize_3d: bool = False   # 3D/2D: plot fractions of the 3 axes' sum
    zoom: bool = False           # ternary: zoom to a sub-triangle around data
    ternary_min: tuple[float, float, float] = (0.0, 0.0, 0.0)  # manual zoom, %
    show_grid: bool = True

    def __post_init__(self):
        if self.kind not in PLOT_KINDS:
            raise ValueError(f"kind must be one of {PLOT_KINDS}")
        self.axes = [a if isinstance(a, Axis) else Axis(**a) if isinstance(a, dict)
                     else Axis(a) for a in self.axes]
        self.regions = [r if isinstance(r, Region) else Region(**r)
                        for r in self.regions]
        self.size_range = tuple(self.size_range)
        self.ternary_min = tuple(float(v) for v in self.ternary_min)

    @property
    def n_axes(self) -> int:
        return 2 if self.kind == "scatter2d" else 3

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "PlotSpec":
        return cls(**json.loads(text))
