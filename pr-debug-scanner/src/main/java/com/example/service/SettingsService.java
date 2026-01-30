package com.example.service;
import com.atlassian.bitbucket.repository.Repository;
import com.atlassian.sal.api.pluginsettings.PluginSettingsFactory;
public class SettingsService {
    private final PluginSettingsFactory factory;
    private static final String KEY = "scan.debug.enabled";
    public SettingsService(PluginSettingsFactory factory) { this.factory = factory; }
    public boolean isEnabled(Repository repo) {
        Object v = factory.createSettingsForKey(repo.getId()+"").get(KEY);
        if (v != null && !"INHERIT".equals(v)) return Boolean.parseBoolean(v.toString());
        v = factory.createSettingsForKey(repo.getProject().getKey()).get(KEY);
        if (v != null && !"INHERIT".equals(v)) return Boolean.parseBoolean(v.toString());
        v = factory.createGlobalSettings().get(KEY);
        return v != null && Boolean.parseBoolean(v.toString());
    }
}
