---
paths:
  - "src/api/**/*.py"
  - "tests/**/*.py"
---
# API Development Rules
# Path-scoped — only activates when accessing matching files

- Validate all input with Pydantic schemas
- Use standard error response format: { "error": "...", "code": 400 }
- Every endpoint needs both unit and integration tests
- Document all endpoints with OpenAPI/Swagger
- Rate limit all public endpoints
