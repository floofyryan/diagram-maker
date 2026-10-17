"""Build examples/mock_hydrogel_data.xlsx - a practice workbook.

Each data tab is a different hydrogel system with its own components:

* Laponite-bCD-PEG      - clay filler, beta-cyclodextrin host, PEG guest
* Silica-aCD-PEG        - silica nanoparticles, alpha-CD host, PEG guest
* MMT-CB8-two guests    - montmorillonite, CB[8] host, two guest polymers
* Mixed fillers-hosts   - two fillers, two hosts, one guest + glycerol

All numbers are invented. Water is an Excel formula (100 - everything else)
so it updates when you change the other amounts. openpyxl can't calculate
formulas, so the Diagram Maker computes water itself when a water column has
no stored values; opening and saving the file in Excel stores them.

    python examples/make_mock_workbook.py
"""

from pathlib import Path

import numpy as np
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

OUT = Path(__file__).with_name("mock_hydrogel_data.xlsx")

FONT = "Arial"
INPUT = Font(name=FONT, color="0000FF")          # blue = type here
FORMULA = Font(name=FONT, color="000000")        # black = calculated
HEADER = Font(name=FONT, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", start_color="305496")
WATER_FILL = PatternFill("solid", start_color="DDEBF7")
TITLE = Font(name=FONT, bold=True, size=14)
BOLD = Font(name=FONT, bold=True)
PLAIN = Font(name=FONT)

COMPONENTS = [  # name, role, color, notes
    ("water", "water", "#56B4E9", "Always the solvent; one water column per tab"),
    ("Laponite XLG", "filler", "#E69F00", "Synthetic hectorite clay"),
    ("silica NP", "filler", "#D55E00", "~20 nm silica nanoparticles"),
    ("MMT", "filler", "#8C564B", "Montmorillonite clay"),
    ("CNC", "filler", "#BCBD22", "Cellulose nanocrystals"),
    ("beta-CD", "host", "#009E73", "beta-cyclodextrin"),
    ("alpha-CD", "host", "#CC79A7", "alpha-cyclodextrin"),
    ("CB[8]", "host", "#17BECF", "Cucurbit[8]uril"),
    ("PEG-Ad", "guest", "#0072B2", "Adamantane-end-capped PEG"),
    ("PEG 20k", "guest", "#4C72B0", "Linear PEG, 20 kg/mol"),
    ("PVA-Np", "guest", "#9467BD", "PVA with naphthyl side groups"),
    ("PVA-MV", "guest", "#E377C2", "PVA with methyl viologen side groups"),
    ("PAAm-Ad", "guest", "#1F77B4", "Polyacrylamide with adamantane groups"),
    ("glycerol", "other", "#7F7F7F", "Co-solvent / plasticiser"),
]

# tab name -> (filler/host/guest/other components with wt % ranges,
#              properties, rule deciding "gelled")
SYSTEMS = {
    "Laponite-bCD-PEG": {
        "prefix": "LAP",
        "amounts": {"Laponite XLG": (0.5, 4.0), "beta-CD": (0.5, 6.0),
                    "PEG-Ad": (1.0, 8.0)},
        "props": ["G' (kPa)", "swelling ratio", "gelled", "notes"],
    },
    "Silica-aCD-PEG": {
        "prefix": "SIL",
        "amounts": {"silica NP": (0.5, 5.0), "alpha-CD": (0.5, 6.0),
                    "PEG 20k": (0.5, 5.0)},
        "props": ["G' (kPa)", "gel time (min)", "gelled", "notes"],
    },
    "MMT-CB8-two guests": {
        "prefix": "MMT",
        "amounts": {"MMT": (0.5, 3.0), "CB[8]": (0.2, 2.0),
                    "PVA-Np": (1.0, 5.0), "PVA-MV": (1.0, 5.0)},
        "props": ["G' (kPa)", "self-healing (%)", "gelled", "notes"],
    },
    "Mixed fillers-hosts": {
        "prefix": "MIX",
        "amounts": {"Laponite XLG": (0.0, 1.5), "CNC": (0.0, 1.0),
                    "beta-CD": (0.0, 2.5), "alpha-CD": (0.0, 2.5),
                    "PAAm-Ad": (1.0, 5.0), "glycerol": (0.0, 5.0)},
        "props": ["G' (kPa)", "swelling ratio", "self-healing (%)", "gelled",
                  "notes"],
    },
}
N_SAMPLES = 12


def mock_rows(system, rng):
    roles = {c[0]: c[1] for c in COMPONENTS}
    rows = []
    prefix = system["prefix"]
    for i in range(N_SAMPLES):
        amt = {c: round(float(rng.uniform(*r)), 2)
               for c, r in system["amounts"].items()}
        filler = sum(v for c, v in amt.items() if roles[c] == "filler")
        host = sum(v for c, v in amt.items() if roles[c] == "host")
        guest = sum(v for c, v in amt.items() if roles[c] == "guest")
        gelled = bool(host * guest > 6 and filler > 0.6)
        modulus = 0.5 * filler * (host + guest) + rng.normal(0, 0.6)
        modulus = round(max(modulus * (2.5 if gelled else 0.2), 0.05), 2)
        props = {
            "G' (kPa)": modulus,
            "swelling ratio": round(float(rng.uniform(5, 40) / (1 + filler)), 1),
            "gel time (min)": round(float(rng.uniform(2, 60)), 0) if gelled else None,
            "self-healing (%)": round(float(min(99, rng.uniform(40, 95)
                                                + 2 * host)), 0),
            "gelled": gelled,
            "notes": "" if gelled else "flowed when inverted",
        }
        rows.append((f"{prefix}-{i + 1:02d}", amt,
                     {p: props[p] for p in system["props"]}))
    return rows


def style_header(ws, ncols):
    for col in range(1, ncols + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = HEADER
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "B2"


def add_data_tab(wb, name, system, rng):
    ws = wb.create_sheet(name)
    comps = list(system["amounts"])
    headers = ["sample", "water"] + comps + system["props"]
    ws.append(headers)
    style_header(ws, len(headers))
    ws.cell(row=1, column=2).comment = Comment(
        "Formula: 100 - all other components. Type a number over it if "
        "you prefer to enter water yourself.", "template")
    first = get_column_letter(3)
    last = get_column_letter(2 + len(comps))
    for r, (sample, amt, props) in enumerate(mock_rows(system, rng),
                                             start=2):
        ws.cell(row=r, column=1, value=sample).font = INPUT
        water = ws.cell(row=r, column=2,
                        value=f"=100-SUM({first}{r}:{last}{r})")
        water.font = FORMULA
        water.fill = WATER_FILL
        water.number_format = "0.00"
        for j, c in enumerate(comps, start=3):
            cell = ws.cell(row=r, column=j, value=amt[c])
            cell.font = INPUT
            cell.number_format = "0.00"
        for j, p in enumerate(system["props"], start=3 + len(comps)):
            cell = ws.cell(row=r, column=j, value=props[p])
            cell.font = INPUT
    ws.column_dimensions["A"].width = 12
    for j in range(2, len(headers) + 1):
        ws.column_dimensions[get_column_letter(j)].width = 15
    ws.column_dimensions[get_column_letter(len(headers))].width = 22


def add_instructions(wb):
    ws = wb.active
    ws.title = "How to use"
    lines = [
        ("Mock hydrogel data (practice workbook)", TITLE),
        ("All numbers here are made up - replace them with your own.", PLAIN),
        ("", PLAIN),
        ("Tabs", BOLD),
        ("components - every ingredient used in any tab and its role "
         "(water, filler, host, guest, other).", PLAIN),
        ("Each other tab is one hydrogel system with its own components. "
         "Rows are samples, amounts are wt %.", PLAIN),
        ("", PLAIN),
        ("Colors", BOLD),
        ("Blue text = values you type or change.", INPUT),
        ("Black text on light blue = water, calculated as 100 - everything "
         "else.", FORMULA),
        ("", PLAIN),
        ("Adding things", BOLD),
        ("New sample: copy a row, change the name and amounts (water updates "
         "itself).", PLAIN),
        ("New component: add a column to the tab, then add a row with its "
         "name and role on the components tab. Widen the water formula's "
         "SUM range to include the new column.", PLAIN),
        ("New system: copy a tab, rename it, and change the column headers.",
         PLAIN),
        ("New measured property: add a column after the components "
         "(numbers, TRUE/FALSE or text).", PLAIN),
        ("", PLAIN),
        ("Using it in the Diagram Maker", BOLD),
        ("Upload this file in the sidebar, then choose a tab under 'Which "
         "tab?' - or 'All tabs combined' to compare systems (a 'dataset' "
         "column says which tab each sample came from).", PLAIN),
    ]
    for i, (text, font) in enumerate(lines, start=1):
        cell = ws.cell(row=i, column=1, value=text)
        cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 110


def add_components(wb):
    ws = wb.create_sheet("components")
    ws.append(["name", "role", "color", "notes"])
    style_header(ws, 4)
    for row in COMPONENTS:
        ws.append(list(row))
    for r in ws.iter_rows(min_row=2):
        for cell in r:
            cell.font = INPUT
    for col, width in zip("ABCD", (16, 10, 11, 45)):
        ws.column_dimensions[col].width = width


def main():
    rng = np.random.default_rng(2024)
    wb = Workbook()
    add_instructions(wb)
    add_components(wb)
    for name, system in SYSTEMS.items():
        add_data_tab(wb, name, system, rng)
    wb.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
