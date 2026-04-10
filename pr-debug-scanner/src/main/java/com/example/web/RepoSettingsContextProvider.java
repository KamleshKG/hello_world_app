package com.example.web;

import com.atlassian.bitbucket.repository.Repository;
import com.atlassian.plugin.PluginParseException;
import com.atlassian.plugin.web.ContextProvider;
import com.example.service.SettingsService;
import com.google.common.collect.Maps;

import java.util.Map;

public class RepoSettingsContextProvider implements ContextProvider {
    private final SettingsService settingsService;

    public RepoSettingsContextProvider(SettingsService settingsService) {
        this.settingsService = settingsService;
    }

    @Override
    public void init(Map<String, String> params) throws PluginParseException {
        // No initialization needed
    }

    @Override
    public Map<String, Object> getContextMap(Map<String, Object> context) {
        Map<String, Object> result = Maps.newHashMap();

        Repository repo = (Repository) context.get("repository");
        if (repo != null) {
            String raw = settingsService.getRepoSettingRaw(repo);
            result.put("enabled", raw != null ? raw : "INHERIT");
        } else {
            result.put("enabled", "INHERIT");
        }

        return result;
    }
}