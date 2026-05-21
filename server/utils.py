import asyncio
import datetime
import os
import shutil
import tomllib
from typing import Any

for config_file in ["config.toml", "config.template.toml"]:
    if os.path.exists(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/" + config_file
    ):
        break
else:
    raise FileNotFoundError("No config file found.")

with open(config_file, "rb") as f:
    config_data: dict[str, Any] = tomllib.load(f)


def get_config(key: str, default: Any = "") -> Any:
    return config_data.get(key) or os.getenv(key, default)


def log(message: str) -> None:
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


CONTRIBUTOR_QUOTA_DEFAULT = get_config("CONTRIBUTOR_QUOTA_DEFAULT", 10)
DB_PATH = get_config("DB_PATH", "data/db.sqlite")
OPENAI_API_KEY = get_config("OPENAI_API_KEY", "")
EMAIL_SENDER = get_config("EMAIL_SENDER", "")
EMAIL_PASSWORD = get_config("EMAIL_PASSWORD", "")
EMAIL_SMTP_SERVER_PORT = get_config("EMAIL_SMTP_SERVER_PORT", None)


async def schedule_daily_backup() -> None:
    while True:
        try:
            now = datetime.datetime.now()
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            delay = (target - now).total_seconds()
            hours = int(delay // 3600)
            minutes = int((delay % 3600) // 60)
            log(f"Next database backup scheduled in {hours} hours and {minutes} minutes (at {target.strftime('%Y-%m-%d %H:%M')})")
            await asyncio.sleep(delay)
            
            # Copy database file
            backup_dir = os.path.join(os.path.dirname(DB_PATH) or "data", "backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_filename = f"db_{timestamp}.sqlite"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            await asyncio.to_thread(shutil.copy, DB_PATH, backup_path)
            log(f"Database backup created at {backup_path}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log(f"Error in backup schedule loop: {e}")
            await asyncio.sleep(60)


async def send_email(to_email: str, subject: str, body: str, headers: dict[str, str] | None = None) -> bool:
    """Sends an email asynchronously using the SMTP configuration from config.toml."""
    def _send() -> bool:
        import smtplib
        from email.header import Header
        from email.mime.text import MIMEText
        from email.utils import formatdate, make_msgid

        if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_SMTP_SERVER_PORT:
            log("Email configuration is missing (EMAIL_SENDER, EMAIL_PASSWORD, or EMAIL_SMTP_SERVER_PORT).")
            return False

        # Parse SMTP host and port
        try:
            host, port_str = EMAIL_SMTP_SERVER_PORT.split(":")
            port = int(port_str)
        except (ValueError, AttributeError):
            log("Invalid email server configuration (EMAIL_SMTP_SERVER_PORT).")
            return False
        
        # Create message
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = EMAIL_SENDER
        msg["To"] = to_email
        
        if headers:
            for k, v in headers.items():
                msg[k] = v

        # Extract domain for Message-ID
        domain = EMAIL_SENDER.split("@")[-1] if "@" in EMAIL_SENDER else "localhost"
        msg["Message-ID"] = make_msgid(domain=domain)
        msg["Date"] = formatdate(localtime=True)

        try:
            server = smtplib.SMTP(host, port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, [to_email], msg.as_string())
            server.quit()
            return True
        except Exception as e:
            log(f"Failed to send email: {e}")
            return False

    return await asyncio.to_thread(_send)

