// Main JavaScript for Memory Site

$(document).ready(function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // File upload preview
    $('#file-input').change(function() {
        const file = this.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                $('#preview').attr('src', e.target.result).show();
            }
            reader.readAsDataURL(file);
        }
    });
    
    // Drag and drop upload
    const dropzone = $('.dropzone');
    
    dropzone.on('drag dragstart dragend dragover dragenter dragleave drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
    });
    
    dropzone.on('dragover dragenter', function() {
        dropzone.addClass('dragover');
    });
    
    dropzone.on('dragleave dragend drop', function() {
        dropzone.removeClass('dragover');
    });
    
    dropzone.on('drop', function(e) {
        const files = e.originalEvent.dataTransfer.files;
        if (files.length > 0) {
            $('#file-input')[0].files = files;
            $('#preview').attr('src', URL.createObjectURL(files[0])).show();
        }
    });
    
    // Lightbox functionality
    $('.memory-card img').click(function() {
        const imgSrc = $(this).attr('src');
        const title = $(this).closest('.memory-card').find('h6').text();
        
        $('.lightbox-content').attr('src', imgSrc);
        $('.lightbox-caption').text(title);
        $('.lightbox').addClass('active');
    });
    
    $('.lightbox-close, .lightbox').click(function(e) {
        if (e.target === this) {
            $('.lightbox').removeClass('active');
        }
    });
    
    // Keyboard navigation
    $(document).keydown(function(e) {
        if ($('.lightbox').hasClass('active')) {
            if (e.key === 'Escape') {
                $('.lightbox').removeClass('active');
            } else if (e.key === 'ArrowLeft') {
                navigateLightbox('prev');
            } else if (e.key === 'ArrowRight') {
                navigateLightbox('next');
            }
        }
    });
    
    // Favorite toggle
    $('.favorite-btn').click(function() {
        const memoryId = $(this).data('memory-id');
        const btn = $(this);
        
        $.ajax({
            url: `/memory/${memoryId}/edit`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                is_favorite: !btn.hasClass('active')
            }),
            success: function(response) {
                if (response.success) {
                    btn.toggleClass('active');
                    btn.find('i').toggleClass('fas far');
                }
            }
        });
    });
    
    // Delete memory confirmation
    $('.delete-memory').click(function(e) {
        e.preventDefault();
        const url = $(this).attr('href');
        
        if (confirm('Are you sure you want to delete this memory? This action cannot be undone.')) {
            window.location.href = url;
        }
    });
    
    // Search with debounce
    let searchTimeout;
    $('#search-input').keyup(function() {
        clearTimeout(searchTimeout);
        const query = $(this).val();
        
        if (query.length >= 3) {
            searchTimeout = setTimeout(function() {
                performSearch(query);
            }, 500);
        }
    });
    
    // Infinite scroll for gallery
    let loading = false;
    let page = 1;
    
    $(window).scroll(function() {
        if ($(window).scrollTop() + $(window).height() > $(document).height() - 100) {
            if (!loading) {
                loadMoreMemories();
            }
        }
    });
});

// Lightbox navigation
function navigateLightbox(direction) {
    const currentImg = $('.lightbox-content').attr('src');
    const currentCard = $(`img[src="${currentImg}"]`).closest('.memory-card');
    let targetCard;
    
    if (direction === 'next') {
        targetCard = currentCard.next('.memory-card');
    } else {
        targetCard = currentCard.prev('.memory-card');
    }
    
    if (targetCard.length) {
        const newImg = targetCard.find('img').attr('src');
        const title = targetCard.find('h6').text();
        
        $('.lightbox-content').attr('src', newImg);
        $('.lightbox-caption').text(title);
    }
}

// Search function
function performSearch(query) {
    $('#search-results').html('<div class="spinner"></div>');
    
    $.ajax({
        url: '/search',
        method: 'GET',
        data: { q: query },
        success: function(response) {
            $('#search-results').html(response);
        }
    });
}

// Load more memories for infinite scroll
function loadMoreMemories() {
    loading = true;
    page++;
    
    $.ajax({
        url: '/gallery',
        method: 'GET',
        data: { page: page },
        success: function(response) {
            if (response.trim()) {
                $('#gallery-grid').append(response);
                loading = false;
            } else {
                loading = true; // No more pages
            }
        }
    });
}

// Upload with progress
function uploadFile(file, formData) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percent = (e.loaded / e.total) * 100;
                updateUploadProgress(percent);
            }
        });
        
        xhr.addEventListener('load', function() {
            if (xhr.status === 200) {
                resolve(JSON.parse(xhr.response));
            } else {
                reject(new Error('Upload failed'));
            }
        });
        
        xhr.addEventListener('error', reject);
        
        xhr.open('POST', '/upload');
        xhr.send(formData);
    });
}

// Update upload progress
function updateUploadProgress(percent) {
    $('.progress-bar').css('width', percent + '%');
    $('#uploadStatus').text(`Uploading... ${Math.round(percent)}%`);
    
    if (percent >= 100) {
        $('#uploadStatus').text('Processing...');
    }
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Get file icon based on type
function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    
    const icons = {
        // Images
        'jpg': 'fa-file-image',
        'jpeg': 'fa-file-image',
        'png': 'fa-file-image',
        'gif': 'fa-file-image',
        
        // Videos
        'mp4': 'fa-file-video',
        'mov': 'fa-file-video',
        'avi': 'fa-file-video',
        'mkv': 'fa-file-video',
        
        // Default
        'default': 'fa-file'
    };
    
    return icons[ext] || icons['default'];
}

// Show notification
function showNotification(message, type = 'info') {
    const types = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'warning': 'alert-warning',
        'info': 'alert-info'
    };
    
    const alert = $(`
        <div class="alert ${types[type]} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    
    $('.container').prepend(alert);
    
    setTimeout(function() {
        alert.alert('close');
    }, 5000);
}
