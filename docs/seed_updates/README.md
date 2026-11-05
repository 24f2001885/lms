# Seed Updates Directory

## Purpose & Conventions

This directory holds **Phase Update Specifications** (`PN_update_<topic>.md`).

### The Golden Rule
> **Never overwrite an existing file that already contains working application code.**

When a new milestone phase requires modifying a file created in an earlier phase (such as adding database setup or authentication to `app/__init__.py`):
1. The milestone script writes an update specification file here (e.g., `docs/seed_updates/P1_update_app_init.md`).
2. The developer reviews:
   - (a) The update prompt in this folder.
   - (b) The *current* working code in the target file.
3. The file is carefully extended so that all existing tests remain green while new functionality is cleanly integrated.
4. Update prompt files are preserved in version control as an audit trail of incremental architecture evolution.