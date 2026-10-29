# SQL formatting

- Do not use semicolons anywhere in SQL files, including comments and statement endings.
- Do not include empty or whitespace-only lines in SQL files.
- Keep separate executable statements in separate files when needed.

The SQLTools Trino driver splits input at every semicolon, including semicolons inside comments.
