package com.example.rest;

import com.atlassian.sal.api.pluginsettings.PluginSettingsFactory;
import javax.ws.rs.*;
import javax.ws.rs.core.*;
import java.util.Map;

@Path("/settings")
public class SettingsResource {
    private final PluginSettingsFactory settingsFactory;
    private static final String KEY = "scan.debug.enabled";

    public SettingsResource(PluginSettingsFactory settingsFactory) {
        this.settingsFactory = settingsFactory;
    }

    @POST
    @Path("/{type}/{key}")
    @Consumes(MediaType.APPLICATION_JSON)
    public Response saveSettings(@PathParam("type") String type, @PathParam("key") String key, Map<String, String> data) {
        // Saves to Repo ID, Project Key, or 'global'
        settingsFactory.createSettingsForKey(key).put(KEY, data.get("enabled"));
        return Response.ok().build();
    }
}