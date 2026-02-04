(function ($) {
    $(document).on('change', '#debug-enabled-select', function () {
        const val = $(this).val();
        const repoId = window.bitbucket && window.bitbucket.repository
            ? window.bitbucket.repository.id
            : null;

        if (!repoId) {
            AJS.flag({ type: 'error', title: 'Error', body: 'Could not detect repository ID.' });
            return;
        }

        $.ajax({
            url: AJS.contextPath() + '/rest/scan-settings/1.0/settings/repo/' + repoId,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ enabled: val }),
            success: function () {
                AJS.flag({ type: 'success', title: 'Saved!', body: 'Settings updated.' });
            },
            error: function (xhr) {
                AJS.flag({
                    type: 'error',
                    title: 'Save failed',
                    body: 'Could not save settings. HTTP ' + (xhr && xhr.status ? xhr.status : '')
                });
            }
        });
    });
})(AJS.$);