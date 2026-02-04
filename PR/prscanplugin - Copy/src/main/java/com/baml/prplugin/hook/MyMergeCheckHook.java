package com.baml.prplugin.hook;

import com.atlassian.bitbucket.content.*;
import com.atlassian.bitbucket.hook.repository.*;
import com.atlassian.bitbucket.pull.*;
import com.atlassian.bitbucket.repository.Repository;
import com.atlassian.bitbucket.util.Page;
import com.atlassian.bitbucket.util.PageRequestImpl;
import com.atlassian.sal.api.pluginsettings.PluginSettings;
import com.atlassian.sal.api.pluginsettings.PluginSettingsFactory;
import org.osgi.framework.BundleContext;
import org.osgi.framework.FrameworkUtil;
import org.osgi.framework.ServiceReference;

import javax.annotation.Nonnull;
import java.util.ArrayList;
import java.util.List;

public class MyMergeCheckHook implements RepositoryMergeCheck {

    private PullRequestService pullRequestService;
    private ContentService contentService;
    private PluginSettingsFactory pluginSettingsFactory;

    // Use lazy initialization
    private synchronized void ensureServices() {
        if (pullRequestService == null || contentService == null || pluginSettingsFactory == null) {
            BundleContext ctx = FrameworkUtil.getBundle(MyMergeCheckHook.class).getBundleContext();

            ServiceReference<?> prRef = ctx.getServiceReference(PullRequestService.class.getName());
            if (prRef != null) {
                pullRequestService = (PullRequestService) ctx.getService(prRef);
            }

            ServiceReference<?> contentRef = ctx.getServiceReference(ContentService.class.getName());
            if (contentRef != null) {
                contentService = (ContentService) ctx.getService(contentRef);
            }

            ServiceReference<?> settingsRef = ctx.getServiceReference(PluginSettingsFactory.class.getName());
            if (settingsRef != null) {
                pluginSettingsFactory = (PluginSettingsFactory) ctx.getService(settingsRef);
            }
        }
    }

    @Nonnull
    @Override
    public RepositoryHookResult preUpdate(@Nonnull PreRepositoryHookContext context,
                                          @Nonnull PullRequestMergeHookRequest request) {

        ensureServices();

        // If services couldn't be loaded, accept the merge (fail-safe)
        if (pullRequestService == null || contentService == null) {
            return RepositoryHookResult.accepted();
        }

        PullRequest pr = request.getPullRequest();
        Repository repo = pr.getToRef().getRepository();

        // Check settings
        if (pluginSettingsFactory != null) {
            PluginSettings settings = pluginSettingsFactory.createSettingsForKey("com.baml.prplugin.repo." + repo.getId());
            Object val = settings.get(".enabled");
            if (val != null && !Boolean.parseBoolean(val.toString())) {
                return RepositoryHookResult.accepted();
            }
        }

        final List<String> violations = new ArrayList<>();

        // Use streamChanges for Bitbucket 9.x compatibility
        pullRequestService.streamChanges(new PullRequestChangesRequest.Builder(pr).build(), new ChangeCallback() {
            @Override
            public boolean onChange(@Nonnull Change change) {
                String path = change.getPath().toString();
                if (path.toLowerCase().endsWith("web.config")) {
                    scanFile(repo, pr.getFromRef().getLatestCommit(), path, violations);
                }
                return true;
            }
        });

        if (!violations.isEmpty()) {
            return RepositoryHookResult.rejected("Insecure Web Config Detected", violations.get(0));
        }
        return RepositoryHookResult.accepted();
    }

    private void scanFile(Repository repo, String commitId, String path, List<String> violations) {
        contentService.streamFile(repo, commitId, path, new PageRequestImpl(0, 5000), false, new FileContentCallback() {
            @Override
            public boolean onLine(int lineCode, @Nonnull String text, boolean more) {
                if (text.contains("debug=\"true\"")) {
                    violations.add("Line " + lineCode + ": Found debug=\"true\" in " + path);
                    return false;
                }
                return true;
            }
            @Override public void onStart(@Nonnull FileContext fc) {}
            @Override public void onEnd(@Nonnull FileSummary s) {}
            @Override public void onBinary() {}
            @Override public void offerBlame(@Nonnull Page<Blame> p) {}
        });
    }
}