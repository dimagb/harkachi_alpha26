from app import worker


def test_worker_recovers_and_touches_heartbeat_on_every_iteration(
    pipeline_factory, monkeypatch, tmp_path
):
    from app.worker import run_once

    assert callable(run_once)
    heartbeat = tmp_path / "heartbeat"
    handlers, iterations, recovered, waits = {}, [], [], []

    class Stop:
        stopped = False

        def is_set(self):
            return self.stopped

        def set(self):
            self.stopped = True

        def wait(self, seconds):
            waits.append(seconds)

    stop = Stop()

    def process(factory, providers, today):
        assert factory is pipeline_factory
        assert heartbeat.exists()
        iterations.append(heartbeat.stat().st_mtime_ns)
        heartbeat.unlink()
        providers.heartbeat()
        assert heartbeat.exists()
        if len(iterations) == 2:
            stop.set()
        return False

    monkeypatch.setattr(worker, "HEARTBEAT_PATH", heartbeat)
    monkeypatch.setattr(worker, "Event", lambda: stop)
    monkeypatch.setattr(
        worker.signal, "signal", lambda sig, handler: handlers.update({sig: handler})
    )
    monkeypatch.setattr(
        worker, "create_engine", lambda *_args, **_kwargs: pipeline_factory.kw["bind"]
    )
    monkeypatch.setattr(
        worker, "sessionmaker", lambda *_args, **_kwargs: pipeline_factory
    )
    monkeypatch.setattr(
        worker, "recover_stale", lambda factory: recovered.append(factory)
    )
    monkeypatch.setattr(worker, "run_once", process)
    worker.main()
    assert recovered == [pipeline_factory]
    assert len(iterations) == 2
    assert waits == [0.5, 0.5]
    assert not heartbeat.exists()
    assert set(handlers) == {worker.signal.SIGTERM, worker.signal.SIGINT}
