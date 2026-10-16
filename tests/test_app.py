from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_app_switches_plot_kinds_without_errors():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception and not at.error
    for kind in ("scatter2d", "scatter3d", "ternary"):
        at.radio(key="w_kind").set_value(kind).run()
        assert not at.exception and not at.error, kind
    # the Z axis survives a trip through 2D mode
    assert at.session_state["w_ax2"] == ["role:guest"]
    at.text_input(key="w_highlight").set_value('`filler type` == "laponite"')
    at.text_area(key="w_regions").set_value("w | 20,30,50; 40,30,30; 30,10,60")
    at.run()
    assert not at.exception and not at.error
