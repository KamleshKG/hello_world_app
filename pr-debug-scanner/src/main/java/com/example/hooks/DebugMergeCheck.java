package com.example.hooks;

import com.atlassian.bitbucket.content.ContentService;
import com.atlassian.bitbucket.hook.repository.*;
import com.atlassian.bitbucket.pull.PullRequest;
import com.atlassian.bitbucket.repository.Repository;
import com.atlassian.plugin.spring.scanner.annotation.imports.ComponentImport;
import com.example.service.SettingsService;
import jakarta.annotation.Nonnull;
import jakarta.inject.Inject;
import jakarta.inject.Named;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;

@Named
public class DebugMergeCheck implements RepositoryMergeCheck {
    private final ContentService contentService;
    private final SettingsService settingsService;

    @Inject // Added
    public DebugMergeCheck(@ComponentImport ContentService contentService,
                           SettingsService settingsService) {
        this.contentService = contentService;
        this.settingsService = settingsService;
    }
        this.contentService = contentService;
        this.settingsService = settingsService;
    }

    @Nonnull
    @Override
    public RepositoryHookResult preUpdate(@Nonnull PreRepositoryHookContext context,
                                          @Nonnull PullRequestMergeHookRequest request) {
        PullRequest pr = request.getPullRequest();
        Repository repo = pr.getToRef().getRepository();

        if (!settingsService.isEnabled(repo)) {
            return RepositoryHookResult.accepted();
        }

        try {
            ByteArrayOutputStream captured = new ByteArrayOutputStream();
            contentService.streamFile(repo, pr.getToRef().getLatestCommit(), "web.config", (ignored) -> captured);
            if (captured.toString(StandardCharsets.UTF_8).contains("debug=\"true\"")) {
                return RepositoryHookResult.rejected("Security Policy Failure", "Merge blocked: debug=\"true\" detected.");
            }
        } catch (Exception ignored) {}
        return RepositoryHookResult.accepted();
    }
}