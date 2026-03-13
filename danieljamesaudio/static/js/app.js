// Daniel James Audio - Client-side JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll('.alert-dismissible').forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });
});

/**
 * Handle photo upload preview before form submission.
 * Attach to a file input to show a thumbnail preview.
 */
function setupPhotoPreview(inputId, previewId) {
    var input = document.getElementById(inputId);
    var preview = document.getElementById(previewId);
    if (!input || !preview) return;

    input.addEventListener('change', function(e) {
        var file = e.target.files[0];
        if (!file) return;

        var reader = new FileReader();
        reader.onload = function(ev) {
            preview.src = ev.target.result;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
    });
}

/**
 * Send a photo to the Claude identification endpoint via AJAX.
 */
function identifyEquipment(fileInput, callback) {
    var file = fileInput.files[0];
    if (!file) return;

    var formData = new FormData();
    formData.append('photo', file);

    fetch('/equipment/identify', {
        method: 'POST',
        body: formData
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        if (data.success) {
            callback(data);
        } else {
            alert('Could not identify equipment: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(err) {
        alert('Error identifying equipment: ' + err.message);
    });
}
