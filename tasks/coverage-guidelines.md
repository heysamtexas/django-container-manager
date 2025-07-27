# Code Coverage: Guidelines & Team Practices

## Executive Summary

**Purpose:** Establish team standards, practices, and maintenance procedures for sustainable code coverage
**Scope:** Team adoption, coverage quality standards, maintenance workflows, and long-term sustainability
**Goal:** Create a coverage culture that enhances code quality without becoming a burden

## Coverage Philosophy & Standards

### Coverage Targets & Rationale

#### Tiered Coverage Requirements
```
┌─────────────────────────────────────────────────────────────┐
│ COVERAGE TARGET HIERARCHY                                   │
├─────────────────────────────────────────────────────────────┤
│ New Features:        ≥90%  (strictest - greenfield code)   │
│ Core Executors:      ≥85%  (business-critical logic)       │
│ Management Commands: ≥80%  (user-facing interfaces)        │
│ Overall Codebase:    ≥75%  (balanced target)               │
│ Service Layer:       ≥70%  (includes Django admin overhead)│
│ Configuration:       ≥60%  (mostly constants and settings) │
└─────────────────────────────────────────────────────────────┘
```

#### Coverage Quality Over Quantity
**Principle:** Focus on meaningful coverage, not just percentage points

**High-Value Coverage:**
- ✅ **Business logic paths** - Core functionality and decision points
- ✅ **Error handling** - Exception scenarios and edge cases  
- ✅ **Integration points** - Service boundaries and data flow
- ✅ **User interfaces** - Management commands and API endpoints
- ✅ **State transitions** - Job lifecycle and status changes

**Low-Value Coverage (Avoid):**
- ❌ **Django admin UI** - Framework code with low business value
- ❌ **Simple getters/setters** - Trivial property access
- ❌ **Configuration files** - Static constants and settings
- ❌ **Migration files** - Auto-generated Django migrations
- ❌ **Import statements** - Module loading code

### Coverage-Driven Development Workflow

#### For New Features
```bash
# 1. Write failing test first (TDD approach)
uv run python manage.py test new_feature --keepdb

# 2. Implement minimal code to pass test
# (implement feature)

# 3. Check coverage for new code
uv run coverage run --source='.' manage.py test new_feature
uv run coverage report --show-missing

# 4. Add tests until ≥90% coverage achieved
# (add edge cases, error scenarios)

# 5. Refactor with coverage protection
# (refactor knowing tests will catch issues)
```

#### For Bug Fixes
```bash
# 1. Write test reproducing the bug
uv run python manage.py test --keepdb -k test_bug_reproduction

# 2. Verify test fails (confirms bug exists)
# 3. Fix the bug
# 4. Verify test passes (confirms fix works)
# 5. Check coverage improvement
uv run coverage run --source='.' manage.py test
uv run coverage report --show-missing
```

#### For Refactoring
```bash
# 1. Establish baseline coverage
uv run coverage run --source='.' manage.py test
uv run coverage report > coverage_before.txt

# 2. Perform refactoring
# (make changes)

# 3. Verify coverage maintained or improved
uv run coverage run --source='.' manage.py test
uv run coverage report > coverage_after.txt
diff coverage_before.txt coverage_after.txt

# 4. Add tests if coverage decreased
```

## Team Practices & Standards

### Code Review Coverage Guidelines

#### Pre-Review Checklist (Author)
- [ ] All tests pass: `uv run python manage.py test`
- [ ] Coverage check passes: `uv run coverage report --fail-under=75`
- [ ] New/modified code has ≥90% coverage
- [ ] Tests include error scenarios and edge cases
- [ ] Tests are meaningful, not just coverage padding

#### Review Guidelines (Reviewer)
**Coverage Quality Assessment:**
- ✅ **Do tests verify behavior?** Not just code execution
- ✅ **Are error paths tested?** Exception handling and edge cases
- ✅ **Are tests maintainable?** Clear, focused, and well-structured
- ✅ **Do tests use appropriate mocks?** External dependencies isolated
- ✅ **Is test data realistic?** Representative of production scenarios

**Coverage Red Flags:**
- ❌ **Tests that only call functions** without asserting outcomes
- ❌ **Overly complex mocks** that obscure actual behavior
- ❌ **Tests that test implementation** instead of behavior
- ❌ **Coverage achieved through trivial tests** (property access, etc.)
- ❌ **Missing error scenario coverage** for critical paths

#### Coverage Review Template
```markdown
## Coverage Review Checklist

### Quantitative
- [ ] Overall coverage target met (≥75%)
- [ ] New/modified files meet target (≥90%)
- [ ] No significant coverage regression

### Qualitative
- [ ] Tests verify expected behavior
- [ ] Error scenarios appropriately tested
- [ ] Mocks are realistic and minimal
- [ ] Tests are maintainable and clear
- [ ] Coverage is meaningful, not artificial

### Comments
<!-- Specific feedback on coverage quality -->
```

### Testing Standards & Best Practices

#### Test Organization Standards
```python
# ✅ GOOD: Clear, focused test class organization
class ContainerExecutorTest(TestCase):
    """Test container execution functionality."""
    
    def setUp(self):
        # Minimal, focused setup
        self.executor = ContainerExecutor()
        self.mock_docker = Mock()
        
    def test_submit_job_creates_container_correctly(self):
        # Test one specific behavior
        job = self.create_test_job()
        
        container_id = self.executor.submit_job(job)
        
        # Clear assertions about expected behavior
        self.assertIsInstance(container_id, str)
        self.mock_docker.containers.create.assert_called_once()
        
    def test_submit_job_handles_docker_errors_gracefully(self):
        # Test error scenario explicitly
        self.mock_docker.containers.create.side_effect = DockerException("Connection failed")
        
        with self.assertRaises(ExecutorError):
            self.executor.submit_job(self.create_test_job())
```

#### Mock Strategy Guidelines
```python
# ✅ GOOD: Mock external dependencies at service boundaries
@patch('container_manager.executors.docker.docker.from_env')
class DockerExecutorTest(TestCase):
    def setUp(self):
        self.mock_docker_client = Mock()
        
    def test_with_realistic_mock_behavior(self):
        # Mock returns realistic responses
        mock_container = Mock()
        mock_container.id = 'container-123'
        mock_container.status = 'running'
        self.mock_docker_client.containers.create.return_value = mock_container
        
        # Test behavior with realistic mock
        
# ❌ BAD: Over-mocking internal implementation details
@patch('container_manager.executors.docker.DockerExecutor._validate_config')
@patch('container_manager.executors.docker.DockerExecutor._prepare_environment')
@patch('container_manager.executors.docker.DockerExecutor._create_container_spec')
class OverMockedTest(TestCase):
    # Too much mocking makes tests brittle and meaningless
```

#### Test Data Management
```python
# ✅ GOOD: Realistic, focused test data
class TestDataMixin:
    def create_test_job(self, **overrides):
        """Create realistic test job with optional overrides."""
        defaults = {
            'template': self.create_test_template(),
            'name': 'test-job',
            'command': ['python', 'script.py'],
            'environment': {'ENV': 'test'},
            'resource_limits': {'memory': '1G', 'cpu': '1'},
        }
        defaults.update(overrides)
        return ContainerJob.objects.create(**defaults)
        
    def create_test_template(self):
        """Create minimal but valid template."""
        return JobTemplate.objects.create(
            name='test-template',
            image='python:3.11',
            default_command=['python'],
        )

# ❌ BAD: Overly complex or unrealistic test data
def create_massive_test_scenario():
    # Creates dozens of related objects
    # Hard to understand what's being tested
    # Slow to run and maintain
```

### Coverage Maintenance Workflows

#### Weekly Coverage Review Process
**Schedule:** Every Monday morning
**Duration:** 30 minutes
**Participants:** Development team

**Agenda:**
1. **Review coverage trends** (using coverage history)
2. **Identify priority areas** for improvement
3. **Discuss coverage quality** issues from recent PRs
4. **Plan coverage improvements** for the sprint
5. **Update coverage targets** if needed

**Deliverables:**
- Weekly coverage report
- Priority list for coverage improvements
- Coverage quality improvement tasks

#### Monthly Coverage Health Check
**Schedule:** First Friday of each month
**Duration:** 1 hour
**Participants:** Development team + tech lead

**Activities:**
1. **Deep dive analysis** of coverage gaps
2. **Review testing infrastructure** and tooling
3. **Assess coverage process** effectiveness
4. **Plan major coverage initiatives**
5. **Update coverage guidelines** if needed

#### Quarterly Coverage Assessment
**Schedule:** End of each quarter
**Duration:** 2 hours
**Participants:** Full engineering team

**Focus Areas:**
1. **Coverage ROI analysis** - which coverage investments paid off?
2. **Process improvement** - what slowed us down or helped?
3. **Tool evaluation** - are our coverage tools effective?
4. **Standard updates** - do our guidelines need adjustment?
5. **Training needs** - where does the team need support?

### Coverage Metrics & Monitoring

#### Key Performance Indicators (KPIs)
```
┌─────────────────────────────────────────────────────────────┐
│ COVERAGE HEALTH DASHBOARD                                   │
├─────────────────────────────────────────────────────────────┤
│ Overall Coverage:     📊 [████████░░] 75.2% ▲              │
│ Coverage Trend:       📈 +2.1% this month                  │
│ Regression Incidents: 🚨 0 this week                       │
│ New Code Coverage:    ✅ 91.3% average (target: ≥90%)     │
│ Test Suite Runtime:   ⏱️  42s (target: <60s)               │
│ Coverage Debt:        📋 23 files below target             │
└─────────────────────────────────────────────────────────────┘
```

#### Tracking Mechanisms
**Daily:** Automated coverage measurement in CI/CD
**Weekly:** Coverage trend analysis and reporting
**Monthly:** Coverage quality assessment and planning
**Quarterly:** Process and tooling evaluation

#### Alert Thresholds
- 🚨 **Critical:** Overall coverage drops below 70%
- ⚠️ **Warning:** Coverage drops >2% in single commit
- 📢 **Info:** New code coverage below 85%
- 📊 **Report:** Weekly coverage summary

### Coverage Debt Management

#### Identifying Coverage Debt
**Coverage Debt:** Files/functions below target coverage that should be prioritized for improvement

**Prioritization Matrix:**
```
High Impact + Low Effort = 🎯 Quick Wins (do first)
High Impact + High Effort = 🏗️ Major Projects (plan carefully)
Low Impact + Low Effort = 🧹 Clean Up (fill time)
Low Impact + High Effort = ❌ Avoid (unless strategic)
```

#### Coverage Debt Workflow
1. **Identify debt** using automated analysis
2. **Prioritize by impact** (business value + risk)
3. **Estimate effort** (complexity + dependencies)
4. **Plan improvements** in sprint cycles
5. **Track progress** against debt reduction goals

#### Technical Debt Integration
- Include coverage debt in technical debt discussions
- Allocate 20% of sprint capacity to coverage improvements
- Balance feature development with coverage improvement
- Treat coverage regression as bugs (fix immediately)

## Quality Assurance & Continuous Improvement

### Coverage Quality Metrics
**Beyond percentage coverage:**
- **Test maintainability score** - How easy are tests to modify?
- **Error scenario coverage** - Are failure paths tested?
- **Mock realism score** - How realistic are our mocks?
- **Test clarity rating** - Are tests self-documenting?
- **Coverage stability** - Does coverage stay consistent?

### Common Coverage Anti-Patterns

#### Anti-Pattern 1: Coverage Farming
**Problem:** Writing tests solely to increase coverage percentage
```python
# ❌ BAD: Test that adds coverage but no value
def test_property_access(self):
    job = ContainerJob()
    job.name = "test"
    self.assertEqual(job.name, "test")  # Tests trivial property
```

**Solution:** Focus on behavior testing
```python
# ✅ GOOD: Test that verifies meaningful behavior
def test_job_execution_updates_status_correctly(self):
    job = self.create_pending_job()
    
    executor.start_job(job)
    
    job.refresh_from_db()
    self.assertEqual(job.status, 'running')
    self.assertIsNotNone(job.started_at)
```

#### Anti-Pattern 2: Over-Mocking
**Problem:** Mocking so much that tests don't verify real behavior
```python
# ❌ BAD: Mocks everything, tests nothing meaningful
@patch('os.path.exists')
@patch('subprocess.run')
@patch('logging.Logger.info')
@patch('time.sleep')
def test_overmocked_function(self, mock_sleep, mock_log, mock_subprocess, mock_exists):
    # Test becomes meaningless
```

**Solution:** Mock only external boundaries
```python
# ✅ GOOD: Mock external dependencies, test real logic
@patch('docker.from_env')
def test_with_minimal_mocking(self, mock_docker):
    # Only mock external Docker API
    # Test all internal logic
```

#### Anti-Pattern 3: Implementation Testing
**Problem:** Tests that break when implementation changes
```python
# ❌ BAD: Tests internal implementation details
def test_internal_method_called(self):
    executor = ContainerExecutor()
    with patch.object(executor, '_internal_helper') as mock_helper:
        executor.submit_job(job)
        mock_helper.assert_called_once()  # Brittle!
```

**Solution:** Test public behavior
```python
# ✅ GOOD: Tests public interface and outcomes
def test_job_submission_creates_container(self):
    executor = ContainerExecutor()
    
    container_id = executor.submit_job(job)
    
    self.assertIsInstance(container_id, str)
    # Verify container was actually created
    self.assertTrue(executor.get_container_status(container_id))
```

### Training & Knowledge Sharing

#### Onboarding Coverage Training
**New Team Members:**
- Coverage philosophy and goals
- Tool usage and workflow
- Common patterns and anti-patterns
- Code review coverage guidelines

#### Regular Training Topics
- **Monthly:** Coverage tool updates and new features
- **Quarterly:** Testing best practices and patterns
- **Annually:** Coverage strategy review and planning

#### Knowledge Sharing Mechanisms
- **Documentation:** Keep coverage guidelines up-to-date
- **Code reviews:** Share knowledge through review feedback
- **Tech talks:** Present coverage improvements and learnings
- **Pair programming:** Share testing approaches hands-on

## Success Metrics & Evaluation

### Short-Term Goals (3 months)
- ✅ **Achieve 75% overall coverage** from current 55%
- ✅ **Zero coverage regressions** in production deployments
- ✅ **90% new code coverage** compliance rate
- ✅ **Coverage infrastructure** fully operational

### Medium-Term Goals (6 months)
- ✅ **80% overall coverage** with focus on critical paths
- ✅ **Coverage-driven development** adopted by all team members
- ✅ **Automated coverage quality** assessment in place
- ✅ **Coverage debt reduction** by 50%

### Long-Term Goals (12 months)
- ✅ **85% overall coverage** with high-quality tests
- ✅ **Coverage culture** embedded in development process
- ✅ **Minimal coverage maintenance** overhead
- ✅ **Coverage as competitive advantage** for code quality

### Evaluation Criteria
**Quantitative:**
- Coverage percentage trends
- Regression frequency
- Test suite performance
- Coverage debt metrics

**Qualitative:**
- Developer satisfaction with coverage process
- Code review quality improvements
- Bug detection rate improvements
- Development velocity impact

## Timeline & Implementation

### Phase 1: Foundation (Month 1)
- Establish coverage guidelines and standards
- Set up team practices and review processes
- Implement basic coverage debt tracking
- Train team on coverage philosophy

### Phase 2: Process Integration (Month 2)
- Integrate coverage into code review process
- Establish coverage maintenance workflows
- Implement quality metrics tracking
- Begin systematic coverage improvement

### Phase 3: Culture & Optimization (Month 3+)
- Refine processes based on team feedback
- Optimize tooling and automation
- Focus on coverage quality improvements
- Establish long-term sustainability practices

This comprehensive approach ensures that code coverage becomes a valuable development tool rather than a burdensome requirement, supporting long-term code quality and team productivity.