# Hydrogel Diagram Maker

A small Python program for plotting hydrogel formulations made of **water**,
**fillers** (clay, nanoparticles, ...), **host molecules** (cyclodextrins,
cucurbiturils, ...) and **guest polymers**, plus anything else you add.

* Type data straight into tables, or open an Excel / CSV sheet.
* Add or remove components at any time: a second guest polymer, a third host
  or a new filler is just another row.
* Plot **ternary diagrams**, **3D scatter** or **2D scatter**. Choose what
  goes on each axis, either single components or the sum of a whole role
  (e.g. *all hosts*).
* Map **dot size**, **color** and **marker shape** to measured properties
  (modulus, swelling, ...) or to categories (filler type, host type, gelled
  yes/no).
* **Highlight** samples that match a condition (`gelled == True`), shade the
  region around them, or draw your own shaded regions.
* **Zoom** ternary plots to the data. Water-rich gels all sit near one
  corner otherwise.
* Export **PNG / SVG / PDF** (matplotlib, for papers) and **interactive
  HTML** (plotly, hover and rotate).

## Install & run

You need Python 3.10 or newer.

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens in your browser. On Windows you can also double-click
`start_app.bat`; on macOS/Linux run `./start_app.sh`.

## Using the app

1. **Components tab**: one row per ingredient with its role (`water`,
   `filler`, `host`, `guest`, `other`) and an optional color. Press
   *Apply component changes*. Renaming keeps the data, and deleting a row
   removes that column.
2. **Samples tab**: one row per formulation, with component amounts in
   **wt %**. Add property columns (number, yes/no or text) for what you
   measured. *Fill water to 100 %* sets water to whatever is left. Press
   *Save table* after editing.
3. **Plot tab**: choose the plot type, the axes and the encodings. The
   settings can be saved as presets, and presets are stored in the project
   file.
4. **Save**: *Download project (.xlsx)* in the sidebar. Upload it later to
   carry on.

## Practice workbook

`examples/mock_hydrogel_data.xlsx` is a practice file with made-up data.
Each tab is a different hydrogel system with its own components:

| tab                   | filler(s)          | host(s)            | guest(s)         | other    |
|-----------------------|--------------------|--------------------|------------------|----------|
| `Laponite-bCD-PEG`    | Laponite XLG       | beta-CD            | PEG-Ad           |          |
| `Silica-aCD-PEG`      | silica NP          | alpha-CD           | PEG 20k          |          |
| `MMT-CB8-two guests`  | MMT                | CB[8]              | PVA-Np, PVA-MV   |          |
| `Mixed fillers-hosts` | Laponite XLG, CNC  | beta-CD, alpha-CD  | PAAm-Ad          | glycerol |

It also has a `How to use` tab and a `components` tab that lists every
ingredient's role. Blue cells are the ones you type in. Water is a formula
(100 − everything else), so it updates when you change the other amounts.

Upload it in the sidebar, then pick a tab under **Which tab?**. Choose
**(all tabs combined)** to compare systems: the samples are stacked, a
`dataset` column records which tab each one came from, and you can color,
mark or highlight by it (`dataset == "Silica-aCD-PEG"`). Rebuild the file
with `python examples/make_mock_workbook.py`.

## Excel format

| sheet        | columns                                                           |
|--------------|-------------------------------------------------------------------|
| `samples`    | `sample`, one column per component (wt %), then property columns  |
| `components` | `name`, `role`, `color`, `notes`                                  |
| `plots`      | saved plot settings (written by the app, optional)                |

A workbook can have several data tabs, for example one per system. The app
asks which one to load, or combines them all. Tabs named `How to use`,
`README`, `notes` and so on are skipped. A workbook with only a samples
sheet works too. Roles are then guessed from
the column names (*laponite* → filler, *β-CD* → host, *PEG* → guest, ...)
and you can fix them on the Components tab. `examples/demo_project.xlsx` is
a ready-made template. Its data are made up.

## Using it from Python

```python
from hydrogel_diagrams import Project, PlotSpec, Axis, Region
from hydrogel_diagrams import io, mpl_plots, plotly_plots

project, saved = io.load("my_project.xlsx")      # sheet="Silica-aCD-PEG" or
                                                 # sheet=io.ALL_SHEETS; or in code:
# project = Project()
# project.add_component("water", "water")
# project.add_component("laponite", "filler")
# project.add_component("beta-CD", "host")
# project.add_component("PEG", "guest")
# project.add_sample("S1", water=90, laponite=2, **{"beta-CD": 3}, PEG=5,
#                    properties={"G' (kPa)": 12.0, "gelled": True})

spec = PlotSpec(
    kind="ternary",                               # "ternary", "scatter3d", "scatter2d"
    axes=[Axis(["role:filler"]), Axis(["role:host"]), Axis(["role:guest"])],
    size_by="G' (kPa)",
    color_by="filler type",                       # derived: main filler per sample
    marker_by="host type",
    highlight="gelled == True",
    hull_of_highlight=True,
    regions=[Region("target", [(10, 40, 50), (30, 30, 40), (20, 20, 60)])],
)
mpl_plots.save(project, spec, "ternary.png")      # static figure
plotly_plots.save_html(project, spec, "ternary.html")  # interactive figure
```

What can go on an axis or be used for size, color or markers:

| write                         | means                                            |
|-------------------------------|--------------------------------------------------|
| `"laponite"`                  | that component's wt %                            |
| `"role:host"`                 | sum of all host components                       |
| `["PEG", "PAAm"]` / `"PEG + PAAm"` | sum of several items                        |
| `"G' (kPa)"`                  | a property column                                |
| `"filler type"`, `"host type"`, `"guest type"` | name of the main component of that role |
| `"total wt%"`                 | sum of all components                            |

Highlight conditions are [pandas queries](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.query.html).
They can use any column plus `all_filler`, `all_host`, `all_guest`, ...
and the `... type` columns. Put names that contain spaces in back-ticks:
`` `G' (kPa)` > 10 and `filler type` == "laponite" ``.

`examples/make_figures.py` renders a set of figures from a workbook in one
go:

```bash
python examples/make_figures.py examples/demo_project.xlsx
```

## Code layout

```
app.py                          the Streamlit program
hydrogel_diagrams/model.py      components, samples, roles, resolving axes
hydrogel_diagrams/spec.py       plot settings (PlotSpec, Axis, Region)
hydrogel_diagrams/prepare.py    shared data prep for both renderers
hydrogel_diagrams/mpl_plots.py  static figures (matplotlib)
hydrogel_diagrams/plotly_plots.py interactive figures (plotly)
hydrogel_diagrams/io.py         Excel / CSV import and export
examples/                       practice workbook, demo project, scripts
tests/                          pytest suite
```

To add a new plot type, add its name to `PLOT_KINDS` in `spec.py` and add a
branch in `mpl_plots.plot` and `plotly_plots.plot`. `prepare()` already
provides the coordinates, sizes, colors and highlight flags.

## Tests

```bash
pip install pytest
pytest
```
