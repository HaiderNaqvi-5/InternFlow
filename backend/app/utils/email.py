import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger("internflow.mail")
settings = get_settings()


def send_email(to: str, subject: str, html_body: str, text_body: str | None = None) -> bool:
    """Send an email through configured SMTP. In development without an SMTP
    host, the email is logged to the application log instead so flows can be
    demoed end-to-end."""
    if not settings.SMTP_HOST:
        logger.info(
            "[dev-email] To: %s | Subject: %s\n%s",
            to,
            subject,
            text_body or html_body,
        )
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to
    msg.attach(MIMEText(text_body or _strip_html(html_body), "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [to], msg.as_string())
        return True
    except Exception as exc:  # pragma: no cover
        logger.error("Email send failed to %s: %s", to, exc)
        return False


def _strip_html(html: str) -> str:
    import re

    return re.sub(r"<[^>]+>", " ", html).strip()