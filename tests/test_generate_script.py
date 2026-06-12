import os
import subprocess
import urllib.error
from pathlib import Path


def test_generate_script_reports_curl_request_failure(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        "  *' --http1.1 '*) ;;\n"
        "  *) echo 'missing --http1.1' >&2; exit 2 ;;\n"
        "esac\n"
        "echo 'curl: (7) Failed to connect to grsaiapi.com' >&2\n"
        "exit 7\n",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    script = Path(__file__).resolve().parents[1] / "scripts" / "generate.sh"
    env = {
        **os.environ,
        "GRSAI_API_KEY": "test-key",
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
    }

    result = subprocess.run(
        ["bash", str(script), "--model", "gpt-image-2-vip", "--size", "2448x3264", "test prompt"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )

    assert result.returncode == 1
    assert "Generating with model: gpt-image-2-vip" in result.stderr
    assert "Generate request failed via" in result.stderr
    assert "curl exit 7" in result.stderr
    assert "Failed to connect to grsaiapi.com" in result.stderr


def test_generate_script_falls_back_to_second_api_node(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        "  *' --http1.1 '*) ;;\n"
        "  *) echo 'missing --http1.1' >&2; exit 2 ;;\n"
        "esac\n"
        "out=''\n"
        "url=''\n"
        "prev=''\n"
        "for arg in \"$@\"; do\n"
        "  if [ \"$prev\" = '-o' ]; then out=\"$arg\"; fi\n"
        "  case \"$arg\" in http*) url=\"$arg\" ;; esac\n"
        "  prev=\"$arg\"\n"
        "done\n"
        "case \"$url\" in\n"
        "  *grsaiapi.com*/v1/api/generate*) echo 'curl: (35) Recv failure: Connection reset by peer' >&2; exit 35 ;;\n"
        "  *grsai.dakka.com.cn*/v1/api/generate*) printf '%s' '{\"status\":\"succeeded\",\"results\":[{\"url\":\"https://files.example/generated.png\"}]}' > \"$out\"; printf '200'; exit 0 ;;\n"
        "  *files.example*) printf 'fake-image' > \"$out\"; exit 0 ;;\n"
        "esac\n"
        "echo \"unexpected url: $url\" >&2\n"
        "exit 3\n",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    script = Path(__file__).resolve().parents[1] / "scripts" / "generate.sh"
    env = {
        **os.environ,
        "GRSAI_API_KEY": "test-key",
        "GRSAI_BASE_URL": "https://grsaiapi.com",
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
    }

    result = subprocess.run(
        [
            "bash",
            str(script),
            "--model",
            "gpt-image-2-vip",
            "--size",
            "1024x1536",
            "--output",
            str(tmp_path),
            "test prompt",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )

    assert result.returncode == 0
    image_path = Path(result.stdout.strip())
    assert image_path.exists()
    assert image_path.read_text(encoding="utf-8") == "fake-image"
    assert "Generate request failed via https://grsaiapi.com" in result.stderr


def test_run_generate_uses_direct_api_before_shell(monkeypatch, tmp_path):
    import app.services.grsai as grsai

    calls = []

    def fake_direct(**kwargs):
        calls.append(kwargs)
        return grsai.GrsaiResult(success=True, image_path=str(tmp_path / "generated.png"))

    def fail_subprocess(*args, **kwargs):
        raise AssertionError("generate.sh should not run when direct generation succeeds")

    monkeypatch.setattr(grsai, "generate_image_direct", fake_direct)
    monkeypatch.setattr(grsai.subprocess, "run", fail_subprocess)

    result = grsai.run_generate(
        prompt="hello",
        model="gpt-image-2-vip",
        output_dir=str(tmp_path),
        size="1024x1536",
        quality="high",
    )

    assert result.success
    assert result.image_path == str(tmp_path / "generated.png")
    assert calls[0]["prompt"] == "hello"
    assert calls[0]["size"] == "1024x1536"


def test_direct_generation_falls_back_between_api_nodes(monkeypatch, tmp_path):
    import app.services.grsai as grsai

    requested_urls = []

    def fake_request_json(url, payload, timeout=1000):
        requested_urls.append(url)
        if "grsaiapi.com" in url:
            raise urllib.error.URLError(ConnectionResetError("reset"))
        return {"status": "succeeded", "results": [{"url": "https://files.example/generated.png"}]}

    def fake_urlretrieve(url, image_path):
        Path(image_path).write_bytes(b"fake-image")
        return image_path, None

    monkeypatch.setattr(grsai.config, "GRSAI_API_KEY", "test-key")
    monkeypatch.setattr(grsai.config, "GRSAI_BASE_URL", "https://grsaiapi.com")
    monkeypatch.setattr(grsai, "_request_json", fake_request_json)
    monkeypatch.setattr(grsai.urllib.request, "urlretrieve", fake_urlretrieve)

    result = grsai.generate_image_direct(
        prompt="hello",
        model="gpt-image-2-vip",
        output_dir=str(tmp_path),
        size="1024x1536",
        quality="high",
    )

    assert result.success
    assert result.image_path
    assert Path(result.image_path).read_bytes() == b"fake-image"
    assert requested_urls == [
        "https://grsaiapi.com/v1/api/generate",
        "https://grsai.dakka.com.cn/v1/api/generate",
    ]
