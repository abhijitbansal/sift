"""Send the rendered HTML digest by email over SMTP.

The SMTP password is never stored in config or logged — it comes from the
SIFT_SMTP_PASSWORD env var, falling back to the macOS login keychain
(service name SIFT_SMTP_PASSWORD).
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
import subprocess
from email.message import EmailMessage
from typing import Callable

from sift.config import EmailConfig

log = logging.getLogger("sift.deliver")

KEYCHAIN_SERVICE = "SIFT_SMTP_PASSWORD"
ENV_VAR = "SIFT_SMTP_PASSWORD"
SMTP_TIMEOUT_SECONDS = 30
SMTPS_PORT = 465


class DeliveryError(RuntimeError):
    """Email delivery could not be completed (missing password, SMTP failure)."""


def resolve_password() -> str:
    """Read the SMTP password from the environment, then the macOS keychain."""
    env_password = os.environ.get(ENV_VAR)
    if env_password:
        return env_password
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise DeliveryError(
            f"SMTP password not found: set ${ENV_VAR} or add keychain item "
            f"'{KEYCHAIN_SERVICE}'"
        ) from exc
    password = result.stdout.strip()
    if not password:
        raise DeliveryError(f"Keychain item '{KEYCHAIN_SERVICE}' is empty")
    return password


def build_message(email_cfg: EmailConfig, html: str, week: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Sift — Week {week}"
    msg["From"] = email_cfg.sender
    msg["To"] = email_cfg.recipient
    msg.set_content(
        f"Your weekly Sift digest for {week}. Open in an HTML-capable client to read it."
    )
    msg.add_alternative(html, subtype="html")
    return msg


def send_digest(
    email_cfg: EmailConfig | None,
    html: str,
    week: str,
    *,
    password_getter: Callable[[], str] = resolve_password,
    transport: Callable[[EmailConfig, str, EmailMessage], None] | None = None,
) -> bool:
    """Email the digest. Returns True if sent, False if delivery is disabled."""
    if email_cfg is None or not email_cfg.enabled:
        log.info("Email delivery disabled; skipping.")
        return False
    message = build_message(email_cfg, html, week)
    password = password_getter()
    (transport or _smtp_transport)(email_cfg, password, message)
    log.info("Emailed digest %s to %s", week, email_cfg.recipient)
    return True


def _smtp_transport(email_cfg: EmailConfig, password: str, message: EmailMessage) -> None:
    context = ssl.create_default_context()
    try:
        if email_cfg.port == SMTPS_PORT:
            with smtplib.SMTP_SSL(
                email_cfg.host, email_cfg.port, context=context, timeout=SMTP_TIMEOUT_SECONDS
            ) as server:
                server.login(email_cfg.sender, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(
                email_cfg.host, email_cfg.port, timeout=SMTP_TIMEOUT_SECONDS
            ) as server:
                if email_cfg.use_tls:
                    server.starttls(context=context)
                server.login(email_cfg.sender, password)
                server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise DeliveryError(f"SMTP delivery failed: {exc}") from exc
