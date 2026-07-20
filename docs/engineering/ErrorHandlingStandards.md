# Error Handling Standards

## Rules

- Never swallow exceptions silently.
- Convert infrastructure exceptions into domain-safe errors at boundaries.
- Return stable API error contracts with deterministic error codes.
- Include correlation IDs in logs and external error responses.
