# 🚀 Vibe Coding Commands

Quick commands for rapid development and release cycles with Claude Code.

## ⚡ Daily Development

```bash
# Run tests (fast feedback)
make test

# Quality check (before commits)
make check

# Fix formatting/linting
make fix

# Test coverage report
make coverage

# Build package
make build

# Pre-commit check (fix + test)
make ready
```

## 🚀 Instant Release

```bash
# Quick patch release (1.0.4 → 1.0.5)
make release-patch

# Minor release (1.0.4 → 1.1.0) 
make release-minor

# Major release (1.0.4 → 2.0.0)
make release-major
```

## 🔥 One-Liners for Claude

**Test everything:**
```bash
make ready && echo "✅ Ready to ship!"
```

**Ship it:**
```bash
make release-patch
```

**Check PyPI status:**
```bash
pip index versions django-container-manager
```

## 🎯 Workflow for Claude Sessions

1. **Make changes** (code, tests, docs)
2. **Quick check:** `make ready` 
3. **Commit changes:** Normal git workflow
4. **Release if ready:** `make release-patch`
5. **Verify publication:** Check GitHub Actions

## 🔄 Auto-Publication Flow

1. **`make release-patch`** → Fixes code, runs tests, bumps version, commits, tags, pushes
2. **GitHub Actions** → Builds, tests, publishes to PyPI
3. **PyPI** → Package available worldwide in minutes

## 🛡️ Safety Checks

- All tests must pass before release
- Ruff linting enforced 
- Coverage maintained at 75%+
- Trusted publishing (no API keys)
- Automated quality gates

## 📋 All Commands

```bash
make help  # Show all available commands
```

---

**🎉 Happy vibe coding with Claude!**