from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_invite_email(
    *,
    to_email: str,
    business_name: str,
    invited_by_name: str,
    role: str,
    accept_url: str,
) -> None:
    """Send an invitation email. Uses SendGrid if configured, SMTP if configured,
    or logs to console in local/test environments."""
    role_label = "Admin" if role == "business_admin" else "Team Member"
    subject = f"You've been invited to join {business_name} on WhatsAgent AI"
    html_body = _render_invite_html(
        business_name=business_name,
        invited_by_name=invited_by_name,
        role_label=role_label,
        accept_url=accept_url,
    )

    if settings.sendgrid_api_key:
        await _send_sendgrid(to=to_email, subject=subject, html=html_body)
    elif settings.smtp_host:
        await asyncio.to_thread(_send_smtp, to=to_email, subject=subject, html=html_body)
    else:
        logger.info(
            "INVITE EMAIL (no provider configured) → to=%s subject=%r accept_url=%s",
            to_email,
            subject,
            accept_url,
        )


async def _send_sendgrid(*, to: str, subject: str, html: str) -> None:
    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {
            "email": settings.email_from_address,
            "name": settings.email_from_name,
        },
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
            json=payload,
        )
    if response.status_code >= 400:
        logger.error("SendGrid error %d: %s", response.status_code, response.text)


def _send_smtp(*, to: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{settings.email_from_address}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:  # type: ignore[arg-type]
        smtp.ehlo()
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)


def _render_invite_html(
    *,
    business_name: str,
    invited_by_name: str,
    role_label: str,
    accept_url: str,
) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;margin:0;padding:40px 20px">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;border:1px solid #e2e8f0;overflow:hidden">
    <div style="background:#6366f1;padding:28px 32px">
      <h1 style="color:#fff;margin:0;font-size:20px;font-weight:700">WhatsAgent AI</h1>
    </div>
    <div style="padding:32px">
      <h2 style="margin:0 0 8px;font-size:18px;color:#0f172a">You're invited!</h2>
      <p style="color:#475569;line-height:1.6;margin:0 0 24px">
        <strong>{invited_by_name}</strong> has invited you to join
        <strong>{business_name}</strong> on WhatsAgent AI as a
        <strong>{role_label}</strong>.
      </p>
      <a href="{accept_url}"
         style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;
                padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px">
        Accept invitation
      </a>
      <p style="margin:24px 0 0;color:#94a3b8;font-size:13px">
        This invitation expires in 7 days. If you weren't expecting this,
        you can safely ignore this email.
      </p>
    </div>
  </div>
</body>
</html>"""
