# Code Coverage: Infrastructure & Tooling (Priority 4)

## Executive Summary

**Purpose:** Establish robust coverage measurement, reporting, and enforcement infrastructure
**Current State:** Basic coverage.py setup, HTML reports generated manually
**Target:** Automated coverage measurement, reporting, regression prevention, and team adoption

## Infrastructure Components

### 1. Coverage Measurement & Reporting

#### Current Setup Analysis
```bash
# Current coverage commands (working)
uv run coverage run --source='.' manage.py test
uv run coverage report --show-missing
uv run coverage html

# Current results
Total coverage: 55% (2381/4333 statements)
HTML reports: Generated in htmlcov/
```

#### Enhanced Coverage Configuration
**File:** `.coveragerc` (to be created/enhanced)
```ini
[run]
source = .
omit = 
    */migrations/*
    */venv/*
    */env/*
    manage.py
    */settings.py
    */tests/*
    */test_*.py
    */__pycache__/*
    */node_modules/*
    */static/*
    */media/*
    */htmlcov/*
    
[report]
# Regexes for lines to exclude from consideration
exclude_lines =
    # Have to re-enable the standard pragma
    pragma: no cover
    
    # Don't complain about missing debug-only code:
    def __repr__
    if self\.debug
    
    # Don't complain if tests don't hit defensive assertion code:
    raise AssertionError
    raise NotImplementedError
    
    # Don't complain if non-runnable code isn't run:
    if 0:
    if __name__ .__main__.:
    
    # Don't complain about Django admin
    class .*Admin.*:
    def get_.*_display
    
show_missing = True
skip_covered = False
precision = 1

[html]
directory = htmlcov
title = Container Manager Coverage Report
```

#### Advanced Reporting Scripts
**File:** `scripts/coverage_report.py` (to be created)
```python
#!/usr/bin/env python
"""Enhanced coverage reporting with analysis and recommendations."""

import subprocess
import json
import os
from pathlib import Path

class CoverageAnalyzer:
    def __init__(self):
        self.coverage_data = {}
        self.recommendations = []
        
    def run_coverage(self):
        """Run coverage and collect data."""
        subprocess.run(['uv', 'run', 'coverage', 'run', '--source=.', 'manage.py', 'test'])
        subprocess.run(['uv', 'run', 'coverage', 'json'])
        
        with open('coverage.json') as f:
            self.coverage_data = json.load(f)
            
    def analyze_priority_files(self):
        """Identify high-priority files for coverage improvement."""
        priority_patterns = [
            'management/commands/',
            'executors/',
            'docker_service.py',
        ]
        
        low_coverage_files = []
        for filename, file_data in self.coverage_data['files'].items():
            coverage_percent = (file_data['summary']['covered_lines'] / 
                             file_data['summary']['num_statements'] * 100)
            
            if coverage_percent < 70:  # Below target
                for pattern in priority_patterns:
                    if pattern in filename:
                        low_coverage_files.append({
                            'file': filename,
                            'coverage': coverage_percent,
                            'statements': file_data['summary']['num_statements'],
                            'missing': file_data['summary']['missing_lines']
                        })
                        break
                        
        return sorted(low_coverage_files, key=lambda x: x['statements'], reverse=True)
        
    def generate_recommendations(self):
        """Generate actionable coverage improvement recommendations."""
        low_coverage = self.analyze_priority_files()
        
        recommendations = []
        for file_info in low_coverage[:5]:  # Top 5 priorities
            impact_score = file_info['statements'] * (100 - file_info['coverage']) / 100
            recommendations.append({
                'file': file_info['file'],
                'current_coverage': f"{file_info['coverage']:.1f}%",
                'impact_score': impact_score,
                'recommended_action': self._get_action_for_file(file_info['file'])
            })
            
        return recommendations
        
    def _get_action_for_file(self, filename):
        """Get recommended action based on file type."""
        if 'management/commands/' in filename:
            return "Create command-specific test cases with mocked external dependencies"
        elif 'executors/' in filename:
            return "Mock external APIs (Docker/CloudRun) and test job lifecycle"
        elif 'admin.py' in filename:
            return "Focus on business logic, skip Django admin UI components"
        else:
            return "Add unit tests for core business logic"
            
    def print_report(self):
        """Print comprehensive coverage report."""
        print("=== COVERAGE ANALYSIS REPORT ===")
        print(f"Overall Coverage: {self.coverage_data['totals']['percent_covered']:.1f}%")
        print(f"Total Statements: {self.coverage_data['totals']['num_statements']}")
        print(f"Covered Statements: {self.coverage_data['totals']['covered_lines']}")
        print()
        
        recommendations = self.generate_recommendations()
        print("=== TOP PRIORITY IMPROVEMENTS ===")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['file']}")
            print(f"   Current: {rec['current_coverage']}")
            print(f"   Impact Score: {rec['impact_score']:.1f}")
            print(f"   Action: {rec['recommended_action']}")
            print()

if __name__ == '__main__':
    analyzer = CoverageAnalyzer()
    analyzer.run_coverage()
    analyzer.print_report()
```

### 2. Pre-Commit Coverage Enforcement

#### Pre-Commit Hook Integration
**File:** `.pre-commit-config.yaml` (to be enhanced)
```yaml
repos:
  - repo: local
    hooks:
      - id: coverage-check
        name: Coverage Check
        entry: scripts/check_coverage.sh
        language: script
        pass_filenames: false
        stages: [commit]
        
      - id: coverage-diff
        name: Coverage Diff Check
        entry: scripts/coverage_diff.py
        language: python
        pass_filenames: false
        stages: [commit]
```

#### Coverage Check Script
**File:** `scripts/check_coverage.sh` (to be created)
```bash
#!/bin/bash
set -e

echo "Running tests with coverage..."
uv run coverage run --source='.' manage.py test

echo "Generating coverage report..."
uv run coverage report

echo "Checking coverage thresholds..."
uv run coverage report --fail-under=75

echo "Coverage check passed ✅"
```

#### Coverage Diff Script
**File:** `scripts/coverage_diff.py` (to be created)
```python
#!/usr/bin/env python
"""Check coverage changes in current commit."""

import subprocess
import json
import sys
from pathlib import Path

def get_coverage_data():
    """Get current coverage data."""
    subprocess.run(['uv', 'run', 'coverage', 'run', '--source=.', 'manage.py', 'test'], 
                   capture_output=True)
    subprocess.run(['uv', 'run', 'coverage', 'json'], capture_output=True)
    
    with open('coverage.json') as f:
        return json.load(f)

def get_changed_files():
    """Get list of Python files changed in current commit."""
    result = subprocess.run(['git', 'diff', '--cached', '--name-only', '--diff-filter=AM'], 
                           capture_output=True, text=True)
    
    changed_files = []
    for line in result.stdout.strip().split('\n'):
        if line.endswith('.py') and not line.startswith('tests/'):
            changed_files.append(line)
            
    return changed_files

def check_new_code_coverage():
    """Ensure new/modified code has adequate coverage."""
    coverage_data = get_coverage_data()
    changed_files = get_changed_files()
    
    if not changed_files:
        print("No Python files changed, skipping coverage diff check")
        return True
        
    low_coverage_files = []
    for filename in changed_files:
        if filename in coverage_data['files']:
            file_data = coverage_data['files'][filename]
            coverage_percent = (file_data['summary']['covered_lines'] / 
                              file_data['summary']['num_statements'] * 100)
            
            # Stricter requirement for new/modified code
            if coverage_percent < 90:
                low_coverage_files.append((filename, coverage_percent))
                
    if low_coverage_files:
        print("❌ Coverage check failed for modified files:")
        for filename, coverage in low_coverage_files:
            print(f"  {filename}: {coverage:.1f}% (requires ≥90%)")
        print("\nPlease add tests for new/modified code before committing.")
        return False
        
    print("✅ Coverage check passed for all modified files")
    return True

if __name__ == '__main__':
    success = check_new_code_coverage()
    sys.exit(0 if success else 1)
```

### 3. Continuous Integration Coverage

#### GitHub Actions Workflow Enhancement
**File:** `.github/workflows/test.yml` (to be enhanced)
```yaml
name: Tests with Coverage

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install uv
      run: pip install uv
      
    - name: Install dependencies
      run: uv sync
      
    - name: Run tests with coverage
      run: |
        uv run coverage run --source='.' manage.py test
        uv run coverage xml
        uv run coverage report
        
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
        
    - name: Coverage comment
      uses: py-cov-action/python-coverage-comment-action@v3
      with:
        GITHUB_TOKEN: ${{ github.token }}
        
    - name: Check coverage threshold
      run: uv run coverage report --fail-under=75
```

### 4. Coverage Monitoring & Alerting

#### Coverage Tracking Database
**File:** `scripts/coverage_tracker.py` (to be created)
```python
#!/usr/bin/env python
"""Track coverage changes over time."""

import sqlite3
import json
import datetime
import subprocess
from pathlib import Path

class CoverageTracker:
    def __init__(self, db_path='coverage_history.db'):
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """Initialize coverage tracking database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coverage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                commit_hash TEXT NOT NULL,
                branch TEXT NOT NULL,
                overall_coverage REAL NOT NULL,
                total_statements INTEGER NOT NULL,
                covered_statements INTEGER NOT NULL,
                coverage_data TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def record_coverage(self):
        """Record current coverage data."""
        # Run coverage
        subprocess.run(['uv', 'run', 'coverage', 'run', '--source=.', 'manage.py', 'test'])
        subprocess.run(['uv', 'run', 'coverage', 'json'])
        
        # Get git info
        commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()
        
        # Load coverage data
        with open('coverage.json') as f:
            coverage_data = json.load(f)
            
        # Store in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO coverage_history 
            (timestamp, commit_hash, branch, overall_coverage, total_statements, 
             covered_statements, coverage_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.datetime.now().isoformat(),
            commit_hash,
            branch,
            coverage_data['totals']['percent_covered'],
            coverage_data['totals']['num_statements'],
            coverage_data['totals']['covered_lines'],
            json.dumps(coverage_data)
        ))
        
        conn.commit()
        conn.close()
        
    def check_regression(self, threshold=2.0):
        """Check for coverage regression."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get last two coverage measurements
        cursor.execute('''
            SELECT overall_coverage FROM coverage_history 
            ORDER BY timestamp DESC LIMIT 2
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        if len(results) < 2:
            return False  # Not enough data
            
        current_coverage = results[0][0]
        previous_coverage = results[1][0]
        
        regression = previous_coverage - current_coverage
        
        if regression > threshold:
            print(f"❌ Coverage regression detected: {regression:.1f}% decrease")
            print(f"Previous: {previous_coverage:.1f}%, Current: {current_coverage:.1f}%")
            return True
            
        return False

if __name__ == '__main__':
    tracker = CoverageTracker()
    tracker.record_coverage()
    
    if tracker.check_regression():
        exit(1)  # Fail build on regression
```

### 5. Development Workflow Integration

#### IDE Integration Setup
**File:** `docs/coverage_setup.md` (to be created)
```markdown
# Coverage Integration Setup

## VS Code Integration

1. Install Python extension
2. Add to settings.json:
```json
{
    "python.testing.coverageEnabled": true,
    "python.testing.coverageCommand": "uv run coverage",
    "python.testing.pytestArgs": ["--cov=.", "--cov-report=html"]
}
```

## PyCharm Integration

1. Go to Settings → Tools → Python Integrated Tools
2. Set Default test runner to pytest
3. Add coverage options: `--cov=. --cov-report=html`

## Command Line Aliases

Add to your shell profile:
```bash
alias coverage-run="uv run coverage run --source='.' manage.py test"
alias coverage-report="uv run coverage report --show-missing"
alias coverage-html="uv run coverage html && open htmlcov/index.html"
alias coverage-check="uv run coverage report --fail-under=75"
```
```

#### Development Scripts
**File:** `scripts/dev_coverage.py` (to be created)
```python
#!/usr/bin/env python
"""Development-friendly coverage tools."""

import subprocess
import argparse
import webbrowser
from pathlib import Path

def run_coverage_for_app(app_name):
    """Run coverage for specific Django app."""
    print(f"Running tests for {app_name} with coverage...")
    subprocess.run([
        'uv', 'run', 'coverage', 'run', '--source=.', 
        'manage.py', 'test', app_name
    ])
    
    subprocess.run(['uv', 'run', 'coverage', 'report', '--show-missing'])
    
def run_coverage_for_file(filename):
    """Run coverage for specific file."""
    # Find tests for this file
    test_file = filename.replace('.py', '_test.py').replace('/', '/test_')
    
    print(f"Running tests for {filename}...")
    subprocess.run([
        'uv', 'run', 'coverage', 'run', '--source=.', 
        'manage.py', 'test', test_file
    ])
    
def generate_html_and_open():
    """Generate HTML coverage report and open in browser."""
    subprocess.run(['uv', 'run', 'coverage', 'html'])
    
    html_file = Path('htmlcov/index.html').absolute()
    if html_file.exists():
        webbrowser.open(f'file://{html_file}')
        print(f"Opened coverage report: {html_file}")
    else:
        print("Coverage HTML report not found")

def main():
    parser = argparse.ArgumentParser(description="Development coverage tools")
    parser.add_argument('--app', help="Run coverage for specific Django app")
    parser.add_argument('--file', help="Run coverage for specific file")
    parser.add_argument('--html', action='store_true', help="Generate and open HTML report")
    
    args = parser.parse_args()
    
    if args.app:
        run_coverage_for_app(args.app)
    elif args.file:
        run_coverage_for_file(args.file)
    elif args.html:
        generate_html_and_open()
    else:
        print("Please specify --app, --file, or --html")

if __name__ == '__main__':
    main()
```

## Implementation Plan

### Phase 1: Enhanced Coverage Configuration (2-3 hours)
1. Create/enhance `.coveragerc` with proper exclusions
2. Set up coverage JSON output for analysis
3. Test coverage measurement accuracy

### Phase 2: Reporting & Analysis Tools (4-6 hours)
1. Create `coverage_report.py` analysis script
2. Implement priority-based recommendations
3. Add impact scoring for coverage improvements

### Phase 3: Pre-Commit Integration (3-4 hours)
1. Set up coverage check scripts
2. Implement coverage diff checking
3. Configure pre-commit hooks

### Phase 4: CI/CD Enhancement (2-3 hours)
1. Enhance GitHub Actions workflow
2. Add Codecov integration
3. Set up coverage commenting on PRs

### Phase 5: Monitoring & Tracking (3-4 hours)
1. Implement coverage history tracking
2. Add regression detection
3. Set up alerting for coverage drops

### Phase 6: Developer Experience (2-3 hours)
1. Create development scripts
2. Document IDE integration
3. Add command-line aliases

## Success Metrics

### Infrastructure Quality
- **Automated coverage measurement** in CI/CD
- **Pre-commit coverage enforcement** preventing regressions
- **Coverage regression detection** with alerting
- **Developer-friendly tools** for local coverage analysis

### Coverage Process
- **Coverage measured on every commit**
- **Regression prevention** (no coverage drops >2%)
- **New code requirements** (≥90% coverage for modified files)
- **Regular coverage reporting** and recommendations

### Team Adoption
- **Developer IDE integration** working smoothly
- **Pre-commit hooks** running successfully
- **CI/CD coverage** reporting in PRs
- **Coverage analysis** informing development priorities

## Timeline Estimate

### Conservative Estimate: 18-24 hours
- **Configuration:** 3 hours
- **Analysis tools:** 6 hours
- **Pre-commit integration:** 4 hours
- **CI/CD enhancement:** 3 hours
- **Monitoring setup:** 4 hours
- **Developer experience:** 3 hours
- **Testing and documentation:** 1-3 hours

### Optimistic Estimate: 14-18 hours
- **Configuration:** 2 hours
- **Analysis tools:** 4 hours
- **Pre-commit integration:** 3 hours
- **CI/CD enhancement:** 2 hours
- **Monitoring setup:** 3 hours
- **Developer experience:** 2 hours
- **Testing and documentation:** 1-2 hours

## Dependencies

### Prerequisites
- Basic coverage.py setup (already done)
- Git hooks infrastructure
- GitHub Actions workflow exists
- SQLite for coverage tracking

### Coordination
- Should be implemented before major coverage improvement work
- Provides foundation for all other coverage tasks
- Enables measurement of coverage improvement progress
- Supports team adoption of coverage practices