# Branch Protection Configuration

This document describes the recommended branch protection rules for the Autotrader repository.

## Main Branch

### Required Status Checks
Configure the following status checks to be required before merging:

#### From `ci.yml` workflow:
- `test (3.11)` - Core test suite on Python 3.11
- `test (3.12)` - Core test suite on Python 3.12
- `test (3.13)` - Core test suite on Python 3.13
- `lint` - Code quality checks
- `security` - Security scanning
- `quality-gate` - Overall quality gate

#### From `security-scan.yml` workflow:
- `semgrep` - Semgrep Security Scan
- `bandit` - Bandit Python Security
- `pip-audit` - Python Dependency Audit
- `trivy` - Trivy Security Scanner
- `gitleaks` - Gitleaks Secret Scanner
- `trufflehog` - TruffleHog Secret Scanner

### Recommended Settings

1. **Require pull request reviews before merging**
   - Required number of approving reviews: 1
   - Dismiss stale pull request approvals when new commits are pushed: ✅

2. **Require status checks to pass before merging**
   - Require branches to be up to date before merging: ✅
   - Status checks listed above must pass

3. **Require conversation resolution before merging**: ✅

4. **Require linear history**: ✅ (optional but recommended)

5. **Do not allow bypassing the above settings**: ✅
   - Include administrators: ✅

6. **Restrict who can push to matching branches**
   - Only allow merge commits from pull requests
   - Restrict pushes that create matching branches (optional)

### Settings via GitHub UI

Navigate to: **Repository Settings → Branches → Add branch protection rule**

```
Branch name pattern: main
```

#### Protection Rules:
- [x] Require a pull request before merging
  - [x] Require approvals: 1
  - [x] Dismiss stale pull request approvals when new commits are pushed
  - [x] Require review from Code Owners (if CODEOWNERS file exists)

- [x] Require status checks to pass before merging
  - [x] Require branches to be up to date before merging
  - Search and add required status checks:
    - `test (3.11)`
    - `test (3.12)`
    - `test (3.13)`
    - `lint`
    - `security`
    - `quality-gate`

- [x] Require conversation resolution before merging

- [x] Require linear history (optional)

- [x] Do not allow bypassing the above settings
  - [x] Include administrators

- [x] Restrict who can dismiss pull request reviews (optional)

## Develop Branch

The develop branch should have similar but slightly relaxed rules to allow for more rapid iteration while still maintaining quality standards.

### Required Status Checks
Configure the following status checks to be required before merging:

- `test (3.11)` - Core test suite on Python 3.11 (at minimum)
- `lint` - Code quality checks
- `security` - Security scanning

### Recommended Settings

1. **Require pull request reviews before merging**
   - Required number of approving reviews: 1

2. **Require status checks to pass before merging**
   - Require branches to be up to date before merging: ✅
   - Status checks: `test`, `lint`, `security`

3. **Require conversation resolution before merging**: ✅

4. **Do not allow bypassing the above settings**: ✅
   - Include administrators: ✅ (recommended)

## Feature Branches

Feature branches do not require branch protection rules, but should follow the standard workflow:

1. Branch from `develop`
2. Make changes
3. Run tests locally
4. Create PR to `develop`
5. Address review feedback
6. Merge when CI passes and approved

## Applying Branch Protection Rules

### Via GitHub Web Interface

1. Go to repository on GitHub
2. Click **Settings**
3. Click **Branches** in the left sidebar
4. Click **Add branch protection rule**
5. Configure as described above
6. Click **Create** or **Save changes**

### Via GitHub CLI

```bash
# Protect main branch
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["test (3.11)","test (3.12)","test (3.13)","lint","security","quality-gate"]}' \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field enforce_admins=true \
  --field required_linear_history=true \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

## Monitoring and Maintenance

### Reviewing Status Check History

1. Go to **Pull Requests** tab
2. Select a PR
3. Scroll to status checks section
4. Click **Show all checks** to see detailed results
5. Click on individual check names to view logs

### Updating Protection Rules

When adding new CI jobs:

1. Add the workflow to `.github/workflows/`
2. Test the workflow on a feature branch
3. Once stable, add the job name to branch protection rules
4. Update this document

### Troubleshooting

**Q: PR is blocked but all checks show as passed**
- Ensure the branch is up to date with base branch
- Check that all required status checks are listed

**Q: Cannot push to protected branch**
- Protected branches can only be updated via pull requests
- Create a feature branch and submit a PR

**Q: Administrator wants to bypass protection**
- Branch protection should apply to administrators
- If override is absolutely necessary, temporarily disable the rule
- Re-enable immediately after merge

## CI Skip for Documentation Changes

For documentation-only changes that don't require full CI:

Add `[skip ci]` to commit message:
```
git commit -m "docs: update README [skip ci]"
```

This will skip CI workflows but note that branch protection may still require manual approval.

## Best Practices

1. **Keep CI fast** - Target < 10 minutes for full pipeline
2. **Run tests locally** - Use pre-commit hooks before pushing
3. **Fix broken main quickly** - Treat main branch failures as P0 incidents
4. **Update branch protection** - When adding new critical CI jobs
5. **Review coverage trends** - Monitor coverage reports in PRs
6. **Security first** - Never bypass security scans

## Resources

- [GitHub Branch Protection Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Required Status Checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging)
- [Autotrader CI/CD Documentation](../docs/CI_GATING_SETUP.md)
