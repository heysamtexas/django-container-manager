# Trusted Publishing Setup Guide

This document outlines the setup required for PyPI trusted publishing with this repository.

## 🔐 PyPI Project Configuration

After creating your PyPI project, configure the trusted publisher:

1. Go to https://pypi.org/manage/projects/
2. Find your project: `django-container-manager`
3. Click "Manage" → "Publishing" tab
4. Add GitHub Actions trusted publisher with these **exact values**:

```
Repository owner: heysamtexas
Repository name: django-container-manager
Workflow filename: .github/workflows/publish.yml
Environment name: pypi
```

## 🛡️ GitHub Environment Setup

Create a GitHub environment for additional security:

1. Go to repository Settings → Environments
2. Create new environment: `pypi`
3. Configure protection rules:
   - ✅ Required reviewers (add maintainers)
   - ✅ Restrict to `main` branch
   - ✅ Wait timer: 0 minutes (or desired delay)

## 🚀 Publishing Workflow

### Automatic Publishing
1. Create a new release on GitHub
2. Workflow automatically:
   - Builds package
   - Runs tests
   - Publishes to PyPI (after manual approval if configured)
   - Signs with Sigstore
   - Uploads artifacts to GitHub Release

### Manual Publishing
If needed, you can also publish manually:
```bash
# Create and push a new tag
git tag v1.0.1
git push origin v1.0.1
```

## 📋 Required Information for PyPI Setup

When configuring the trusted publisher on PyPI, use these exact values:
- **Repository owner:** `heysamtexas`
- **Repository name:** `django-container-manager`
- **Workflow filename:** `.github/workflows/publish.yml`
- **Environment name:** `pypi` (optional but recommended)

## ✅ Verification

After setup, the workflow will:
1. ✅ Build distributions automatically
2. ✅ Run full test suite
3. ✅ Require manual approval (if environment configured)
4. ✅ Publish to PyPI without API tokens
5. ✅ Create signed GitHub releases

## 🔒 Security Benefits

- **No long-lived API tokens** stored in repository secrets
- **Short-lived OIDC tokens** (15 minutes) from GitHub
- **Manual approval gates** via GitHub environments
- **Audit trail** of all publications tied to commits
- **Cryptographic signatures** via Sigstore