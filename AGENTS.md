# SQL formatting

- Do not use semicolons anywhere in SQL files, including comments and statement endings.
- Do not include empty or whitespace-only lines in SQL files.
- Keep separate executable statements in separate files when needed.

The SQLTools Trino driver splits input at every semicolon, including semicolons inside comments.

# Data storage

Do not persist query, example, exploration, or debug results locally or in Git. Display results in memory/stdout, and keep selected evidence in requested Markdown documentation. Keep notebook outputs and execution counts empty. SQL source, code/configuration, synthetic test fixtures and the nickname reference seed are allowed. Any local data export requires an explicit user request. Run `python3 tools/check_data_storage.py` before completion and enable `.githooks` with `git config core.hooksPath .githooks`.
