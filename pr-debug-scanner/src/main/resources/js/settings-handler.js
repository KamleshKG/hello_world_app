(function ($) {
    $(document).on('change', '#debug-enabled-select', function () {
        const val = $(this).val();
        const repoId = window.bitbucket.repository.id;

        $.ajax({
            url: AJS.contextPath() + '/rest/scan-settings/1.0/settings/repo/' + repoId,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ enabled: val }),
            success: function () {
                AJS.flag({ type: 'success', title: 'Saved!', body: 'Settings updated.' });
            }
        });
    });
})(AJS.$);