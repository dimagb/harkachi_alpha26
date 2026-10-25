import re

import pytest

from app.config import Settings


@pytest.fixture(autouse=True)
def clear_security_environment(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)


def test_default_settings_allow_demo_startup():
    settings = Settings(_env_file=None)

    assert settings.demo_mode is True
    assert settings.jwt_secret == "local-demo-secret-change-before-deployment"


@pytest.mark.parametrize("secret", ["", "short", "s" * 31])
def test_demo_mode_allows_short_secret(monkeypatch, secret):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("JWT_SECRET", secret)

    assert Settings(_env_file=None).jwt_secret == secret


def test_non_demo_mode_rejects_missing_secret(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")

    with pytest.raises(ValueError, match="DEMO_MODE=false: задайте свой JWT_SECRET"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "secret", ["local-demo-secret-change-before-deployment", "", "short", "s" * 31]
)
def test_non_demo_mode_rejects_insecure_secret(monkeypatch, secret):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("JWT_SECRET", secret)

    with pytest.raises(
        ValueError,
        match=re.escape(
            "DEMO_MODE=false: задайте свой JWT_SECRET (не короче 32 символов)"
        ),
    ):
        Settings(_env_file=None)


@pytest.mark.parametrize("secret", ["s" * 32, "s" * 64])
def test_non_demo_mode_accepts_custom_secret(monkeypatch, secret):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("JWT_SECRET", secret)

    settings = Settings(_env_file=None)

    assert settings.demo_mode is False
    assert settings.jwt_secret == secret
