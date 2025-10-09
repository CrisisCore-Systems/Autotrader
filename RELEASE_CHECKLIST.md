# Release Checklist for AutoTrader

**Version**: Template  
**Release Manager**: _________________  
**Target Date**: _________________

---

## Pre-Release (1-2 weeks before)

### Code Quality

- [ ] All CI/CD pipelines passing
- [ ] No critical or high-severity security vulnerabilities
- [ ] Code coverage ≥ 80% (or documented exceptions)
- [ ] All linter warnings resolved
- [ ] Type checking passes (`mypy src/`)
- [ ] No deprecated API usage (check `--print-deprecation-warnings`)

### Testing

- [ ] Unit tests pass (`pytest tests/unit/`)
- [ ] Integration tests pass (`pytest tests/integration/`)
- [ ] Reproducibility test passes (synthetic dataset)
- [ ] Manual smoke test completed
- [ ] Performance regression test passed
- [ ] Backward compatibility verified (if applicable)

### Documentation

- [ ] CHANGELOG.md updated with all changes
- [ ] README.md reflects new features/changes
- [ ] API documentation generated (`pdoc src/`)
- [ ] Migration guide written (if breaking changes)
- [ ] Quick reference updated
- [ ] Examples updated for new features

### Dependencies

- [ ] Dependencies up to date (`pip list --outdated`)
- [ ] Security audit passed (`pip-audit` or `safety check`)
- [ ] Dependency locks updated (`requirements.txt`, `pyproject.toml`)
- [ ] Known CVEs documented with mitigation plan

### Versioning

- [ ] Version number follows semantic versioning
- [ ] Version updated in `pyproject.toml`
- [ ] Version updated in `src/__version__.py` (if exists)
- [ ] Schema version bumped (if output changes)
- [ ] Strategy API version bumped (if plugin interface changes)

---

## Release Day

### Final Checks

- [ ] All pre-release items completed
- [ ] Clean git working directory (`git status`)
- [ ] On correct branch (e.g., `main` or `release`)
- [ ] Latest changes pulled (`git pull`)
- [ ] No uncommitted changes

### Build & Tag

- [ ] Create git tag: `git tag -a v{VERSION} -m "Release v{VERSION}"`
- [ ] Push tag: `git push origin v{VERSION}`
- [ ] GitHub release created with notes
- [ ] Release assets uploaded (if applicable)

### Package

- [ ] Build distribution: `python -m build`
- [ ] Check package: `twine check dist/*`
- [ ] Upload to TestPyPI: `twine upload --repository testpypi dist/*`
- [ ] Test install from TestPyPI
- [ ] Upload to PyPI: `twine upload dist/*`
- [ ] Verify package on PyPI

### Documentation

- [ ] Documentation site updated (if applicable)
- [ ] Release notes published
- [ ] Blog post/announcement drafted (if major release)
- [ ] Social media posts prepared

---

## Post-Release (Within 24 hours)

### Verification

- [ ] Installation verified: `pip install autotrader=={VERSION}`
- [ ] Quick start guide works with new version
- [ ] Example notebooks run successfully
- [ ] Docker image updated (if applicable)
- [ ] Helm chart updated (if applicable)

### Communication

- [ ] Team notified via Slack/email
- [ ] Users notified (mailing list, forum, etc.)
- [ ] Documentation links shared
- [ ] Known issues communicated

### Monitoring

- [ ] Monitor error tracking (Sentry, etc.)
- [ ] Check download statistics
- [ ] Review user feedback/issues
- [ ] Set up alerts for critical metrics

---

## Post-Release (Within 1 week)

### Cleanup

- [ ] Close completed milestones
- [ ] Update project board
- [ ] Archive old release branches
- [ ] Clean up stale branches
- [ ] Update roadmap

### Retrospective

- [ ] Schedule release retrospective
- [ ] Document lessons learned
- [ ] Update release process (this checklist)
- [ ] Identify improvements for next release

---

## Version-Specific Checklists

### Major Release (X.0.0)

Additional items:

- [ ] Migration guide comprehensive
- [ ] Deprecation warnings in place (if applicable)
- [ ] Breaking changes clearly documented
- [ ] Support timeline for old version defined
- [ ] Users given advance notice (≥ 3 months)
- [ ] Enterprise customers notified directly

### Minor Release (x.Y.0)

Additional items:

- [ ] New features documented with examples
- [ ] Feature flags tested (if applicable)
- [ ] Backward compatibility verified
- [ ] Optional features clearly marked

### Patch Release (x.y.Z)

Additional items:

- [ ] Bug fixes documented
- [ ] Regression tests added
- [ ] Security patches applied
- [ ] Urgency level communicated (if security fix)

---

## Emergency Release (Hotfix)

For critical bugs or security issues:

### Fast-Track Process

- [ ] Severity confirmed (P0/P1)
- [ ] Minimal changes only (focused fix)
- [ ] Expedited review by senior engineer
- [ ] Smoke tests passed
- [ ] Tag created: `v{VERSION}-hotfix`
- [ ] Immediate deployment to production
- [ ] Incident report filed

### Communication (Urgent)

- [ ] Users notified immediately
- [ ] Security advisory published (if CVE)
- [ ] Workarounds provided
- [ ] Timeline for full fix communicated

---

## Tag Naming Convention

### Format

```
v{MAJOR}.{MINOR}.{PATCH}[-{PRE_RELEASE}][+{BUILD}]
```

### Examples

- Stable release: `v1.0.0`, `v2.1.3`
- Alpha: `v1.0.0-alpha.1`
- Beta: `v1.0.0-beta.2`
- Release candidate: `v1.0.0-rc.1`
- Hotfix: `v1.0.1-hotfix`
- Build metadata: `v1.0.0+20251008`

### Command

```bash
# Annotated tag (recommended)
git tag -a v1.0.0 -m "Release v1.0.0: Initial stable release"

# Push tag
git push origin v1.0.0

# List tags
git tag -l "v*"

# Delete tag (if needed)
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0
```

---

## CHANGELOG Discipline

### Format

Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New feature descriptions

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security fixes

## [1.0.0] - 2025-10-08

### Added
- Initial stable release
- Feature A
- Feature B

[Unreleased]: https://github.com/user/repo/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/user/repo/releases/tag/v1.0.0
```

### Categories

- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security fixes

### Best Practices

- [ ] One line per change
- [ ] Link to issues/PRs
- [ ] User-facing language (avoid jargon)
- [ ] Impact clearly stated
- [ ] Breaking changes highlighted
- [ ] Migration instructions linked

---

## Rollback Plan

In case of critical issues:

### Quick Rollback

1. **PyPI**: Cannot unpublish, but can yank release
   ```bash
   twine upload --skip-existing --repository pypi dist/*
   # Contact PyPI support to yank if needed
   ```

2. **Git**: Revert release and tag
   ```bash
   git revert {commit}
   git push origin main
   git tag -d v{VERSION}
   git push origin :refs/tags/v{VERSION}
   ```

3. **Communication**: Immediate user notification

### Recovery Steps

- [ ] Identify root cause
- [ ] Create hotfix branch
- [ ] Apply minimal fix
- [ ] Fast-track release process
- [ ] Deploy fixed version
- [ ] Post-mortem analysis

---

## Release Checklist Template

Copy this section for each release:

```markdown
## Release v{VERSION} - {DATE}

**Release Manager**: {NAME}
**Release Type**: [Major | Minor | Patch | Hotfix]

### Pre-Release
- [ ] Code quality checks passed
- [ ] All tests passing
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped

### Release
- [ ] Tag created and pushed
- [ ] GitHub release created
- [ ] Package built and uploaded
- [ ] Installation verified

### Post-Release
- [ ] Users notified
- [ ] Monitoring set up
- [ ] Feedback reviewed
- [ ] Retrospective scheduled

### Notes
{Any special notes or issues encountered}
```

---

## Automation Opportunities

Consider automating:

- [ ] Version bumping (e.g., `bump2version`)
- [ ] CHANGELOG generation (e.g., `git-changelog`)
- [ ] Package building (CI/CD)
- [ ] Release notes generation (GitHub Actions)
- [ ] Notification dispatch (Slack webhooks)
- [ ] Documentation deployment

---

## References

- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [PyPI Packaging](https://packaging.python.org/)
- [Release Engineering Best Practices](https://landing.google.com/sre/sre-book/chapters/release-engineering/)

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-10-08 | Initial checklist created | AutoTrader Team |

---

**Last Updated**: 2025-10-08  
**Version**: 1.0
