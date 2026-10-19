from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _ok(at):
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def test_app_switches_plot_kinds_without_errors():
    at = AppTest.from_file(APP, default_timeout=60).run()
    _ok(at)
    for kind in ("scatter2d", "scatter3d", "ternary"):
        at.radio(key="w_kind").set_value(kind).run()
        _ok(at)
    # the Z axis survives a trip through 2D mode
    assert at.session_state["w_ax2"] == ["role:guest"]
    at.text_area(key="w_regions").set_value("w | 20,30,50; 40,30,30; 30,10,60")
    at.run()
    _ok(at)


def test_quick_plots_load():
    at = AppTest.from_file(APP, default_timeout=60).run()
    for label in [b.label for b in at.button if b.key and
                  b.key.startswith("quick_")]:
        _button(at, label).click().run()
        _ok(at)
    assert at.session_state["w_kind"] == "scatter2d"   # the last quick plot


def test_highlight_builder_and_free_text():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.radio(key="w_hl_mode").set_value("Samples where...").run()
    _ok(at)
    at.selectbox(key="w_hl_col").set_value("gelled").run()
    at.selectbox(key="w_hl_val").set_value(True).run()
    _ok(at)
    assert any("gelled == True" in c.value for c in at.caption)
    at.selectbox(key="w_hl_col").set_value("G' (kPa)").run()  # numeric column
    at.selectbox(key="w_hl_op").set_value("greater than").run()
    at.number_input(key="w_hl_val").set_value(10.0).run()
    _ok(at)
    assert any("`G' (kPa)` > 10.0" in c.value for c in at.caption)
    at.radio(key="w_hl_mode").set_value("Type a condition").run()
    at.text_input(key="w_highlight").set_value('`filler type` == "laponite"')
    at.run()
    _ok(at)


def test_empty_project_then_example_data():
    at = AppTest.from_file(APP, default_timeout=60).run()
    _button(at, "Empty project").click().run()
    _ok(at)
    assert len(at.session_state["project"].samples) == 1
    _button(at, "Example data").click().run()
    _ok(at)
