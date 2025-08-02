# Documentation Task: Contributing Guide Updates

**Priority:** Low-Medium
**Component:** Developer Documentation
**Estimated Effort:** Low
**Current Status:** Existing CONTRIBUTING.md may need updates

## Task Summary
Review and update CONTRIBUTING.md to ensure it reflects the current development workflow, documentation standards, and contribution requirements. Align contributor guidance with the project's mature development practices and documentation standards.

## Potential Updates Needed

### 1. Documentation Contribution Guidelines
Add specific guidance for documentation contributions:

```markdown
## Documentation Contributions

This project maintains comprehensive documentation for both users and developers:

### Documentation Types
- **User Documentation**: README.md, INSTALL.md, DOCKER.md, TROUBLESHOOTING.md
- **API Documentation**: API.md with complete model and method reference
- **Developer Documentation**: CLAUDE.md for internal development guidance
- **Code Documentation**: Inline docstrings and comments

### Documentation Standards
- **Technical writing style**: Direct, helpful, avoid marketing language
- **Code examples**: All examples must be tested and working
- **Cross-references**: Link between related documentation sections
- **User-focused**: Assume intelligent users, don't assume domain knowledge
- **Machine-readable**: Structure content for both human and AI readers

### Documentation Workflow
1. **Small changes**: Edit documentation directly, test examples
2. **New documentation**: Create task file in `tasks/` folder first
3. **Major restructuring**: Discuss in issue before starting work
4. **Code documentation**: Update docstrings with code changes

### Documentation Testing
- Test all code examples in clean environment
- Verify external links are functional
- Check cross-references for accuracy
- Validate installation instructions on multiple platforms
```

### 2. Development Workflow Updates
Ensure contributing guide reflects current practices:

```markdown
## Development Workflow

### Pre-Commit Requirements (MANDATORY)
Before any commit, run this exact sequence:
```bash
1. uv run python manage.py test          # ALL tests must pass
2. uv run ruff check .                   # Linting must pass  
3. uv run ruff format .                  # Code formatting
4. git add <files>                       # Stage changes
5. git commit -m "message"               # Only then commit
```

**No exceptions**: If any test fails, fix ALL failures before committing.

### Testing Requirements
- **Mandatory testing**: Every feature change must have passing tests
- **Test organization**: Use `tests/` module structure, never single `tests.py` files
- **Django testing focus**: Write tests for Django models, views, and business logic
- **Mock external services**: Don't require actual Docker/cloud credentials for basic tests
- **Coverage expectations**: Aim for ≥75% overall, ≥90% for new features

### Code Quality Standards
- **McCabe Complexity**: ≤8 per function (enforced by ruff C901)
- **Error handling**: Use `logger.exception()` for full tracebacks
- **Documentation**: Update docstrings with code changes
- **Performance**: Consider resource implications of changes
```

### 3. Issue and PR Guidelines
Update guidance for effective contributions:

```markdown
## Contributing Issues and Pull Requests

### Issue Reporting
Use the issue template provided in TROUBLESHOOTING.md for bug reports:
- Include system environment details
- Provide minimal reproduction steps
- Include complete error messages and logs
- Sanitize configuration of sensitive information

### Pull Request Process
1. **Create feature branch** from main branch
2. **Implement changes** following code quality standards
3. **Add/update tests** for all changes
4. **Update documentation** as needed
5. **Run pre-commit checklist** (tests, linting, formatting)
6. **Create pull request** with descriptive title and summary

### Pull Request Description Template
```
## Summary
- Brief description of changes made
- Why these changes were needed

## Changes Made
- Specific list of modifications
- New features or bug fixes
- Documentation updates

## Testing
- New tests added or existing tests updated
- All tests passing locally
- Manual testing performed

## Documentation
- Documentation updated to reflect changes
- Code examples tested and verified
```

### Code Review Guidelines
- **Focus on functionality**: Does the code work correctly?
- **Test coverage**: Are changes adequately tested?
- **Documentation**: Are changes properly documented?
- **Performance**: Consider resource and efficiency implications
- **Security**: Review for potential security issues
```

### 4. Development Environment Setup
Ensure setup instructions are current:

```markdown
## Development Environment Setup

### Prerequisites
- Python 3.8 or higher
- Docker (for container job testing)
- uv package manager (`pip install uv`)

### Setup Process
```bash
# Clone repository
git clone <repository-url>
cd django-docker

# Install dependencies
uv sync

# Setup database
uv run python manage.py migrate

# Create superuser (optional)
uv run python manage.py createsuperuser

# Run tests to verify setup
uv run python manage.py test

# Start development server
uv run python manage.py runserver
```

### Development Tools
- **Code formatting**: `uv run ruff format .`
- **Linting**: `uv run ruff check .` or `uv run ruff check --fix .`
- **Testing**: `uv run python manage.py test`
- **Django shell**: `uv run python manage.py shell`
```

### 5. Documentation Task System Integration
Reference the documentation task system:

```markdown
## Documentation Task System

This project uses a structured task system for documentation improvements:

### Task Files
Documentation tasks are tracked in `tasks/docs-*.md` files:
- `docs-readme-enhancement.md`: README improvements
- `docs-install-guide.md`: Installation documentation
- `docs-docker-integration.md`: Docker usage guide
- `docs-api-reference.md`: API documentation
- `docs-troubleshooting.md`: Problem resolution guide

### Working with Documentation Tasks
1. **Choose a task**: Review available tasks in `tasks/` folder
2. **Understand scope**: Read task success criteria and requirements
3. **Complete work**: Follow task specifications exactly
4. **Test thoroughly**: Verify all examples and instructions work
5. **Mark complete**: Update task status or create completion PR

### Creating New Documentation Tasks
When identifying documentation gaps:
1. Create task file in `tasks/` folder following existing format
2. Define clear scope, success criteria, and file locations
3. Include content structure and style guidelines
4. Reference related documentation and technical sources
```

### 6. Community Guidelines
Add or update community standards:

```markdown
## Community Guidelines

### Communication Standards
- **Be direct and helpful**: Focus on practical solutions
- **Assume good intentions**: Contributors want to improve the project
- **Provide context**: Explain the reasoning behind suggestions
- **Share knowledge**: Help others learn from discussions

### Code of Conduct
- Respectful and inclusive communication
- Focus on technical merit and project improvement
- Constructive feedback and collaborative problem-solving
- Recognition that all contributors are volunteers

### Getting Help
- **Documentation first**: Check existing documentation
- **Search issues**: Look for similar problems or questions
- **Ask specific questions**: Provide context and details
- **Contribute back**: Share solutions with the community
```

## LLM Agent Guidelines

### Behavioral Constraints
- **DO**: Follow existing CONTRIBUTING.md structure and tone
- **DO**: Integrate documentation standards with existing code quality requirements
- **DO**: Test all documented procedures before including them
- **DO**: Maintain consistency with project's development philosophy
- **DO NOT**: Remove or override existing contribution guidelines
- **DO NOT**: Add requirements that conflict with current development workflow
- **DO NOT**: Include documentation standards that can't be enforced
- **DO NOT**: Create barriers that discourage community contributions
- **LIMITS**: Additions only, no removal of existing contributor guidance

### Security Requirements
- **Process integrity**: Ensure documentation changes don't bypass code review
- **Quality gates**: Document validation steps that maintain code quality
- **Access control**: Don't document processes that could compromise security
- **Contribution safety**: Ensure contributor guidelines promote secure development

### Safe Operation Patterns
- **Contributing guide enhancement**:
  1. Read existing CONTRIBUTING.md thoroughly
  2. Identify gaps in documentation guidance
  3. Add documentation standards that align with code standards
  4. Test all documented procedures with actual contribution workflow
  5. Ensure new requirements don't burden contributors unnecessarily
- **Integration approach**:
  1. Build on existing code quality foundations
  2. Align documentation requirements with testing requirements
  3. Create clear, actionable documentation standards
  4. Provide examples and templates where helpful

### Error Handling
- **If existing process conflicts**: Adapt new standards to fit existing workflow
- **If requirements too complex**: Simplify or provide clear guidance
- **If enforcement unclear**: Document specific validation steps
- **If contributor burden too high**: Reduce requirements to essential standards

### Validation Requirements
- [ ] All documented procedures tested with actual contribution workflow
- [ ] Documentation standards align with existing code quality requirements
- [ ] No conflicts with existing contribution guidelines
- [ ] Clear examples provided for documentation expectations
- [ ] Validation steps are practical and enforceable
- [ ] AI agent guidelines don't restrict human contributor flexibility
- [ ] Review process integrates smoothly with existing code review

### Contributing Documentation Safety Boundaries
- **NEVER remove**: Existing contributor rights or processes
- **NEVER create**: Barriers that discourage community participation
- **NEVER require**: Documentation standards that can't be reasonably enforced
- **NEVER conflict**: With existing code quality or testing requirements
- **NEVER impose**: Overly complex documentation requirements on contributors
- **NEVER ignore**: The need for practical, actionable guidance
- **NEVER separate**: Documentation quality from code quality standards

## Success Criteria
- [ ] CONTRIBUTING.md reflects current development practices
- [ ] Documentation contribution guidelines comprehensive
- [ ] Pre-commit workflow clearly documented
- [ ] Testing requirements align with CLAUDE.md standards
- [ ] Issue and PR templates updated
- [ ] Development environment setup current and tested
- [ ] Documentation task system integrated
- [ ] Community guidelines promote effective collaboration

## File Location
- **Review and Edit**: `/Users/samtexas/src/playground/django-docker/CONTRIBUTING.md`
- **Reference**: CLAUDE.md for technical accuracy
- **Cross-reference**: All documentation task files for consistency

## Review Process
1. **Read existing CONTRIBUTING.md** to understand current content
2. **Compare with CLAUDE.md** to identify gaps or inconsistencies  
3. **Review documentation task files** for contribution patterns
4. **Check GitHub templates** (if they exist) for alignment
5. **Update content** to reflect current practices
6. **Test setup instructions** to ensure they work

## Style Guidelines
- **Actionable guidance**: Provide specific steps and requirements
- **Examples included**: Show rather than just tell
- **Progressive complexity**: Start with basics, build to advanced topics
- **Cross-references**: Link to related documentation
- **Consistent formatting**: Match project documentation style
- **Testing emphasis**: Reinforce testing requirements throughout

## Definition of Done
- [ ] CONTRIBUTING.md updated with current development practices
- [ ] Documentation contribution guidelines added
- [ ] Pre-commit workflow accurately documented
- [ ] Testing requirements clearly stated
- [ ] Issue and PR guidance comprehensive
- [ ] Development setup instructions tested
- [ ] Documentation task system integrated
- [ ] Aligns with project's technical writing standards