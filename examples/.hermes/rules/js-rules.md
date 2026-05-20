---
paths:
  - "src/**/*.{js,jsx,ts,tsx}"
  - "tests/**/*.test.{js,jsx,ts,tsx}"
---
# JavaScript/TypeScript Rules
# Path-scoped — only activates when accessing JS/TS files

- Use named exports only, no default exports
- Prefer async/await over raw promises
- Use `const` by default, `let` only when reassignment is needed
- Run prettier before committing
- Keep components under 200 lines
- Use TypeScript strict mode for new files
