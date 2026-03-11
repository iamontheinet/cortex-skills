# Learnings

This file is **append-only**. After each streaming run, the agent records any deviations
between what SKILL.md instructed and what actually worked. Before the next run, the agent
reads this file and applies any PENDING fixes to the bundled skill files.

**Format**: Each entry follows the template in `FEEDBACK_TEMPLATE.md`.

**Statuses**:
- `PENDING` — Learning recorded but bundled skill files not yet updated.
- `APPLIED` — Learning recorded AND the corresponding skill files have been patched.

---

<!-- Append new entries below this line -->

## 2026-03-05: RSA key mismatch -- multiple .p8 files on system

- **Problem**: SKILL.md Step 2 says to reuse an existing `.p8` file if found. The agent found `/Users/ddesai/rsa_key.p8` and used it, but it was not registered with the target Snowflake user (`iamontheinet` on `JBGGDHN-AIB28454`). JWT auth failed with error 250001.
- **Root cause**: The system had 22 different `.p8` files for different accounts/users. The generic `rsa_key.p8` in the home directory was for a different account. The correct key was `coco_streaming_key.p8`.
- **Fix applied**: Searched for all `.p8` files on the system, identified `coco_streaming_key.p8` by naming convention, and used it successfully.
- **Skill files to update**: SKILL.md Step 2 should advise testing the key with a simple connector login before proceeding to object creation, rather than assuming any found `.p8` file is valid.
- **Status**: PENDING

## 2026-03-05: CoCo SQL connection key path mismatch

- **Problem**: The `coco-streaming` CoCo connection referenced a key at `/Users/ddesai/Apps/coco-streaming/coco_streaming_key.p8` which did not exist. Could not use `snowflake_sql_execute` with this connection for verification queries.
- **Root cause**: The CoCo connection config had a stale `private_key_file` path. This is an environment issue, not a skill issue.
- **Fix applied**: Used the project's Python venv and `snowflake.connector` directly for verification instead of the CoCo SQL tool.
- **Skill files to update**: SKILL.md Step 6 (Verify Data) should note that if the CoCo connection fails, verification can be done via the project's Python connector as a fallback.
- **Status**: PENDING
