import os
import time
import smtplib
from contextlib import asynccontextmanager
from email.message import EmailMessage
from collections import defaultdict
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import EmailStr, ValidationError, BaseModel


def send_ionos_email(
    name: str,
    sender_email: str,
    message_body: str,
    subject: str | None = None,
    debug: bool = False,
) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.ionos.de")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.environ["SMTP_USERNAME"]
    smtp_pass = os.environ["SMTP_PASSWORD"]
    recipient = os.getenv("RECIPIENT_EMAIL", smtp_user)

    msg = EmailMessage()
    msg["Subject"] = subject or f"New Contact Inquiry from {name}"
    msg["From"] = f"Website Contact <{smtp_user}>"
    msg["To"] = recipient
    msg["Reply-To"] = f"{name} <{sender_email}>"

    msg.set_content(
        f"Name: {name}\n"
        f"Email: {sender_email}\n"
        f"{'-' * 40}\n\n"
        f"{message_body}\n"
    )

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
            if debug:
                server.set_debuglevel(1)
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            if debug:
                server.set_debuglevel(1)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once on container startup
    if os.getenv("SEND_STARTUP_TEST_MAIL", "false").lower() in ("true", "1", "yes"):
        print("Sending IONOS SMTP startup test email...")
        try:
            smtp_user = os.environ["SMTP_USERNAME"]
            send_ionos_email(
                name="Docker Startup Check",
                sender_email=smtp_user,
                message_body="Your contact-api container started successfully and connected to IONOS SMTP.",
                subject="✅ Contact API - Startup SMTP Test"
            )
            print("Startup test email sent successfully!")
        except Exception as e:
            print(f"❌ Startup test email failed: {e}")
    yield


app = FastAPI(title="AIRA Contact Mailer", lifespan=lifespan)

# Allow requests from your Vue app (comma-separated in env, or "*")
allowed_origins = os.getenv("CORS_ALLOW_ORIGIN", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

# Simple in-memory IP rate limiter (max 5 submissions per 10 minutes per IP)
RATE_LIMIT_WINDOW = 600
RATE_LIMIT_MAX = 5
ip_requests: dict[str, list[float]] = defaultdict(list)


class ContactPayload(BaseModel):
    name: str
    email: EmailStr
    message: str


def is_rate_limited(ip: str) -> bool:
    now = time.time()
    ip_requests[ip] = [t for t in ip_requests[ip] if now - t < RATE_LIMIT_WINDOW]
    if len(ip_requests[ip]) >= RATE_LIMIT_MAX:
        return True
    ip_requests[ip].append(now)
    return False


@app.post("/f/contact")
async def handle_contact(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    message: str = Form(""),
    gotcha: str = Form("", alias="_gotcha"),
):
    # 1. Honeypot check: if a bot filled _gotcha, pretend it succeeded
    if gotcha.strip():
        return JSONResponse({"success": True, "message": "Message sent."})

    # 2. Rate limiting
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()
    if is_rate_limited(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    # 3. Validate fields
    try:
        validated = ContactPayload(
            name=name.strip(),
            email=email.strip(),
            message=message.strip(),
        )
        if not validated.name or not validated.message:
            raise ValueError("Name and message cannot be empty.")
    except (ValidationError, ValueError):
        raise HTTPException(status_code=400, detail="Please provide a valid name, email, and message.")

    # 4. Send via IONOS SMTP
    try:
        send_ionos_email(validated.name, str(validated.email), validated.message)
    except Exception as e:
        print(f"SMTP Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email via mail server.")

    return JSONResponse({"success": True, "message": "Message sent successfully!"})


@app.get("/health")
async def health():
    return {"status": "ok"}
