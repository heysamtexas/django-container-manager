# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-08-06

### Added
- Django Container Manager - Complete Django app for container orchestration
- Multi-executor support (Docker, Google Cloud Run, AWS Fargate, Mock)
- Container job lifecycle management with full tracking
- Django admin integration with real-time monitoring
- Management commands for job processing and cleanup  
- Resource monitoring (CPU, memory usage)
- Environment variable template system
- Production-ready security controls and resource limits
- Comprehensive test suite with >75% coverage
- Complete documentation including installation, usage, and troubleshooting guides

### Features
- **ContainerJob Model**: Full lifecycle tracking of containerized tasks
- **ExecutorHost Configuration**: Flexible executor selection and routing
- **Real-time Monitoring**: Live job status updates and log viewing
- **Background Processing**: Automatic job execution via management command
- **Multi-cloud Support**: Single codebase for local and cloud deployments
- **Django Integration**: Seamless integration with existing Django projects
- **Resource Management**: Memory and CPU limits with monitoring
- **Error Handling**: Comprehensive error tracking and recovery

### Security
- Container isolation with security contexts
- Resource limits (max 2GB memory, 2 CPU cores)
- Network isolation and TLS support
- Environment variable masking for sensitive data

### Documentation
- Complete API reference
- Installation guide for all platforms  
- Docker integration guide
- Troubleshooting documentation
- Contributing guidelines

## v1.0.13 (2025-08-07)

## v1.0.12 (2025-08-07)

## v1.0.11 (2025-08-07)

## v1.0.10 (2025-08-07)

## v1.0.9 (2025-08-07)

## v1.0.8 (2025-08-07)

## v1.0.7 (2025-08-07)

## v1.0.6 (2025-08-07)

## v1.0.5 (2025-08-07)

## v1.0.4 (2025-08-07)

## v1.0.3 (2025-08-07)

## v1.0.1 (2025-08-06)

## v1.0.0 (2025-08-06)

### Feat

- expand management command test coverage to 55%+ with comprehensive business logic testing
- implement comprehensive code coverage infrastructure and management command testing
