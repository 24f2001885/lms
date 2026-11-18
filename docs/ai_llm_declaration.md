# AI / LLM Usage Declaration

This document serves as the formal academic integrity log for the **Examination Management Portal (LMS)** project (Modern Application Development I). In accordance with course guidelines, all usage of Large Language Models (LLMs) and generative AI assistance is documented here and updated across each milestone phase.

Every file, architectural pattern, and business logic constraint in this repository is thoroughly reviewed, tested, and understood by the team, and can be defended individually during the viva evaluation.

---

## 1. Phase-by-Phase AI Usage Log

| Phase | Tool & Model Used | Request / Prompt Scope | Manual Verification & Changes Made by Team | Viva Defense Owner |
|---|---|---|---|---|
| **P0** | Gemini / Claude 3.5 | Repository skeleton, Dockerfile, Makefile, and initial smoke test setup. | Verified all Makefile commands with tabs; verified Docker offline build flags; checked that smoke tests pass. | Lead Architect |
| **P1** | Gemini / Claude 3.5 | SQLite models, schema constraints, migrations, pragmas | Verified foreign keys, check constraints, cascading rules and index definitions | Database Engineer |
| **P2** | Gemini / Claude 3.5 | Authentication routes, password hashing, registration, role gates | Audited password hashing cost, session fixation mitigation and validation rules | Security Engineer |
| **P3** | Gemini / Claude 3.5 | Admin course, exam, rubric management and window timeline logic | Verified rubric sum validation (100%), slot creation window bounds and filters | Backend Developer |
| **P4** | Gemini / Claude 3.5 | Examiner dashboard, slot management, rubric evaluation workflow | Verified score bounds, remarks requirements and draft/submit/publish states | Backend Developer |
| **P5** | Gemini / Claude 3.5 | Student portal, examination discovery, slot booking & cancellation | Verified concurrency locks, capacity decrement and deadline cancel rules | Full-Stack Developer |
| **P6** | Gemini / Claude 3.5 | Booking engine race condition hardening, background sync & cleanup jobs | Audited SQLite write transaction locks and soft-delete purge queries | Core Architect |
| **P7** | Gemini / Claude 3.5 | RESTful JSON API endpoints, serialization, error schemas & pagination | Validated HTTP status codes (200, 201, 404, 409, 422) and API matrix | API Engineer |
| **P8** | Gemini / Claude 3.5 | Interactive Chart.js analytics dashboards for all three roles | Tested canvas fallback accessibility tables, data aggregation and dark mode | Frontend Engineer |
| **P9** | Gemini / Claude 3.5 | Dual-layer validation (HTML5 + vanilla JS mirror) and server rules | Verified client/server parity, custom error banners and input sanitization | Frontend Engineer |
| **P10** | Gemini / Claude 3.5 | Responsive mobile-first CSS layout, card grids, off-canvas navigation | Verified 375px/768px/1280px viewports, WCAG 2.1 AA contrast and focus rings | UI/UX Designer |
| **P11** | Gemini / Claude 3.5 | Flask-Login migration, session timeouts, lockout, security headers, CSP | Verified session fixation protection, nonce-based CSP, 5-failure lockout | Security Architect |
| **P12** | Gemini / Claude 3.5 | ReportLab PDF scorecard generation, transactional email event hooks | Verified zero mark leakage in emails, safe background dispatch, retry job | Lead Architect |
| **Final** | Gemini / Claude 3.5 | Report synthesis, diagram formatting, and demo script review. | Verified deterministic facts output, ER diagram consistency, gate criteria | Entire Team |

---

## 2. Pre-Viva Checklist

Before appearing for the viva evaluation, ensure:
- [x] Every team member can explain the architecture and logic of the modules they own.
- [x] No live secret keys, real API tokens, or production passwords have been committed or pasted into AI prompts.
- [x] All automated tests pass 100% offline using `make test-core` and inside `docker compose --profile test run --rm test`.
- [x] The git history contains clean, unique commit messages matching the course milestone specification.
