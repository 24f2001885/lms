# AI / LLM Usage Declaration

This document serves as the formal academic integrity log for the **Examination Management Portal (LMS)** project (Modern Application Development I). In accordance with course guidelines, all usage of Large Language Models (LLMs) and generative AI assistance is documented here and updated across each milestone phase.

Every file, architectural pattern, and business logic constraint in this repository is thoroughly reviewed, tested, and understood by the team, and can be defended individually during the viva evaluation.

---

## 1. Phase-by-Phase AI Usage Log

| Phase | Tool & Model Used | Request / Prompt Scope | Manual Verification & Changes Made by Team | Viva Defense Owner |
|---|---|---|---|---|
| **P0** | Gemini / Claude 3.5 | Repository skeleton, Dockerfile, Makefile, and initial smoke test setup. | Verified all Makefile commands with tabs; verified Docker offline build flags; checked that smoke tests pass. | Team Lead |
| **P1** | | | | |
| **P2** | | | | |
| **P3** | | | | |
| **P4** | | | | |
| **P5** | | | | |
| **P6** | | | | |
| **Final** | | Report synthesis, diagram formatting, and demo script review. | | Entire Team |

---

## 2. Pre-Viva Checklist

Before appearing for the viva evaluation, ensure:
- [ ] Every team member can explain the architecture and logic of the modules they own.
- [ ] No live secret keys, real API tokens, or production passwords have been committed or pasted into AI prompts.
- [ ] All automated tests pass 100% offline using `make test-core` and inside `docker compose --profile test run --rm test`.
- [ ] The git history contains clean, unique commit messages matching the course milestone specification.