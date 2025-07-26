# Task 005: Update Management Commands for Multi-Executor Support

## Objective
Update `process_container_jobs` and `manage_container_job` commands to use the executor factory, enabling multi-cloud job execution while maintaining backward compatibility and existing command-line interfaces.

## Git Strategy  
- Branch: `task-005-update-commands`
- Commit pattern: "Update [command]: [change description]"
- Commits: "Update process_container_jobs for multi-executor", "Update manage_container_job commands", "Add executor status reporting"

## Prerequisites
- Task 004 completed (ExecutorFactory and routing logic)
- All previous tasks completed
- Understanding of existing command structure

## Implementation Steps

1. [ ] Update `process_container_jobs.py` to use executor factory
2. [ ] Update `manage_container_job.py` for multi-executor operations
3. [ ] Add executor status and capacity reporting commands
4. [ ] Update job monitoring to handle multiple executor types
5. [ ] Add command-line options for executor preferences
6. [ ] Ensure backward compatibility with existing usage
7. [ ] Run ruff format and check before committing

## Code Quality Requirements
- Maintain existing command-line interface
- Use early returns in command logic
- Keep method complexity low
- Add comprehensive help text for new options
- Preserve existing functionality exactly

## Success Criteria
- [ ] All commands work with multiple executor types
- [ ] Existing command-line usage unchanged
- [ ] New executor-specific options available
- [ ] Job monitoring works across all executors
- [ ] Status reporting includes executor information
- [ ] Backward compatibility maintained
- [ ] Performance characteristics preserved

## Next Task Preparation
Sets up foundation for Task 006 (MockExecutor implementation)