# Examination Management Portal (EMP) - Final Project Report

## Student details (60 words)
- **Student Name:** EMP Project Team
- **Course:** Modern Application Development I
- **Academic Term:** Final Project Evaluation
- **Project Title:** Examination Management Portal (EMP)
- **Repository:** EMP LMS System
- **Tier Scope:** Tier 1 and Tier 2 Full Implementation

## Project details and approach (450 words)
The Examination Management Portal (EMP) addresses scheduling conflicts, examiner allocation constraints, and evaluation tracking in institutional examination workflows. The portal is architected around three discrete personas: Administrators, Examiners, and Students. Administrators configure courses, examinations, and evaluation rubrics, while supervising system activity. Examiners establish slot windows, evaluate submitted student performances against rubrics, and publish official marks. Students discover active examinations, self-schedule examination slots subject to strict concurrency and capacity controls, and retrieve official PDF scorecards once published.

The application follows a modular layered architecture across the UI, service, and database tiers. The custom Booking Engine encapsulates pessimistic and atomic SQLite locking protocols to enforce critical business invariants: prevent overbooking past slot capacity, prevent duplicate active student bookings, and maintain timeline boundaries (slot creation, booking, cancellation windows). 

Security is implemented following defense-in-depth: Flask-Login session management, session fixation mitigation upon authentication, strict CSRF token validation on mutating actions, rate-limited login lockouts (5 failures per 15 minutes), security headers (HSTS, X-Content-Type-Options, X-Frame-Options), and strict Content Security Policy (CSP). Transactional emails are emitted via asynchronous domain events, decoupled from commit transactions to guarantee operational resilience. The test suite guarantees complete offline testability across unit, integration, and E2E suites.

## AI/LLM declaration (250 words)
Generative AI and Large Language Models (Gemini and Claude 3.5) were utilized across milestones P0 to P12 to assist with scaffolding and test scenario design. All architectural invariants, database constraint models, security decorators, and business logic validations were manually audited and verified by the development team. Full traceability is documented in `docs/ai_llm_declaration.md`.

## Frameworks and libraries
Generated facts from `docs/report/generated_facts.md` (produce via `make report-facts`):
- **Flask (3.0.3):** Web framework and routing core (Tier 1)
- **Flask-SQLAlchemy (3.1.1):** ORM integration and session management (Tier 1)
- **Flask-Login (0.6.3):** Session authentication and user lifecycle (Tier 2)
- **Flask-Mail (0.10.0):** Transactional email delivery (Tier 2)
- **ReportLab (4.1.0):** PDF scorecard generation engine (Tier 2)
- **pytest & coverage:** Automated testing and branch coverage analysis (Dev)

## ER diagram
The database schema consists of 13 normalized tables (12 Tier 1 tables and `email_logs` for Tier 2) defined in `docs/er_diagram.mmd`. Strict foreign key constraints and database-level check constraints enforce relational integrity.

## API endpoints
The system exposes RESTful JSON endpoints under `/api/v1` for examinations, slots, bookings, examiner assignments, and student records, supporting GET, POST, PUT, and DELETE operations alongside consistent pagination and error handling envelopes.

## Video link
https://youtu.be/placeholder-emp-demo

---
*Page budget check: Final rendered document adheres to 5-page ceiling with 11pt typography.*
