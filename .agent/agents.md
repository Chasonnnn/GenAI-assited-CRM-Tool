# Agent Development Rules

## Code Quality Standards

### Zero Tolerance for Warnings and Bugs
**CRITICAL**: When you encounter any warnings, bugs, or issues during development:
- **DO NOT** leave them for later
- **DO NOT** add TODO comments
- **IMMEDIATELY** fix them before proceeding
- If a warning appears during build/test, stop and fix it

**Examples of issues to fix immediately:**
- ❌ Build warnings (TypeScript errors, lint errors)
- ❌ Test failures
- ❌ Runtime warnings (React hooks, deprecations)
- ❌ Performance issues (N+1 queries, memory leaks)
- ❌ Security vulnerabilities
- ❌ Configuration warnings (Turbopack, dependencies)

### Best Practices
- Run tests after every significant change
- Fix lint/type errors before committing
- Address deprecation warnings immediately
- Optimize performance bottlenecks when discovered
- Never commit broken code

### Rationale
Leaving warnings and bugs creates technical debt that:
- Compounds over time
- Makes future debugging harder
- Degrades code quality
- Reduces team velocity
- Can cause production issues

**Remember**: A clean codebase is a maintainable codebase.
