# Contributing to Duq Tracing

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Set up development environment for Python and/or Go
4. Create a feature branch from `master`

## Development Setup

### Python

```bash
cd python
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Go

```bash
cd go
go mod download
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Changes

- Write clean, readable code
- Follow existing code patterns
- Add tests for new functionality
- Keep Python and Go implementations in sync

### 3. Test Your Changes

#### Python

```bash
cd python
pytest
ruff check .
mypy .
```

#### Go

```bash
cd go
go test ./...
golangci-lint run
```

### 4. Commit Your Changes

Use conventional commit messages:

```
feat(python): add decorator for async tracing
fix(go): handle nil span gracefully
docs: update quick start guide
test(python): add tests for middleware
```

### 5. Submit a Pull Request

1. Push your branch to your fork
2. Open a Pull Request against `master`
3. Fill out the PR template
4. Wait for review

## Code Style

### Python

- Use Python 3.11+ features
- Follow PEP 8 with 100 char line limit
- Use type hints for all public functions
- Use `ruff` for linting
- Use `mypy` for type checking

### Go

- Follow [Effective Go](https://go.dev/doc/effective_go)
- Use `gofmt` for formatting
- Use `golangci-lint` for linting

## Testing

### Python

```bash
cd python
pytest --cov=duq_tracing --cov-report=html
```

### Go

```bash
cd go
go test -cover ./...
```

## Keeping Implementations in Sync

This library has both Python and Go implementations. When adding features:

1. Implement in both languages (if applicable)
2. Ensure consistent behavior
3. Update documentation for both
4. Run tests for both

## Pull Request Guidelines

### PR Title

Use conventional commit format:

- `feat: ...` - New feature
- `fix: ...` - Bug fix
- `docs: ...` - Documentation only
- `refactor: ...` - Code restructuring
- `test: ...` - Test additions/changes
- `chore: ...` - Maintenance tasks

Include scope if change is language-specific:
- `feat(python): ...`
- `fix(go): ...`

### PR Description

Include:
- Summary of changes
- Which languages are affected
- Related issue number (if any)
- Testing performed
- Breaking changes (if any)

## Reporting Issues

### Bug Reports

Include:
- Clear description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Language/version (Python X.X or Go X.X)
- Relevant logs or error messages

### Feature Requests

Include:
- Clear description of the feature
- Use case / motivation
- Proposed implementation (optional)
- Both Python and Go considerations

## Security

For security vulnerabilities, please see [SECURITY.md](SECURITY.md) for reporting instructions.

## Questions?

Open a GitHub Discussion or Issue for questions.

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License.
