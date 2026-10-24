from types import SimpleNamespace

import pytest

from app import worker


@pytest.mark.parametrize("fail_first", [False, True])
def test_maintenance_runs_during_busy_queue_and_survives_errors(
    monkeypatch, tmp_path, fail_first
):
    seconds = [0, 15, 30, 60, 90, 120]
    iterations = []
    maintenance = []

    class Stop:
        def is_set(self):
            return len(iterations) == len(seconds)

        def set(self):
            pass

        def wait(self, timeout):
            pytest.fail("Busy queue must not wait")

    class Engine:
        def dispose(self):
            pass

    def process(*args):
        iterations.append(seconds[len(iterations)])
        return True

    def maintain(name):
        def run(*args):
            now = seconds[len(iterations)]
            maintenance.append((name, now))
            if fail_first and now == 0:
                raise RuntimeError("sensitive database parameters")

        return run

    monkeypatch.setattr(worker, "Event", Stop)
    monkeypatch.setattr(worker.signal, "signal", lambda *args: None)
    monkeypatch.setattr(worker, "HEARTBEAT_PATH", tmp_path / "heartbeat")
    monkeypatch.setattr(worker, "create_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(worker, "sessionmaker", lambda *args: object())
    monkeypatch.setattr(worker, "run_once", process)
    monkeypatch.setattr(worker, "recover_stale", maintain("recover"))
    monkeypatch.setattr(worker, "expire_due", maintain("expire"), raising=False)
    monkeypatch.setattr(
        worker,
        "time",
        SimpleNamespace(monotonic=lambda: seconds[len(iterations)]),
        raising=False,
    )
    worker.main()
    assert iterations == seconds
    assert [at for name, at in maintenance if name == "expire"] == [0, 30, 60, 90, 120]
    assert [at for name, at in maintenance if name == "recover"] == [0, 60, 120]
    assert not (tmp_path / "heartbeat").exists()
