# 1. Define the Root Project Folder
$root = "pr-debug-scanner"
New-Item -ItemType Directory -Path "$root\src\main\java\com\example\service" -Force
New-Item -ItemType Directory -Path "$root\src\main\java\com\example\hooks" -Force
New-Item -ItemType Directory -Path "$root\src\main\java\com\example\rest" -Force
New-Item -ItemType Directory -Path "$root\src\main\resources\templates" -Force
New-Item -ItemType Directory -Path "$root\src\main\resources\js" -Force

# 2. Create pom.xml
$pomContent = @'
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/maven-v4_0_0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example.bitbucket</groupId>
    <artifactId>pr-debug-scanner</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <packaging>atlassian-plugin</packaging>
    <properties>
        <bitbucket.version>8.19.0</bitbucket.version>
        <amps.version>8.12.0</amps.version>
    </properties>
    <dependencies>
        <dependency><groupId>com.atlassian.bitbucket.server</groupId><artifactId>bitbucket-api</artifactId><version>${bitbucket.version}</version><scope>provided</scope></dependency>
        <dependency><groupId>com.atlassian.sal</groupId><artifactId>sal-api</artifactId><version>4.0.0</version><scope>provided</scope></dependency>
        <dependency><groupId>junit</groupId><artifactId>junit</artifactId><version>4.13.2</version><scope>test</scope></dependency>
        <dependency><groupId>org.mockito</groupId><artifactId>mockito-core</artifactId><version>4.8.0</version><scope>test</scope></dependency>
    </dependencies>
    <build>
        <plugins>
            <plugin><groupId>com.atlassian.maven.plugins</groupId><artifactId>bitbucket-maven-plugin</artifactId><version>${amps.version}</version><extensions>true</extensions></plugin>
            <plugin><groupId>com.atlassian.maven.plugins</groupId><artifactId>clover-maven-plugin</artifactId><version>4.1.2</version>
                <configuration><targetPercentage>80%</targetPercentage></configuration>
            </plugin>
        </plugins>
    </build>
</project>
'@
$pomContent | Out-File -FilePath "$root\pom.xml" -Encoding utf8

# 3. Create atlassian-plugin.xml
$pluginXml = @'
<atlassian-plugin key="com.example.debug-scan" name="Debug Veto Plugin" plugins-version="2">
    <plugin-info><version>1.0.0</version></plugin-info>
    <repository-merge-check key="debug-check" class="com.example.hooks.DebugMergeCheck" name="PR Scan Check"/>
    <rest key="settings-rest" path="/scan-settings" version="1.0"><package>com.example.rest</package></rest>
</atlassian-plugin>
'@
$pluginXml | Out-File -FilePath "$root\src\main\resources\atlassian-plugin.xml" -Encoding utf8

# 4. Create SettingsService.java
$serviceJava = @'
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
'@
$serviceJava | Out-File -FilePath "$root\src\main\java\com\example\service\SettingsService.java" -Encoding utf8

# 5. Create DebugMergeCheck.java
$checkJava = @'
package com.example.hooks;
import com.atlassian.bitbucket.hook.repository.*;
import com.atlassian.bitbucket.content.ContentService;
import com.example.service.SettingsService;
import java.io.*;
public class DebugMergeCheck implements RepositoryMergeCheck {
    private final ContentService contentService;
    private final SettingsService settingsService;
    public DebugMergeCheck(ContentService cs, SettingsService ss) { this.contentService = cs; this.settingsService = ss; }
    @Override
    public void check(MergeCheckContext context) {
        Repository repo = context.getPullRequest().getToRef().getRepository();
        if (!settingsService.isEnabled(repo)) return;
        try (InputStream is = contentService.getRaw(repo, "web.config", null)) {
            BufferedReader reader = new BufferedReader(new InputStreamReader(is));
            if (reader.lines().anyMatch(l -> l.contains("debug=\"true\""))) {
                context.getDecision().veto("Security Policy Failure", "debug=\"true\" detected in web.config.");
            }
        } catch (Exception ignored) {}
    }
}
'@
$checkJava | Out-File -FilePath "$root\src\main\java\com\example\hooks\DebugMergeCheck.java" -Encoding utf8

Write-Host "Success! Folder structure and files created in: $root" -ForegroundColor Green