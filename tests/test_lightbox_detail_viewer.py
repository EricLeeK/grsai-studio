from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_lightbox_has_desktop_detail_viewer_controls():
    template = (ROOT / "app/templates/index.html").read_text()
    script = (ROOT / "app/static/js/app.js").read_text()
    styles = (ROOT / "app/static/css/style.css").read_text()

    assert 'id="lightboxViewport"' in template
    assert 'id="lightboxZoomIn"' in template
    assert 'id="lightboxZoomOut"' in template
    assert 'id="lightboxFit"' in template
    assert 'id="lightboxReset"' in template
    assert 'id="lightboxCompress"' in template
    assert "applyLightboxTransform" in script
    assert "lightboxViewport.addEventListener('wheel'" in script
    assert "lightboxViewport.addEventListener('pointerdown'" in script
    assert "compressCurrentLightboxImage" in script
    assert "/api/tasks/images/${img.id}/compress" in script
    assert "task-image-tag" in script
    assert "lightbox.classList.add('dragging')" in script
    assert "detail-viewer-active" in script
    assert "cursor: grab" in styles
    assert "cursor: grabbing" in styles
    assert ".lightbox-compress" in styles
    assert ".task-image-tag" in styles
    assert ".lightbox.open .lightbox-content" in styles
    assert ".lightbox.open.dragging" in styles
