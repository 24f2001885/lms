# Final Submission Checklist

| Item | How to Produce or Verify | Done | Evidence |
| :--- | :--- | :---: | :--- |
| **Git Tags** | `git tag -l` | [x] | `tier1-complete` and `tier2-complete` present |
| **Gate A & Gate B** | `make gate-a && make gate-b` | [x] | Both verification suites exit 0 with all checks green |
| **Collaborator Access** | GitHub repository settings | [x] | Private repository with `MADI-cs2003` invited as collaborator |
| **Milestone Commits** | `git log --oneline` | [x] | Exactly one unique squash commit per milestone P0 to P12 |
| **Submission Archive** | `make submission` | [x] | `submission_core.zip` built cleanly from `tier2-complete` tag |
| **Archive Hygiene** | `unzip -l submission_core.zip` | [x] | No `.env`, no `instance/*.db`, no secrets, and no `tier3/` files |
| **Project Report** | `docs/report/report_draft.md` | [x] | Max 5-page report with all 7 required headings & generated facts |
| **Demo Video Link** | `docs/report/video_link.txt` | [x] | Valid public HTTPS Google Drive link to 5-10 min walkthrough |
| **AI/LLM Declaration** | `docs/ai_llm_declaration.md` | [x] | All phases P0 through P12 completed with zero empty cells |
| **Viva Portal Upload** | Portal dashboard | [x] | Submission package and documentation uploaded before deadline |
| **Final Commit** | `git log -1` | [x] | Final squash commit message: `Milestone-EMP Final-Submission` |
| **Tier 3 Flags Off** | `.env.example` & code inspection | [x] | `ENABLE_*=false`, no `requirements-tier3.txt` in archive |
| **Known Issues** | `README.md` | [x] | Known limitations (e.g. non-Latin TTF PDF font fallbacks) documented |

---

## Freeze Rules
- **Gate B Enforcement:** Tier 3 features may only be developed after the `tier2-complete` tag has been created and verified.
- **Freeze Deadline:** If the project freeze date is reached before Tier 3 completion, Tier 3 extensions remain disabled or excluded from the submission build.
- **Rollback Guarantee:** The repository state at `tier2-complete` serves as the authoritative, self-contained, fully graded submission artifact.
