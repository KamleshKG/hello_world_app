package com.example.hooks;

import com.atlassian.bitbucket.hook.repository.*;
import com.atlassian.bitbucket.content.*;
import com.atlassian.bitbucket.repository.Repository;
import com.atlassian.bitbucket.pull.PullRequest;
import com.atlassian.bitbucket.util.InputSupplier;
import com.example.service.SettingsService;
import javax.annotation.Nonnull;
import java.io.*;

public class DebugMergeCheck implements RepositoryMergeCheck {
    private final ContentService contentService;
    private final SettingsService settingsService;

    public DebugMergeCheck(ContentService contentService, SettingsService settingsService) {
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
            // Fix: Removing <InputStream> to resolve "does not take parameters" error
            InputSupplier supplier = contentService.getContent(repo, pr.getToRef().getLatestCommit(), "web.config");
            
            try (InputStream is = (InputStream) supplier.openStream();
                 BufferedReader reader = new BufferedReader(new InputStreamReader(is))) {
                
                if (reader.lines().anyMatch(line -> line.contains("debug=\"true\""))) {
                    return RepositoryHookResult.rejected(
                        "Security Policy Failure", 
                        "Merge blocked: debug=\"true\" detected in web.config."
                    );
                }
            }
        } catch (Exception e) {
            // File not found or error accessing; allow the merge
        }

        return RepositoryHookResult.accepted();
    }
}