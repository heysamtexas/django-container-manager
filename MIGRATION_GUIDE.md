# Migration Guide: Legacy Mode → Queue Mode

## 🚨 Legacy Mode Deprecation Notice

**Legacy mode has been deprecated** and will be removed in a future version. Please migrate to **Queue Mode** (now the default) for better performance, reliability, and features.

## Quick Migration

### ✅ NEW (Recommended - Queue Mode)
```bash
# Queue mode is now the default - no flags needed!
python manage.py process_container_jobs                    # Continuous processing
python manage.py process_container_jobs --once             # Process once and exit
python manage.py process_container_jobs --max-concurrent=10 # Custom concurrency
```

### ❌ OLD (Deprecated - Legacy Mode)  
```bash
# These commands now show deprecation warnings
python manage.py process_container_jobs --legacy-mode              # ⚠️  DEPRECATED
python manage.py process_container_jobs --legacy-mode --single-run # ⚠️  DEPRECATED  
python manage.py process_container_jobs --legacy-mode --host=docker-host # ⚠️  DEPRECATED
```

## Key Differences

| Feature | Legacy Mode | Queue Mode |
|---------|-------------|------------|
| **Job Selection** | Finds `pending` jobs | Finds `queued` jobs |
| **Priority Handling** | ❌ None | ✅ Priority-based selection |
| **Retry Logic** | ❌ Basic | ✅ Exponential backoff |
| **Concurrency Control** | ❌ Simple limit | ✅ Intelligent resource management |
| **Graceful Shutdown** | ❌ Basic | ✅ Advanced with job completion tracking |
| **Metrics & Monitoring** | ❌ Limited | ✅ Real-time queue statistics |

## Migration Steps

### 1. Update Job Creation
Ensure new jobs are created in **queue mode** workflow:

```python
# ✅ RECOMMENDED: Create and queue jobs
job = ContainerJob.objects.create(...)
queue_manager.queue_job(job, priority=80)  # High priority

# ❌ OLD: Create jobs in pending status  
job = ContainerJob.objects.create(status='pending', ...)
```

### 2. Update Management Commands
```bash
# ✅ NEW: Default behavior (queue mode)
python manage.py process_container_jobs --once

# ❌ OLD: Explicit legacy mode (deprecated)
python manage.py process_container_jobs --legacy-mode --single-run
```

### 3. Admin Interface Migration
- **Queue Jobs**: Use admin bulk actions like "Queue Selected Jobs"
- **Priority Management**: Set job priorities for intelligent processing
- **Monitoring**: Check queue status instead of individual job status

## Deprecated Arguments

These arguments show warnings and will be removed:

- `--legacy-mode` - Use default queue mode instead
- `--single-run` - Use `--once` instead
- `--host` - Queue mode handles all hosts intelligently  
- `--max-jobs` - Use `--max-concurrent` instead
- `--cleanup` - Use `cleanup_containers` command separately
- `--use-factory` - Always enabled in queue mode
- `--executor-type` - Queue mode handles all executor types

## Benefits of Queue Mode

### 🚀 **Performance**
- Priority-based job selection
- Intelligent concurrency management
- Efficient resource utilization

### 🛡️ **Reliability**  
- Automatic retry with exponential backoff
- Graceful shutdown with job completion tracking
- Better error handling and recovery

### 📊 **Monitoring**
- Real-time queue statistics
- Job completion tracking
- Enhanced logging and metrics

### 🔧 **Operations**
- Signal-based status reporting (`kill -USR1 <pid>`)
- Enhanced graceful shutdown (`kill -TERM <pid>`)
- Better Docker integration

## Getting Help

If you encounter issues during migration:

1. **Test with dry-run**: `python manage.py process_container_jobs --dry-run`
2. **Check queue status**: Use admin interface queue displays
3. **Monitor logs**: Enable `--verbose` for detailed output
4. **Gradual migration**: Both modes work simultaneously during transition

## Timeline

- **Now**: Legacy mode deprecated with warnings
- **Next version**: Legacy mode will show stronger warnings  
- **Future version**: Legacy mode will be removed entirely

**Migrate now to avoid disruption!** 🚀