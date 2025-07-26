# Task 007: Implement Google Cloud Run Executor

## Objective
Create a CloudRunExecutor that executes container jobs using Google Cloud Run Jobs API, enabling serverless container execution with automatic scaling and pay-per-use pricing.

## Git Strategy  
- Branch: `task-007-cloudrun-executor`
- Commit pattern: "Add [component]: [cloud run functionality]"
- Commits: "Add CloudRunExecutor class", "Add GCP authentication", "Add job status monitoring"

## Prerequisites
- Task 001 completed (ContainerExecutor interface)
- Task 006 completed (MockExecutor for testing patterns)
- Google Cloud SDK understanding
- Cloud Run Jobs API knowledge

## Implementation Steps

1. [ ] Create `container_manager/executors/cloudrun.py`
2. [ ] Implement CloudRunExecutor with GCP integration
3. [ ] Add authentication handling (service account, ADC)
4. [ ] Map Django job parameters to Cloud Run job specs
5. [ ] Implement log collection from Cloud Logging
6. [ ] Add cost estimation and tracking
7. [ ] Create comprehensive tests with mocked GCP APIs
8. [ ] Run ruff format and check before committing

## Success Criteria
- [ ] CloudRunExecutor implements all ContainerExecutor methods
- [ ] Proper GCP authentication handling
- [ ] Job parameter mapping works correctly
- [ ] Log collection from Cloud Logging
- [ ] Error handling for GCP API failures
- [ ] Cost tracking integration
- [ ] Comprehensive test coverage with mocks

## Next Task Preparation
Provides pattern for implementing other cloud executors (Fargate, Scaleway)