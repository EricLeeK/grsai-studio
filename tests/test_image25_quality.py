import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _quality_values(template: str) -> set[str]:
    match = re.search(r'<select id="quality"[^>]*>(.*?)</select>', template, re.S)
    assert match
    return set(re.findall(r'<option value="([^"]+)"', match.group(1)))


def test_image25_quality_options_are_declared_in_both_generation_forms():
    for page in ("index.html", "comic.html"):
        values = _quality_values((ROOT / "app/templates" / page).read_text())
        assert {"low", "medium", "high", "xhigh", "max"} <= values


def test_quality_control_allows_only_supported_values_for_each_image25_model():
    app_js = (ROOT / "app/static/js/app.js").read_text()
    comic_js = (ROOT / "app/static/js/comic.js").read_text()
    for source in (app_js, comic_js):
        assert "gpt-image-2.5-sunburst" in source
        assert "gpt-image-2.5-flare" in source
        assert "xhigh" in source and "max" in source
        assert "updateQualityControl" in source
