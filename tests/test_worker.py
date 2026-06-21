from __future__ import annotations


def test_worker_entrypoint_exports_main():
    import src.worker

    assert src.worker.main.__name__ == "main"
