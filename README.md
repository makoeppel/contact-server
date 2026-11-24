# AIRA Contact API

A lightweight, self-hosted FastAPI service that receives contact form submissions from a frontend application (such as Vue 3) and relays them via **SMTP**.

## Features

- **SMTP Compatible:** Supports both Implicit SSL (`465`) and STARTTLS (`587`), automatically setting the `From` header to your authenticated mailbox and the visitor's address in `Reply-To`.
- **Spam Protection:** Includes a hidden `_gotcha` honeypot field and in-memory per-IP rate limiting (5 requests per 10 minutes).
- **Startup Connection Test:** Optional test email on container startup to verify SMTP credentials and firewall connectivity immediately.
- **CORS Ready:** Configurable allowed origins for local development and production domains.

---

## Project Structure

```text
contact-server/
├── Dockerfile
├── docker-compose.yml
├── main.py
├── requirements.txt
└── README.md
