"""Image 2.5 model availability and pixel-size routing."""
import json
import re
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
MODELS = ('gpt-image-2.5-flare', 'gpt-image-2.5-sunburst')


@pytest.mark.parametrize('page', ['/', '/comic'])
def test_only_4k_image25_models_are_available(page):
    from app.main import app
    html = TestClient(app).get(page).text
    assert set(re.findall(r'<option value="(gpt-image-2\.5[^"]*)"', html)) == set(MODELS)


@pytest.mark.parametrize('model', MODELS)
def test_size_control_routes_image25_to_pixel_sizes(model):
    source = (ROOT / 'app/static/js/app.js').read_text()
    helpers = '\n'.join(re.findall(r'  function (?:isGpt4kModel|getActiveSizeSelect|updateSizeControl)\([^)]*\) \{.*?\n  \}', source, re.S))
    script = '''const modelSelect = {value: MODEL};
const sizeSelect = {style:{}}, sizeGpt = {style:{}}, sizeGptVip = {style:{}, value:'3840x2160'}, ratioGroup = {style:{}};
HELPERS
updateSizeControl();
console.log(JSON.stringify([getActiveSizeSelect().value, sizeGptVip.style.display, ratioGroup.style.display]));'''.replace('MODEL', json.dumps(model)).replace('HELPERS', helpers)
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == ['3840x2160', 'block', 'none']


@pytest.mark.parametrize('model', MODELS)
def test_direct_request_preserves_4k_pixels(model, monkeypatch, tmp_path):
    from app.services import grsai
    monkeypatch.setattr(grsai.config, 'GRSAI_API_KEY', 'test-key')
    requests = []
    def request(url, payload):
        requests.append(payload)
        return {'status': 'succeeded', 'results': [{'url': 'https://example.test/image.png'}]}
    monkeypatch.setattr(grsai, '_request_json', request)
    monkeypatch.setattr(grsai.urllib.request, 'urlretrieve', lambda url, path: path.write_bytes(b'image'))
    result = grsai.generate_image_direct('test', model, str(tmp_path), size='3840x2160')
    assert result.success
    assert requests[0]['model'] == model
    assert requests[0]['aspectRatio'] == '3840x2160'
    assert 'imageSize' not in requests[0]
