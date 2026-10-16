"""Hydrogel composition diagrams: ternary, 3D and 2D scatter plots."""

from .model import ROLES, Component, Project
from .spec import PLOT_KINDS, Axis, PlotSpec, Region

__all__ = ["ROLES", "PLOT_KINDS", "Component", "Project", "Axis", "PlotSpec",
           "Region"]
