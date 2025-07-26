/* Container Manager Admin JavaScript */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips and popovers
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-refresh job status indicators
    setupAutoRefresh();
    
    // Setup real-time log streaming
    setupLogStreaming();
    
    // Setup enhanced form validation
    setupFormValidation();
});

function setupAutoRefresh() {
    // Auto-refresh status indicators every 30 seconds on job list pages
    if (window.location.pathname.includes('/containerjob/')) {
        setInterval(function() {
            refreshJobStatuses();
        }, 30000);
    }
    
    // Auto-refresh connection status for Docker hosts
    if (window.location.pathname.includes('/dockerhost/')) {
        setInterval(function() {
            refreshConnectionStatuses();
        }, 60000); // Every minute
    }
}

function refreshJobStatuses() {
    const statusCells = document.querySelectorAll('.field-status');
    statusCells.forEach(function(cell) {
        const jobRow = cell.closest('tr');
        const jobId = getJobIdFromRow(jobRow);
        
        if (jobId) {
            // Use HTMX to refresh the status
            htmx.ajax('GET', `/admin/container_manager/containerjob/${jobId}/status/`, {
                target: cell,
                swap: 'innerHTML'
            });
        }
    });
}

function refreshConnectionStatuses() {
    const statusCells = document.querySelectorAll('.field-connection_status');
    statusCells.forEach(function(cell) {
        const hostRow = cell.closest('tr');
        const hostId = getHostIdFromRow(hostRow);
        
        if (hostId) {
            htmx.ajax('GET', `/admin/container_manager/dockerhost/${hostId}/status/`, {
                target: cell,
                swap: 'innerHTML'
            });
        }
    });
}

function setupLogStreaming() {
    // Setup WebSocket connections for real-time log streaming
    const logButtons = document.querySelectorAll('.view-logs-btn');
    
    logButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const jobId = this.dataset.jobId;
            openLogsModal(jobId);
        });
    });
}

function openLogsModal(jobId) {
    const modal = new bootstrap.Modal(document.getElementById('logsModal'));
    const logsContainer = document.getElementById('logsContainer');
    const modalTitle = document.getElementById('logsModalLabel');
    
    modalTitle.textContent = `Logs for Job ${jobId}`;
    logsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    
    modal.show();
    
    // Load initial logs
    htmx.ajax('GET', `/admin/container_manager/containerjob/${jobId}/logs/`, {
        target: '#logsContainer',
        swap: 'innerHTML'
    });
    
    // Setup WebSocket for real-time updates
    setupLogWebSocket(jobId);
}

function setupLogWebSocket(jobId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/logs/${jobId}/`;
    
    const socket = new WebSocket(wsUrl);
    
    socket.onopen = function(e) {
        console.log('Log WebSocket connected for job:', jobId);
    };
    
    socket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        updateLogsDisplay(data);
    };
    
    socket.onclose = function(e) {
        console.log('Log WebSocket disconnected');
    };
    
    socket.onerror = function(e) {
        console.error('Log WebSocket error:', e);
    };
    
    // Close socket when modal is closed
    const modal = document.getElementById('logsModal');
    modal.addEventListener('hidden.bs.modal', function() {
        socket.close();
    });
}

function updateLogsDisplay(data) {
    const container = document.getElementById('logsContainer');
    
    if (data.type === 'log_update') {
        let html = '<div class="logs-viewer">';
        
        if (data.logs.stdout) {
            html += `<div class="log-section mb-3">
                <h6 class="text-success">Standard Output:</h6>
                <pre class="stdout-log">${escapeHtml(data.logs.stdout)}</pre>
            </div>`;
        }
        
        if (data.logs.stderr) {
            html += `<div class="log-section mb-3">
                <h6 class="text-danger">Standard Error:</h6>
                <pre class="stderr-log">${escapeHtml(data.logs.stderr)}</pre>
            </div>`;
        }
        
        if (data.logs.docker) {
            html += `<div class="log-section mb-3">
                <h6 class="text-info">Docker Logs:</h6>
                <pre class="docker-log">${escapeHtml(data.logs.docker)}</pre>
            </div>`;
        }
        
        html += '</div>';
        container.innerHTML = html;
        
        // Auto-scroll to bottom
        container.scrollTop = container.scrollHeight;
    }
}

function setupFormValidation() {
    // Enhanced form validation for container templates
    const templateForms = document.querySelectorAll('form[name="containertemplate_form"]');
    
    templateForms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            if (!validateTemplateForm(form)) {
                e.preventDefault();
                showValidationErrors();
            }
        });
    });
}

function validateTemplateForm(form) {
    let isValid = true;
    const errors = [];
    
    // Validate Docker image format
    const imageField = form.querySelector('#id_docker_image');
    if (imageField && imageField.value) {
        const imageRegex = /^([a-zA-Z0-9_.-]+\/)?[a-zA-Z0-9_.-]+(:[\w.-]+)?$/;
        if (!imageRegex.test(imageField.value)) {
            errors.push('Docker image format is invalid');
            isValid = false;
        }
    }
    
    // Validate resource limits
    const memoryField = form.querySelector('#id_memory_limit');
    if (memoryField && memoryField.value) {
        const memory = parseInt(memoryField.value);
        if (memory < 64) {
            errors.push('Memory limit must be at least 64 MB');
            isValid = false;
        }
    }
    
    const cpuField = form.querySelector('#id_cpu_limit');
    if (cpuField && cpuField.value) {
        const cpu = parseFloat(cpuField.value);
        if (cpu < 0.1 || cpu > 32) {
            errors.push('CPU limit must be between 0.1 and 32.0');
            isValid = false;
        }
    }
    
    // Store errors for display
    form._validationErrors = errors;
    return isValid;
}

function showValidationErrors() {
    // Display validation errors using Bootstrap alerts
    const errors = document.querySelector('form')._validationErrors;
    if (errors && errors.length > 0) {
        const alertHtml = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <strong>Validation Error:</strong>
                <ul class="mb-0">
                    ${errors.map(error => `<li>${error}</li>`).join('')}
                </ul>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        const formContainer = document.querySelector('.form-container') || document.querySelector('form').parentNode;
        formContainer.insertAdjacentHTML('afterbegin', alertHtml);
    }
}

// Utility functions
function getJobIdFromRow(row) {
    const link = row.querySelector('a[href*="/containerjob/"]');
    if (link) {
        const match = link.href.match(/\/containerjob\/([^\/]+)\//);
        return match ? match[1] : null;
    }
    return null;
}

function getHostIdFromRow(row) {
    const link = row.querySelector('a[href*="/dockerhost/"]');
    if (link) {
        const match = link.href.match(/\/dockerhost\/([^\/]+)\//);
        return match ? match[1] : null;
    }
    return null;
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Export functions for global access
window.ContainerManager = {
    refreshJobStatuses: refreshJobStatuses,
    refreshConnectionStatuses: refreshConnectionStatuses,
    openLogsModal: openLogsModal,
    setupLogWebSocket: setupLogWebSocket
};