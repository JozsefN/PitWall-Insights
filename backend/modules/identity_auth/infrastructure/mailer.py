import smtplib
import ssl
from email.message import EmailMessage

from app.config import settings


class MailUnavailable(Exception):
    pass


def mail_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_username and settings.smtp_password)


def send_verification_code(recipient: str, code: str) -> None:
    if not mail_configured():
        raise MailUnavailable("Email verification is unavailable on this instance.")
    message = EmailMessage()
    message["From"] = settings.smtp_from_email or settings.smtp_username
    message["To"] = recipient
    message["Subject"] = "Your PitWall Insights verification code"
    message.set_content(f"Your PitWall Insights code is {code}. It expires in 10 minutes.\n\n"
                        "If you did not request this code, you can ignore this message.")
    tls = ssl.create_default_context()
    try:
        if settings.smtp_implicit_tls:
            client = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=tls, timeout=10)
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
        with client:
            if not settings.smtp_implicit_tls:
                client.starttls(context=tls)
            client.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            client.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        raise MailUnavailable("The verification email could not be sent. Try again in a minute.") from error
