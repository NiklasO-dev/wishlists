// Minimal JS - copy to clipboard for share links
document.addEventListener('DOMContentLoaded', function() {
    // Auto-select text in readonly inputs on click
    document.querySelectorAll('input[readonly]').forEach(function(input) {
        input.addEventListener('click', function() {
            this.select();
            if (navigator.clipboard) {
                navigator.clipboard.writeText(this.value);
            }
        });
    });
});
