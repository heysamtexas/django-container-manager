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
    
    // Setup enhanced form validation
    setupFormValidation();
});

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
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}