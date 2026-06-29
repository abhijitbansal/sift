"""Unit tests for email delivery (SMTP is mocked; no real send)."""

import pytest

from sift import deliver
from sift.config import EmailConfig


def email_cfg(enabled=True, port=587, use_tls=True):
    return EmailConfig(
        enabled=enabled,
        host="smtp.example.com",
        sender="sift@example.com",
        recipient="me@example.com",
        port=port,
        use_tls=use_tls,
    )


def test_build_message_has_subject_recipients_and_html():
    msg = deliver.build_message(email_cfg(), "<h1>hi</h1>", "2026-26")

    assert msg["Subject"] == "Sift — Week 2026-26"
    assert msg["From"] == "sift@example.com"
    assert msg["To"] == "me@example.com"
    html_parts = [p for p in msg.walk() if p.get_content_type() == "text/html"]
    assert html_parts and "<h1>hi</h1>" in html_parts[0].get_content()


def test_send_digest_disabled_returns_false_without_transport():
    calls = []

    sent = deliver.send_digest(
        email_cfg(enabled=False),
        "<p>x</p>",
        "2026-26",
        password_getter=lambda: "pw",
        transport=lambda *a: calls.append(a),
    )

    assert sent is False
    assert calls == []


def test_send_digest_none_config_is_noop():
    assert deliver.send_digest(None, "<p>x</p>", "2026-26", transport=lambda *a: None) is False


def test_send_digest_invokes_transport_with_message():
    captured = {}

    def fake_transport(cfg, password, message):
        captured["cfg"] = cfg
        captured["password"] = password
        captured["to"] = message["To"]

    sent = deliver.send_digest(
        email_cfg(),
        "<p>digest</p>",
        "2026-26",
        password_getter=lambda: "secret-pw",
        transport=fake_transport,
    )

    assert sent is True
    assert captured["password"] == "secret-pw"
    assert captured["to"] == "me@example.com"


def test_resolve_password_prefers_env(monkeypatch):
    monkeypatch.setenv(deliver.ENV_VAR, "env-password")

    assert deliver.resolve_password() == "env-password"


def test_resolve_password_raises_when_absent(monkeypatch):
    monkeypatch.delenv(deliver.ENV_VAR, raising=False)
    # Force the keychain lookup to fail deterministically.
    monkeypatch.setattr(
        deliver.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("no security cmd")),
    )

    with pytest.raises(deliver.DeliveryError):
        deliver.resolve_password()


class _FakeServer:
    def __init__(self, *args, **kwargs):
        self.events = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.events.append("starttls")

    def login(self, user, password):
        self.events.append(f"login:{user}")

    def send_message(self, message):
        self.events.append("send")


def test_smtp_transport_starttls_path(monkeypatch):
    captured = {}

    def factory(*args, **kwargs):
        server = _FakeServer()
        captured["server"] = server
        return server

    monkeypatch.setattr(deliver.smtplib, "SMTP", factory)
    cfg = email_cfg(port=587, use_tls=True)
    msg = deliver.build_message(cfg, "<p>x</p>", "2026-26")

    deliver._smtp_transport(cfg, "pw", msg)

    assert "starttls" in captured["server"].events
    assert "send" in captured["server"].events


def test_smtp_transport_implicit_tls_on_465(monkeypatch):
    captured = {}

    def factory(*args, **kwargs):
        server = _FakeServer()
        captured["server"] = server
        return server

    monkeypatch.setattr(deliver.smtplib, "SMTP_SSL", factory)
    cfg = email_cfg(port=465)
    msg = deliver.build_message(cfg, "<p>x</p>", "2026-26")

    deliver._smtp_transport(cfg, "pw", msg)

    assert "send" in captured["server"].events
    assert "starttls" not in captured["server"].events  # implicit TLS, no STARTTLS


def test_smtp_transport_wraps_failure(monkeypatch):
    import smtplib

    def boom(*args, **kwargs):
        raise smtplib.SMTPException("nope")

    monkeypatch.setattr(deliver.smtplib, "SMTP", boom)
    cfg = email_cfg(port=587)
    msg = deliver.build_message(cfg, "<p>x</p>", "2026-26")

    with pytest.raises(deliver.DeliveryError):
        deliver._smtp_transport(cfg, "pw", msg)
