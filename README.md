# Hydrogel Diagram Maker

Make triangle (ternary), 3D and 2D plots of hydrogel recipes made of
**water**, **fillers** (clay, nanoparticles...), **host molecules**
(cyclodextrins, cucurbiturils...) and **guest polymers**. You can type your
data in or use an Excel sheet, and you can add as many fillers, hosts or
polymers as you like.

## Start it (about 5 minutes the first time)

1. **Install Python** (one time only) from
   <https://www.python.org/downloads/>. On Windows, **tick "Add python.exe to
   PATH"** on the first screen of the installer.
2. **Download this program:** on the GitHub page, click the green **Code**
   button, then **Download ZIP**. Unzip it somewhere easy to find, such as
   your Desktop.
3. **Double-click the launcher** in the unzipped folder:
   * **Windows:** `start_app.bat`
   * **Mac:** `start_app.command`. If the Mac says it can't be opened,
     right-click it, choose **Open**, then click **Open** again.
4. A black window appears and sets things up. The first time this takes a
   few minutes. Then **the program opens in your web browser.**
   **Keep the black window open while you work**, and close it when you're
   done.

Next time, just double-click the launcher again; it starts in seconds.

## Make your first diagram

The program opens with example data, so you can try step 4 straight away.

1. **Bring in your data.** In the left panel, drop your Excel file into the
   box, or click **Empty project** to type it in.
   *No spreadsheet yet?* Open **Spreadsheets to fill in** on the left and
   download the **blank template** or the **practice workbook**.
2. **① Ingredients tab:** check that every ingredient has the right *role*:
   water, filler, host, guest or other. To add a second polymer or another
   host, click the empty row at the bottom. Press **Apply**.
3. **② Samples tab:** one row per sample, with amounts in **wt %**. Add
   columns for what you measured (stiffness, swelling, gelled yes/no...).
   Press **Save**. **Fill water to 100 %** does the water for you.
4. **③ Make a plot tab:** click one of the **ready-made plots**, then change
   anything you like:
   * **What goes on each axis:** single ingredients, or *All hosts (sum)*
     and so on.
   * **Dot size / color / shape:** for example size = stiffness,
     color = gelled, shape = host type.
   * **Highlight samples:** for example *gelled is yes* or *G' greater than
     10*. Optionally grey out the rest or shade the area around them.
   * **Zoom in on my samples:** use this when water is a corner and every
     point sits at the top.
5. **Download the plot:** PNG for slides, SVG or PDF for papers, or HTML for
   an interactive version that opens in any browser.
6. **Save your work:** click **Download project (.xlsx)** on the left.
   Next time, drop that file into the box to carry on where you left off.

The **❓ Help** tab inside the program has the same guide.

## Using your own Excel file

* Put **one row per sample** in a tab: a `sample` column, then one column
  per ingredient (amounts in wt %), then any measured columns.
* Optionally add a tab called `components` with `name` and `role` columns.
  Without it, roles are guessed from the names (Laponite → filler,
  β-CD → host, PEG → guest), and you can fix them on the Ingredients tab.
* **Several tabs are fine**, for example one per hydrogel system. After you
  drop the file in, choose a tab under **Which tab?**, or choose
  **(all tabs combined)** to compare them on one plot. A `dataset` column
  then tells you which tab each sample came from, so you can color by it.
* Water can be a formula such as `=100-SUM(C2:E2)`.

### The practice workbook

`examples/mock_hydrogel_data.xlsx` (also downloadable inside the program)
has made-up data. Each tab is a different system with its own ingredients:

| tab                   | filler(s)          | host(s)            | guest(s)         | other    |
|-----------------------|--------------------|--------------------|------------------|----------|
| `Laponite-bCD-PEG`    | Laponite XLG       | beta-CD            | PEG-Ad           |          |
| `Silica-aCD-PEG`      | silica NP          | alpha-CD           | PEG 20k          |          |
| `MMT-CB8-two guests`  | MMT                | CB[8]              | PVA-Np, PVA-MV   |          |
| `Mixed fillers-hosts` | Laponite XLG, CNC  | beta-CD, alpha-CD  | PAAm-Ad          | glycerol |

Blue cells are the ones you type in. Water updates itself.

## If something goes wrong

* **"Python was not found":** install Python (step 1 above) and remember the
  *Add python.exe to PATH* box. Then double-click the launcher again.
* **The browser didn't open:** go to <http://localhost:8501> yourself while
  the black window is open.
* **A sample is missing from the plot:** the note under the plot says which
  samples were left out and why.
* Anything else: copy the text from the black window and send it to whoever
  set this up for you.

---

# For programmers

Start without the launchers:

```bash
pip install -r requirements.txt
streamlit run app.py
```

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
python examples/make_figures.py examples/mock_hydrogel_data.xlsx
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
examples/                       practice workbook (+ the script that builds
                                it), demo project, batch-figure script
tests/                          pytest suite
```

To add a new plot type, add its name to `PLOT_KINDS` in `spec.py` and add a
branch in `mpl_plots._draw` and `plotly_plots.plot`. `prepare()` already
provides the coordinates, sizes, colors and highlight flags.

## Tests

```bash
pip install pytest
pytest
```
