# 🚀 Django Container Manager - Vibe Coding Makefile
# Quick commands for rapid development with Claude Code

.PHONY: test check fix build coverage release-patch release-minor release-major clean help ready

# Default target
all: check test

# 🧪 Run tests (fast feedback)
test:
	@echo "🧪 Running tests..."
	@uv run python manage.py test

# 🔍 Quality checks (pre-commit)
check:
	@echo "🔍 Running quality checks..."
	@uv run ruff check .
	@uv run ruff format --check .

# 🛠️ Fix formatting and linting
fix:
	@echo "🛠️ Fixing code formatting..."
	@uv run ruff check --fix .
	@uv run ruff format .

# 📦 Build package
build:
	@echo "📦 Building package..."
	@uv run python -m build

# 📊 Test coverage report  
coverage:
	@echo "📊 Generating coverage report..."
	@uv run coverage run --source=container_manager manage.py test
	@uv run coverage report

# 🚀 Release commands
release-patch: _release-patch
release-minor: _release-minor  
release-major: _release-major

_release-patch:
	@$(MAKE) _release BUMP_TYPE=patch

_release-minor:
	@$(MAKE) _release BUMP_TYPE=minor

_release-major:
	@$(MAKE) _release BUMP_TYPE=major

_release:
	@echo "🚀 Creating $(BUMP_TYPE) release..."
	@$(MAKE) ready
	@$(eval CURRENT_VERSION := $(shell grep '__version__' container_manager/__init__.py | sed 's/.*"\(.*\)".*/\1/'))
	@$(eval NEW_VERSION := $(shell python3 -c "v='$(CURRENT_VERSION)'.split('.'); major, minor, patch = int(v[0]), int(v[1]), int(v[2]); print('$(CURRENT_VERSION)' if '$(BUMP_TYPE)'=='' else f'{major+1}.0.0' if '$(BUMP_TYPE)'=='major' else f'{major}.{minor+1}.0' if '$(BUMP_TYPE)'=='minor' else f'{major}.{minor}.{patch+1}')"))
	@echo "📝 Bumping version: $(CURRENT_VERSION) → $(NEW_VERSION)"
	@sed -i '' 's/__version__ = ".*"/__version__ = "$(NEW_VERSION)"/' container_manager/__init__.py
	@git add container_manager/__init__.py
	@git commit -m "Bump version to $(NEW_VERSION)

🚀 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
	@git tag v$(NEW_VERSION)
	@git push origin main
	@git push origin v$(NEW_VERSION)
	@gh release create v$(NEW_VERSION) --title "Django Container Manager v$(NEW_VERSION)" --generate-notes
	@echo "🎉 Release v$(NEW_VERSION) created successfully!"
	@echo "📦 PyPI publication will begin automatically via GitHub Actions"

# 🧹 Clean build artifacts
clean:
	@echo "🧹 Cleaning up..."
	@rm -rf dist/ build/ *.egg-info/
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -delete

# 📋 Show available commands
help:
	@echo "🚀 Django Container Manager - Vibe Coding Commands"
	@echo ""
	@echo "Development:"
	@echo "  make test          - Run test suite"
	@echo "  make check         - Quality checks (ruff)"
	@echo "  make fix           - Fix formatting/linting"
	@echo "  make coverage      - Test coverage report"
	@echo ""
	@echo "Build & Release:"
	@echo "  make build         - Build package"
	@echo "  make release-patch - Quick patch release (1.0.4 → 1.0.5)"
	@echo "  make release-minor - Minor release (1.0.4 → 1.1.0)"
	@echo "  make release-major - Major release (1.0.4 → 2.0.0)"
	@echo "  make clean         - Clean artifacts"
	@echo ""
	@echo "Shortcuts:"
	@echo "  make all           - check + test"
	@echo "  make ready         - fix + test (pre-commit)"
	@echo "  make help          - Show this help"

# 🎯 Claude-friendly shortcuts
ready: fix test
	@echo "✅ Code is ready to ship!"