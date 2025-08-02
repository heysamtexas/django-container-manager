# Documentation Task: Troubleshooting Guide Creation

**Priority:** High
**Component:** User Support Documentation
**Estimated Effort:** Medium
**Current Status:** Missing - No troubleshooting documentation exists

## Task Summary
Create comprehensive TROUBLESHOOTING.md to address common issues users will encounter. Based on the system's complexity (Docker integration, multiple executors, resource management), users will need systematic guidance for diagnosing and resolving problems.

## Critical Need Analysis
This system integrates multiple complex components (Django, Docker, container orchestration, resource monitoring) where failures can occur at many levels. Users need structured troubleshooting guidance to:
- Diagnose system vs. configuration vs. environmental issues
- Understand error messages and their implications
- Resolve problems without deep system knowledge
- Escalate issues appropriately when needed

## Specific Content Required

### 1. Troubleshooting Framework
- **Problem classification**: System, configuration, Docker, resource, network issues
- **Diagnostic approach**: Systematic problem isolation methodology
- **Information gathering**: What to collect before seeking help
- **Escalation paths**: When to file issues vs. when to investigate further

### 2. Installation and Setup Issues

#### Docker Configuration Problems
- **Permission denied accessing Docker socket**:
  ```bash
  # Error: permission denied while trying to connect to Docker daemon
  # Solution: Add user to docker group
  sudo usermod -aG docker $USER
  newgrp docker
  # Verify fix
  docker ps
  ```
- **Docker daemon not running**:
  - Symptoms: Connection refused errors
  - Diagnosis: `docker version` command failure
  - Solutions: Start Docker service, check Docker Desktop

#### Database Connection Issues
- **Database connection failures**:
  - Connection string format errors
  - Authentication failures
  - Network connectivity issues
  - Migration conflicts
- **Migration problems**:
  - Conflicting migrations
  - Database schema inconsistencies
  - Permission issues with database files

#### Python Environment Issues
- **uv sync failures**:
  - Dependency conflicts
  - Network connectivity during package installation
  - Virtual environment corruption
- **Import errors**:
  - PYTHONPATH configuration
  - Missing dependencies
  - Version compatibility issues

### 3. Job Execution Problems

#### Container Launch Failures
- **Image pull failures**:
  ```bash
  # Error: pull access denied for image
  # Diagnosis steps:
  docker pull <image-name>  # Test direct pull
  docker login               # Check authentication
  # Solutions: Authentication, image name verification, registry access
  ```
- **Container startup failures**:
  - Invalid command syntax
  - Missing base image dependencies
  - Resource limit violations
  - Network configuration issues

#### Job Status Issues
- **Jobs stuck in pending status**:
  - Executor host availability
  - Resource allocation failures
  - Queue processing problems
- **Jobs failing immediately**:
  - Command execution errors
  - Environment variable issues
  - Working directory problems
  - Permission issues inside containers

#### Resource Management Problems
- **Memory limit exceeded**:
  ```python
  # Error: Container killed due to memory limit
  # Diagnosis: Check job.memory_limit vs actual usage
  # Solutions: Increase limit or optimize container memory usage
  job = ContainerJob.objects.get(id=job_id)
  print(f"Memory limit: {job.memory_limit}MB")
  print(f"Peak usage: {job.peak_memory_usage}MB")
  ```
- **CPU throttling issues**:
  - CPU limit configuration
  - Host CPU availability
  - CPU-intensive workload optimization

### 4. Executor-Specific Issues

#### Docker Executor Problems
- **Docker daemon connectivity**:
  - Unix socket permission issues
  - TCP connection configuration
  - TLS certificate problems
- **Container networking**:
  - Port binding conflicts
  - Network isolation issues
  - DNS resolution problems
- **Volume mounting failures**:
  - File permission issues
  - Path existence verification
  - SELinux/AppArmor restrictions

#### Cloud Run Executor Issues
- **Authentication failures**:
  - Service account configuration
  - Permission scope issues
  - Credential file location
- **Deployment failures**:
  - Image registry access
  - Resource allocation limits
  - Region availability issues
- **Execution timeouts**:
  - Cloud Run timeout limits
  - Network connectivity issues
  - Cold start performance

### 5. Environment Variable Issues
- **Template parsing errors**:
  ```bash
  # Error: Invalid environment variable format
  # Common issues:
  KEY=value                    # ✓ Correct
  KEY = value                  # ✗ Spaces around equals
  KEY="value with spaces"      # ✓ Correct
  KEY='single quotes'          # ✓ Correct
  MULTILINE_KEY=line1\nline2   # ✗ Newlines need proper escaping
  ```
- **Variable interpolation problems**:
  - Circular reference detection
  - Missing variable definitions
  - Type conversion issues
- **Secure variable handling**:
  - Secrets appearing in logs
  - Environment variable exposure
  - Access permission issues

### 6. Logging and Monitoring Issues

#### Log Collection Problems
- **Missing container logs**:
  - Docker logging driver configuration
  - Log retention policy issues
  - Container termination timing
- **Log parsing failures**:
  - Character encoding issues
  - Log format inconsistencies
  - Large log file handling

#### Health Check Failures
- **Executor host health checks**:
  - Network connectivity verification
  - Service availability testing
  - Resource capacity checking
- **Job monitoring issues**:
  - Status update delays
  - Metric collection failures
  - Alert notification problems

### 7. Performance Issues

#### Slow Job Execution
- **Image pull optimization**:
  - Registry proximity and caching
  - Image layer optimization
  - Parallel pull configuration
- **Container startup delays**:
  - Base image optimization
  - Init process configuration
  - Resource allocation tuning

#### Resource Contention
- **Host resource exhaustion**:
  - Memory overcommitment
  - CPU scheduling issues
  - Disk I/O bottlenecks
- **Database performance**:
  - Query optimization
  - Index usage analysis
  - Connection pool tuning

### 8. Security and Permissions

#### Container Security Issues
- **User namespace problems**:
  - UID/GID mapping issues
  - File permission conflicts
  - Security context configuration
- **Network security**:
  - Container isolation verification
  - Port exposure concerns
  - Network policy enforcement

#### Access Control Problems
- **Django admin access**:
  - User authentication issues
  - Permission group configuration
  - Session management problems
- **API access control**:
  - Authentication token issues
  - Permission verification
  - Rate limiting problems

### 9. Diagnostic Commands and Tools

#### System Information Collection
```bash
# Collect system information for troubleshooting
echo "=== System Information ==="
uname -a
docker --version
python --version

echo "=== Docker Status ==="
docker info
docker ps -a

echo "=== Django Status ==="
cd /path/to/project
uv run python manage.py check
uv run python manage.py showmigrations

echo "=== Database Status ==="
uv run python manage.py dbshell --command=".tables"  # SQLite
# or for PostgreSQL:
# uv run python manage.py dbshell --command="\dt"

echo "=== Job Status ==="
uv run python manage.py shell -c "
from container_manager.models import ContainerJob, ExecutorHost
print('Active Jobs:', ContainerJob.objects.active().count())
print('Available Hosts:', ExecutorHost.objects.available().count())
"
```

#### Log Analysis Tools
```bash
# Container log analysis
docker logs <container-id> --tail=100 --follow

# Django application logs
tail -f /path/to/logs/django.log

# System resource monitoring
top -p $(pgrep -d, docker)
df -h  # Disk usage
free -h  # Memory usage
```

### 10. Getting Help and Reporting Issues

#### Information to Collect
- **System environment**: OS, Docker version, Python version
- **Error messages**: Complete error text and stack traces
- **Configuration**: Relevant model configurations (sanitized)
- **Reproduction steps**: Minimal example that demonstrates the issue
- **Logs**: Relevant log excerpts with timestamps

#### Issue Reporting Template
```markdown
## Problem Description
[Clear description of what's not working]

## Environment
- OS: [Operating System and version]
- Docker: [Docker version]
- Python: [Python version]
- Project: [Git commit hash or version]

## Steps to Reproduce
1. [First step]
2. [Second step]
3. [Third step]

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Error Messages
```
[Complete error text]
```

## Configuration
[Relevant model configurations, sanitized of secrets]

## Logs
[Relevant log excerpts with timestamps]
```

## LLM Agent Guidelines

### Behavioral Constraints
- **DO**: Follow diagnostic procedures step-by-step without skipping steps
- **DO**: Document all findings and attempted solutions
- **DO**: Stop troubleshooting when safety boundaries are approached
- **DO**: Verify system state before and after troubleshooting actions
- **DO NOT**: Modify production data during troubleshooting
- **DO NOT**: Restart services without understanding impact
- **DO NOT**: Delete logs or system files during diagnostics
- **DO NOT**: Continue troubleshooting if system stability is at risk
- **LIMITS**: Maximum 30 minutes per troubleshooting session before escalation

### Security Requirements
- **Access control**: Only use read-only operations for diagnostics unless explicitly authorized
- **Data protection**: Never expose sensitive information in troubleshooting logs
- **System integrity**: Avoid operations that could compromise system security
- **Privilege boundaries**: Do not escalate privileges beyond necessary scope
- **Evidence preservation**: Maintain audit trail of all troubleshooting actions

### Safe Operation Patterns
- **Diagnostic workflow**:
  1. Identify and document the problem symptoms
  2. Check system health and resource availability
  3. Review recent logs for error patterns
  4. Verify configuration settings are correct
  5. Test connectivity and permissions
  6. Apply minimal, reversible fixes first
- **Recovery procedures**:
  1. Create backups before making changes
  2. Test fixes in non-production environment first
  3. Document all changes made during troubleshooting
  4. Verify fix resolves issue without side effects
  5. Monitor system stability after applying fixes

### Error Handling
- **If diagnostic commands fail**: Document failure, try alternative approaches, escalate if needed
- **If system becomes unstable**: Stop troubleshooting, revert changes, escalate immediately
- **If data corruption suspected**: Stop all operations, preserve evidence, escalate to data recovery
- **If security breach indicated**: Follow security incident procedures, do not continue troubleshooting
- **If unclear on procedure**: Request guidance rather than guessing

### Validation Requirements
- [ ] All diagnostic commands are read-only or have minimal system impact
- [ ] Troubleshooting procedures tested in safe environments
- [ ] No sensitive information exposed in diagnostic outputs
- [ ] Clear escalation criteria defined for each problem category
- [ ] Recovery procedures include rollback steps
- [ ] Documentation includes expected diagnostic outputs
- [ ] Safety boundaries clearly marked for dangerous operations

### Troubleshooting Safety Boundaries
- **NEVER delete**: System logs, database files, or configuration without explicit authorization
- **NEVER modify**: Production database data during troubleshooting
- **NEVER restart**: Critical services without understanding dependencies and impact
- **NEVER bypass**: Security controls or authentication mechanisms
- **NEVER ignore**: System stability warnings or resource exhaustion alerts
- **NEVER continue**: If troubleshooting actions could cause data loss
- **NEVER escalate**: Privileges beyond minimum required for diagnostics

## Success Criteria
- [ ] Covers 90% of common installation and setup issues
- [ ] Addresses Docker-specific problems comprehensively
- [ ] Includes working diagnostic commands and scripts
- [ ] Provides systematic troubleshooting methodology
- [ ] Contains practical solutions, not just problem identification
- [ ] Includes escalation guidance for complex issues
- [ ] Templates for effective issue reporting
- [ ] Cross-references other documentation appropriately

## File Location
- **Create**: `/Users/samtexas/src/playground/django-docker/TROUBLESHOOTING.md`
- **Reference**: CLAUDE.md for technical commands and procedures
- **Link from**: README.md, INSTALL.md, DOCKER.md, API.md

## Content Structure
```markdown
# Troubleshooting Guide

## Quick Start Troubleshooting
[Most common issues and immediate solutions]

## Installation Issues
[Setup and configuration problems]

## Job Execution Problems
[Container and execution issues]

## Executor-Specific Issues
[Docker, Cloud Run, and other executor problems]

## Environment and Configuration
[Environment variable and settings issues]

## Performance Issues
[Slow execution and resource problems]

## Security and Permissions
[Access control and security issues]

## Diagnostic Tools
[Commands and scripts for problem diagnosis]

## Getting Help
[How to report issues and seek assistance]

## FAQ
[Frequently asked questions and answers]
```

## Style Guidelines
- **Problem-solution format**: Clear problem statement followed by solution
- **Step-by-step solutions**: Numbered procedures for complex fixes
- **Command examples**: Copy-pasteable commands with expected output
- **Visual hierarchy**: Use headers, bullets, and code blocks effectively
- **Cross-platform awareness**: Note OS-specific differences
- **Safety first**: Warn about potentially destructive operations
- **Link to external resources**: Official documentation and community resources

## Definition of Done
- [ ] TROUBLESHOOTING.md addresses major system failure modes
- [ ] All diagnostic commands tested and verified
- [ ] Solutions provided for identified problems
- [ ] Escalation paths clearly defined
- [ ] Issue reporting template comprehensive
- [ ] Cross-references to other documentation included
- [ ] Serves as primary support resource for users