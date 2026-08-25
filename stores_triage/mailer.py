"""Send the vendor mail. This half of the irreversible action really sends.

The recipient is a mailbox the operator controls, standing in for the vendor.
No real vendor address is ever configured here.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any


class MailConfigError(RuntimeError):
    pass


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MailConfigError(f"{name} is not set. Copy .env.example to .env.")
    return value


def compose(
    *,
    indent_no: str,
    part_no: str,
    description: str,
    qty: int,
    uom: str,
    vendor_name: str,
    needed_by: str,
) -> EmailMessage:
    """Build the exact message. The dossier shows this before anyone approves it."""
    msg = EmailMessage()
    msg["Subject"] = f"Indent {indent_no} - {part_no} - {qty} {uom}"
    msg["From"] = _required("SMTP_USER")
    msg["To"] = _required("VENDOR_MAIL_TO")
    msg.set_content(
        f"""Dear {vendor_name},

Please supply against indent {indent_no}:

  Part      : {part_no}
  Item      : {description}
  Quantity  : {qty} {uom}
  Needed by : {needed_by}

Kindly confirm dispatch and share the consignment number once despatched.

Regards,
Stores
"""
    )
    return msg


def send(msg: EmailMessage) -> dict[str, Any]:
    host = _required("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = _required("SMTP_USER")
    password = _required("SMTP_PASSWORD")

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)

    return {
        "sent": True,
        "to": msg["To"],
        "subject": msg["Subject"],
    }
