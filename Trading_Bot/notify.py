import smtplib
import ssl
from email.mime.text import MIMEText

import config


def send_email(subject: str, html_body: str) -> None:
    if not (config.SMTP_USER and config.SMTP_PASS and config.EMAIL_TO):
        raise RuntimeError("SMTP_USER, SMTP_PASS, and EMAIL_TO must be set to send email")

    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM
    msg["To"] = config.EMAIL_TO

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context) as server:
        server.login(config.SMTP_USER, config.SMTP_PASS)
        server.sendmail(config.EMAIL_FROM, [config.EMAIL_TO], msg.as_string())
