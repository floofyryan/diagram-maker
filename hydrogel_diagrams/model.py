"""Data model: components (water, fillers, hosts, guests, ...) and samples.

A :class:`Project` holds

* a list of :class:`Component` objects, each with a *role*
  (``water``, ``filler``, ``host``, ``guest`` or ``other``), and
* a ``samples`` table (pandas DataFrame) with one row per formulation.
  Columns are ``sample`` (the name), one column per component (wt %), and
  any number of extra *property* columns (modulus, swelling, gelled?, ...).

Anything you want to plot is looked up through :meth:`Project.resolve`, which
understands component names, whole roles (``"role:filler"`` = sum of all
fillers), sums (``["PEG", "PAAm"]``), property columns and a few derived
columns such as ``"filler type"`` (the main filler in each sample).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

ROLES = ("water", "filler", "host", "guest", "other")
SAMPLE_COL = "sample"
ROLE_PREFIX = "role:"
TYPE_SUFFIX = " type"  # derived column: "filler type", "host type", ...
TOTAL_COL = "total wt%"

# Keywords used to guess a role when importing a spreadsheet without a
# components sheet. Matching is case-insensitive substring matching.
_ROLE_KEYWORDS = {
    "water": ("water", "h2o", "d2o"),
    "filler": ("clay", "laponite", "montmorillonite", "mmt", "bentonite",
               "silica", "sio2", "nanoparticle", "np", "cnc", "cellulose nano",
               "graphene", "go", "tio2", "fe3o4", "hydroxyapatite", "filler"),
    "host": ("cd", "cyclodextrin", "cucurbit", "cb[", "cb7", "cb8",
             "pillar", "calixarene", "crown", "host"),
    "guest": ("peg", "paam", "pnipam", "pva", "pdma", "pam", "adamant",
              "azobenzene", "ferrocene", "polymer", "guest"),
}


def guess_role(name: str) -> str | None:
    """Best-effort role guess from a column name (``None`` if no idea).

    When several keywords match, the one nearest the start of the name wins,
    so "PVA-Np" is a guest (PVA) rather than a filler (NP)."""
    low = name.lower()
    tokens = _tokenize(low)
    best = None  # (position, role)
    for role, words in _ROLE_KEYWORDS.items():
        for w in words:
            if len(w) <= 3 and "[" not in w:
                # short keywords must be a whole word to avoid false hits
                pos = tokens.index(w) if w in tokens else -1
                pos = low.find(tokens[pos]) if pos >= 0 else -1
            else:
                pos = low.find(w)
            if pos >= 0 and (best is None or pos < best[0]):
                best = (pos, role)
    return best[1] if best else None


def _tokenize(text: str) -> list[str]:
    out, cur = [], ""
    for ch in text:
        if ch.isalnum() or ch in "[]":
            cur += ch
        else:
            if cur:
                out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


@dataclass
class Component:
    name: str
    role: str = "other"
    color: str = ""          # optional hex colour used when plotting categories
    notes: str = ""

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}, got {self.role!r}")


@dataclass
class Project:
    components: list[Component] = field(default_factory=list)
    samples: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame({SAMPLE_COL: pd.Series(dtype=str)}))

    # ------------------------------------------------------------------ #
    # components
    # ------------------------------------------------------------------ #
    @property
    def component_names(self) -> list[str]:
        return [c.name for c in self.components]

    def get_component(self, name: str) -> Component:
        for c in self.components:
            if c.name == name:
                return c
        raise KeyError(name)

    def add_component(self, name: str, role: str = "other", color: str = "",
                      notes: str = "") -> Component:
        name = name.strip()
        if not name:
            raise ValueError("component name is empty")
        if name in self.component_names:
            raise ValueError(f"component {name!r} already exists")
        if name == SAMPLE_COL:
            raise ValueError(f"{SAMPLE_COL!r} is reserved")
        comp = Component(name, role, color, notes)
        self.components.append(comp)
        if name not in self.samples.columns:
            self.samples[name] = 0.0
        else:  # an existing property column becomes a component
            self.samples[name] = pd.to_numeric(self.samples[name],
                                               errors="coerce").fillna(0.0)
        return comp

    def remove_component(self, name: str, keep_column: bool = False) -> None:
        self.components = [c for c in self.components if c.name != name]
        if not keep_column and name in self.samples.columns:
            self.samples = self.samples.drop(columns=[name])

    def rename_component(self, old: str, new: str) -> None:
        new = new.strip()
        if new in self.samples.columns and new != old:
            raise ValueError(f"column {new!r} already exists")
        self.get_component(old).name = new
        self.samples = self.samples.rename(columns={old: new})

    def apply_component_table(self, original: pd.DataFrame,
                              edited: pd.DataFrame) -> None:
        """Apply an edited copy of :meth:`components_frame`.

        Rows are matched on the DataFrame index, so a changed name is a
        rename (data kept), a missing row is a removal and a new index is a
        new component.
        """
        edited = edited.copy()
        edited["name"] = edited["name"].fillna("").astype(str).str.strip()
        names = [n for n in edited["name"] if n]
        if len(names) != len(set(names)):
            raise ValueError("component names must be unique")
        for idx in original.index:
            if idx not in edited.index:
                self.remove_component(original.at[idx, "name"])
        for idx, row in edited.iterrows():
            if not row["name"]:
                continue
            role = row["role"] if row["role"] in ROLES else "other"
            color = "" if pd.isna(row["color"]) else str(row["color"]).strip()
            notes = "" if pd.isna(row["notes"]) else str(row["notes"])
            if idx in original.index:
                old = original.at[idx, "name"]
                if old != row["name"]:
                    self.rename_component(old, row["name"])
                comp = self.get_component(row["name"])
                comp.role, comp.color, comp.notes = role, color, notes
            else:
                self.add_component(row["name"], role, color, notes)

    def components_by_role(self, role: str) -> list[str]:
        return [c.name for c in self.components if c.role == role]

    # ------------------------------------------------------------------ #
    # samples & properties
    # ------------------------------------------------------------------ #
    @property
    def property_names(self) -> list[str]:
        comps = set(self.component_names)
        return [c for c in self.samples.columns
                if c != SAMPLE_COL and c not in comps]

    def add_property(self, name: str, kind: str = "number") -> None:
        """Add an empty property column. ``kind``: number, text or yes/no."""
        name = name.strip()
        if not name or name in self.samples.columns:
            raise ValueError(f"bad or duplicate column name {name!r}")
        if kind == "number":
            self.samples[name] = np.nan
        elif kind == "yes/no":
            self.samples[name] = False
        else:
            self.samples[name] = ""

    def remove_property(self, name: str) -> None:
        if name in self.property_names:
            self.samples = self.samples.drop(columns=[name])

    def add_sample(self, name: str | None = None,
                   properties: dict | None = None, **amounts: float) -> None:
        """Append a sample. ``amounts`` are wt % keyed by component name.

        Unknown keyword names raise; put measured values in ``properties``.
        """
        unknown = set(amounts) - set(self.component_names)
        if unknown:
            raise KeyError(f"unknown components {sorted(unknown)}; "
                           "add them with add_component() first")
        row = {SAMPLE_COL: name or f"S{len(self.samples) + 1}"}
        row.update({c: 0.0 for c in self.component_names})
        row.update(amounts)
        for k, v in (properties or {}).items():
            if k not in self.samples.columns:
                if isinstance(v, (bool, np.bool_)):
                    self.samples[k] = False
                elif isinstance(v, (int, float)):
                    self.samples[k] = np.nan
                else:
                    self.samples[k] = ""
            row[k] = v
        self.samples = pd.concat([self.samples, pd.DataFrame([row])],
                                 ignore_index=True)

    def fill_water_to_100(self) -> None:
        """Set the (single) water component so every sample sums to 100 wt %."""
        waters = self.components_by_role("water")
        if len(waters) != 1:
            raise ValueError("need exactly one water component")
        w = waters[0]
        others = [c for c in self.component_names if c != w]
        rest = self.samples[others].apply(pd.to_numeric, errors="coerce")
        self.samples[w] = (100 - rest.fillna(0).sum(axis=1)).clip(lower=0)

    def totals(self) -> pd.Series:
        """Sum of all component wt % per sample."""
        cols = self.component_names
        if not cols:
            return pd.Series(0.0, index=self.samples.index)
        return self.samples[cols].apply(pd.to_numeric,
                                        errors="coerce").fillna(0).sum(axis=1)

    # ------------------------------------------------------------------ #
    # resolving plot quantities
    # ------------------------------------------------------------------ #
    def plot_options(self) -> dict[str, list[str]]:
        """What can be put on an axis / used for size, colour, markers."""
        roles = [ROLE_PREFIX + r for r in ROLES if self.components_by_role(r)]
        types = [r + TYPE_SUFFIX for r in ROLES
                 if r != "water" and self.components_by_role(r)]
        return {
            "roles": roles,
            "components": self.component_names,
            "properties": self.property_names,
            "derived": types + [TOTAL_COL],
        }

    def resolve(self, spec: str | Iterable[str]) -> pd.Series:
        """Turn a spec into one value per sample.

        * ``"laponite"``             -> that component's wt %
        * ``"role:host"``            -> sum of all host components
        * ``["PEG", "role:filler"]`` -> sum of the listed terms
        * ``"PEG + PAAm"``           -> same as a list
        * ``"modulus_kPa"``          -> a property column, as-is
        * ``"filler type"``          -> name of the main filler in the sample
        * ``"total wt%"``            -> sum of all components
        """
        if not isinstance(spec, str):
            terms = list(spec)
            if len(terms) == 1:
                return self.resolve(terms[0])
            return sum((self._numeric(self.resolve(t)) for t in terms),
                       start=pd.Series(0.0, index=self.samples.index))
        spec = spec.strip()
        if spec in self.samples.columns:
            col = self.samples[spec]
            return self._numeric(col) if spec in self.component_names else col
        if "+" in spec:
            return self.resolve([s.strip() for s in spec.split("+")])
        if spec.startswith(ROLE_PREFIX):
            role = spec[len(ROLE_PREFIX):]
            names = self.components_by_role(role)
            if role not in ROLES:
                raise KeyError(f"unknown role {role!r}")
            if not names:
                return pd.Series(0.0, index=self.samples.index)
            return self.resolve(names)
        if spec.endswith(TYPE_SUFFIX):
            return self.dominant(spec[: -len(TYPE_SUFFIX)])
        if spec == TOTAL_COL:
            return self.totals()
        raise KeyError(f"don't know how to plot {spec!r}")

    def dominant(self, role: str) -> pd.Series:
        """Per sample, the name of the component of ``role`` with most wt %.

        Samples containing none of that role get ``"none"``; samples with
        two or more of that role present get e.g. ``"laponite + silica NP"``
        when they are mixed (each > 0)."""
        names = self.components_by_role(role)
        if not names:
            return pd.Series("none", index=self.samples.index)
        vals = self.samples[names].apply(pd.to_numeric, errors="coerce").fillna(0)

        def label(row):
            present = [n for n in names if row[n] > 0]
            if not present:
                return "none"
            present.sort(key=lambda n: -row[n])
            return " + ".join(present)

        return vals.apply(label, axis=1)

    @staticmethod
    def _numeric(s: pd.Series) -> pd.Series:
        return pd.to_numeric(s, errors="coerce").fillna(0.0)

    def label_for(self, spec: str | Iterable[str]) -> str:
        if isinstance(spec, str):
            terms = [spec]
        else:
            terms = list(spec)
        pretty = []
        for t in terms:
            if t.startswith(ROLE_PREFIX):
                role = t[len(ROLE_PREFIX):]
                pretty.append(role if role == "water" else role + "s")
            else:
                pretty.append(t)
        return " + ".join(pretty)

    def color_of(self, name: str) -> str:
        for c in self.components:
            if c.name == name and c.color:
                return c.color
        return ""

    # ------------------------------------------------------------------ #
    # tables for UI / IO
    # ------------------------------------------------------------------ #
    def components_frame(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(c) for c in self.components],
                            columns=["name", "role", "color", "notes"])

    def copy(self) -> "Project":
        return Project([Component(**asdict(c)) for c in self.components],
                       self.samples.copy())
