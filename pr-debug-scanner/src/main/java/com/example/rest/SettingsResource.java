package com.example.rest;

import com.example.service.SettingsService;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.inject.Inject;
import jakarta.inject.Named;

import java.util.Map;

@Path("/settings")
@Produces(MediaType.APPLICATION_JSON)
@Named // Added
public class SettingsResource {
    private final SettingsService settingsService;

    @Inject // Added
    public SettingsResource(SettingsService settingsService) {
        this.settingsService = settingsService;
    }
    private final SettingsService settingsService;

    public SettingsResource(SettingsService settingsService) {
        this.settingsService = settingsService;
    }

    @POST
    @Path("/repo/{repoId}")
    @Consumes(MediaType.APPLICATION_JSON)
    public Response saveRepo(@PathParam("repoId") String repoId, Map<String, String> data) {
        String enabled = data == null ? null : data.get("enabled");
        if (enabled == null) {
            return Response.status(Response.Status.BAD_REQUEST)
                    .entity(Map.of("error", "Missing 'enabled'"))
                    .build();
        }

        if (!"true".equals(enabled) && !"false".equals(enabled) && !"INHERIT".equals(enabled)) {
            return Response.status(Response.Status.BAD_REQUEST)
                    .entity(Map.of("error", "enabled must be one of: true, false, INHERIT"))
                    .build();
        }

        settingsService.setRepoSettingRaw(repoId, enabled);
        return Response.ok(Map.of("status", "ok")).build();
    }
}