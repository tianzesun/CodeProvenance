"""Parallel pair scoring must not race on the first transformers import."""

import builtins
import importlib.util
import subprocess
import sys
import threading
import time
import types

import pytest

from src.backend.engines.similarity import unixcoder_similarity as unixcoder


def test_the_import_runs_one_thread_at_a_time(monkeypatch) -> None:
    fake = types.SimpleNamespace(AutoModel=object(), AutoTokenizer=object())
    in_flight, peak = [0], [0]
    real_import = builtins.__import__

    def tracking_import(name, *args, **kwargs):
        if name != "transformers":
            return real_import(name, *args, **kwargs)
        in_flight[0] += 1
        peak[0] = max(peak[0], in_flight[0])
        time.sleep(0.02)  # widen the window two threads would need to overlap
        in_flight[0] -= 1
        return fake

    monkeypatch.setattr(builtins, "__import__", tracking_import)
    results = []
    threads = [
        threading.Thread(
            target=lambda: results.append(unixcoder._import_transformers())
        )
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert peak[0] == 1
    assert results == [(fake.AutoModel, fake.AutoTokenizer)] * 8


@pytest.mark.skipif(
    importlib.util.find_spec("transformers") is None,
    reason="transformers not installed",
)
def test_a_concurrent_first_import_succeeds_in_every_thread() -> None:
    """The real race: a fresh process, eight threads importing at once."""
    script = (
        "import threading\n"
        "from src.backend.engines.similarity import unixcoder_similarity as u\n"
        "failures = []\n"
        "def go():\n"
        "    try:\n"
        "        u._import_transformers()\n"
        "    except ImportError as exc:\n"
        "        failures.append(exc)\n"
        "threads = [threading.Thread(target=go) for _ in range(8)]\n"
        "[t.start() for t in threads]\n"
        "[t.join() for t in threads]\n"
        "print(len(failures))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == "0"
