package com.example.service;

import com.atlassian.bitbucket.repository.Repository;
import com.atlassian.plugin.spring.scanner.annotation.imports.ComponentImport;
import com.atlassian.sal.api.pluginsettings.PluginSettingsFactory;
import jakarta.inject.Inject; // Added
import jakarta.inject.Named;
import jakarta.inject.Singleton;

@Named("settingsService")
@Singleton
public class SettingsService {
    private final PluginSettingsFactory factory;
    private static final String KEY = "scan.debug.enabled";

    @Inject // Added
    public SettingsService(@ComponentImport PluginSettingsFactory factory) {
        this.factory = factory;
    }
    private final PluginSettingsFactory factory;
    private static final String KEY = "scan.debug.enabled";

    @Inject
    public SettingsService(@ComponentImport PluginSettingsFactory factory) {
        this.factory = factory;
    }

    public String getRepoSettingRaw(Repository repo) {
        Object v = factory.createSettingsForKey(String.valueOf(repo.getId())).get(KEY);
        return v == null ? null : v.toString();
    }

    public void setRepoSettingRaw(String repoId, String value) {
        factory.createSettingsForKey(repoId).put(KEY, value);
    }

    public boolean isEnabled(Repository repo) {
        Object v = factory.createSettingsForKey(String.valueOf(repo.getId())).get(KEY);
        if (v != null && !"INHERIT".equals(v)) {
            return Boolean.parseBoolean(v.toString());
        }
        v = factory.createSettingsForKey(repo.getProject().getKey()).get(KEY);
        if (v != null && !"INHERIT".equals(v)) {
            return Boolean.parseBoolean(v.toString());
        }
        return false;
    }
}