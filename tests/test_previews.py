import io

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest


@pytest.fixture
def preview_client(monkeypatch, tmp_path):
    from app.main import app
    from app.database import Base, get_db
    from app import config
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    def db_override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    try:
        yield TestClient(app), sessions, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.mark.parametrize('kind', ['generated', 'reference'])
def test_preview_is_small_cached_and_preserves_original(preview_client, tmp_path, kind, monkeypatch):
    from app.models import Task, GeneratedImage, ReferenceImage
    client, sessions, _ = preview_client
    source = tmp_path / 'original.png'
    Image.new('RGB', (3840, 2160), 'red').save(source)
    original = source.read_bytes()
    with sessions() as db:
        if kind == 'generated':
            task = Task(prompt='preview', model='gpt-image-2.5-flare')
            db.add(task); db.flush()
            row = GeneratedImage(task_id=task.id, image_path=str(source))
        else:
            row = ReferenceImage(original_filename='original.png', stored_filename='original.png', image_path=str(source), image_url='/reference-images/original.png')
        db.add(row); db.commit(); image_id = row.id
    url = f'/api/previews/{kind}/{image_id}'
    response = client.get(url)
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (320, 180)
    assert source.read_bytes() == original
    assert len(response.content) < len(original) / 5
    etag = response.headers['etag']
    assert client.get(url, headers={'If-None-Match': etag}).status_code == 304
    with monkeypatch.context() as patch:
        patch.setattr(Image, 'open', lambda *a, **kw: pytest.fail('cache hit must not decode original'))
        assert client.get(url).content == response.content
    Image.new('RGB', (2160, 3840), 'blue').save(source)
    updated = client.get(url, headers={'If-None-Match': etag})
    assert updated.status_code == 200
    assert updated.headers['etag'] != etag
    source.unlink()
    assert client.get(url).status_code == 404
    assert client.get(f'/api/previews/{kind}/999999').status_code == 404


def test_task_listing_has_bounded_query_count(preview_client):
    from app.models import Task, GeneratedImage
    client, sessions, engine = preview_client
    with sessions() as db:
        for i in range(20):
            task = Task(prompt=str(i), model='test', images=[GeneratedImage(image_path='/test.png')])
            db.add(task)
        db.commit()
    queries = []
    def count(*args): queries.append(args[2])
    event.listen(engine, 'before_cursor_execute', count)
    response = client.get('/api/tasks?limit=20')
    assert response.status_code == 200
    assert len(response.json()) == 20
    assert len(queries) <= 2
