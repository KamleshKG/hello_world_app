package com.company.bitbucket.hook;

import com.atlassian.bitbucket.hook.repository.*;
import com.atlassian.bitbucket.content.*;
import com.atlassian.bitbucket.repository.*;
import com.atlassian.bitbucket.setting.*;
import com.atlassian.bitbucket.io.TypeAwareOutputSupplier;
import com.atlassian.plugin.spring.scanner.annotation.imports.ComponentImport;

import javax.annotation.Nonnull;
import java.io.IOException;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;
import java.util.regex.PatternSyntaxException;

/**
 * Bitbucket Server Pre-Merge Hook for Bitbucket 9.4.16
 * Scans repository files directly for debug configurations
 */
public class DebugConfigVetoHook implements PreRepositoryHook<RepositoryHookRequest> {

    private final ContentService contentService;

    // Config file patterns to scan
    private static final String[] CONFIG_FILES = {
        "web.config",
        "Web.config",
        "appsettings.json",
        "settings.py",
        "config.py",
        ".env"
    };

    // Debug detection patterns
    private static final String[] DEBUG_PATTERNS = {
        "debug\\s*=\\s*[Tt]rue",
        "DEBUG\\s*=\\s*[Tt]rue",
        "\"debug\"\\s*:\\s*true",
        "'debug'\\s*:\\s*true",
        "<compilation\\s+debug\\s*=\\s*\"true\""
    };

    public DebugConfigVetoHook(@ComponentImport ContentService contentService) {
        this.contentService = contentService;
    }

    @Nonnull
    @Override
    public RepositoryHookResult preUpdate(@Nonnull PreRepositoryHookContext context,
                                          @Nonnull RepositoryHookRequest request) {
        
        // Get the refs being updated
        List<RefChange> refChanges = new ArrayList<>();
        request.getRefChanges().forEach(refChanges::add);
        
        if (refChanges.isEmpty()) {
            return RepositoryHookResult.accepted();
        }

        List<Violation> violations = new ArrayList<>();

        // Scan each ref change
        for (RefChange refChange : refChanges) {
            if (refChange.getToHash() != null && !refChange.getToHash().isEmpty()) {
                scanCommit(request.getRepository(), refChange.getToHash(), violations);
            }
        }

        // Handle violations
        if (!violations.isEmpty()) {
            String message = buildViolationMessage(violations);
            return RepositoryHookResult.rejected("Debug Configuration Violation", message);
        }

        return RepositoryHookResult.accepted();
    }

    private void scanCommit(Repository repository, String commitId, List<Violation> violations) {
        // Compile debug patterns once
        List<Pattern> debugPatterns = new ArrayList<>();
        for (String patternStr : DEBUG_PATTERNS) {
            try {
                debugPatterns.add(Pattern.compile(patternStr, Pattern.CASE_INSENSITIVE));
            } catch (PatternSyntaxException e) {
                // Skip invalid patterns
            }
        }

        // Try to read each known config file
        for (String configFile : CONFIG_FILES) {
            try {
                String content = readFile(repository, commitId, configFile);
                if (content != null) {
                    scanFileContent(configFile, content, debugPatterns, violations);
                }
            } catch (Exception e) {
                // File doesn't exist or can't be read - that's OK
            }
        }

        // Also try common paths
        String[] commonPaths = {
            "web.config",
            "src/web.config",
            "Web.config",
            "appsettings.json",
            "appsettings.Development.json",
            "settings.py",
            "config/settings.py",
            "config.py",
            ".env",
            "config/.env"
        };

        for (String path : commonPaths) {
            try {
                String content = readFile(repository, commitId, path);
                if (content != null) {
                    scanFileContent(path, content, debugPatterns, violations);
                }
            } catch (Exception e) {
                // File doesn't exist - ignore
            }
        }
    }

    private String readFile(Repository repository, String commitId, String path) throws IOException {
        final StringBuilder content = new StringBuilder();
        
        try {
            contentService.streamFile(repository, commitId, path, new TypeAwareOutputSupplier() {
                @Override
                public OutputStream getStream(String contentType) throws IOException {
                    return new OutputStream() {
                        @Override
                        public void write(int b) throws IOException {
                            content.append((char) b);
                        }
                        
                        @Override
                        public void write(byte[] b, int off, int len) throws IOException {
                            content.append(new String(b, off, len, "UTF-8"));
                        }
                    };
                }
            });
            
            return content.toString();
        } catch (Exception e) {
            // File not found or not readable
            return null;
        }
    }

    private void scanFileContent(String filePath, String content, List<Pattern> debugPatterns, List<Violation> violations) {
        if (content == null || content.isEmpty()) {
            return;
        }

        String[] lines = content.split("\n");
        for (int i = 0; i < lines.length; i++) {
            String line = lines[i];
            
            for (Pattern pattern : debugPatterns) {
                if (pattern.matcher(line).find()) {
                    violations.add(new Violation(filePath, i + 1, line.trim()));
                    break; // Only report one violation per line
                }
            }
        }
    }

    private String buildViolationMessage(List<Violation> violations) {
        StringBuilder message = new StringBuilder();
        
        message.append("MERGE BLOCKED - Debug Configuration Detected\n\n");
        message.append("Debug mode is enabled in configuration files.\n");
        message.append("Production code must not contain debug settings.\n\n");
        
        message.append(String.format("Found %d violation(s):\n\n", violations.size()));

        int count = 1;
        for (Violation violation : violations) {
            message.append(String.format("%d. File: %s\n", count++, violation.filePath));
            message.append(String.format("   Line %d: %s\n\n", violation.lineNumber, violation.content));
        }

        message.append("Required Actions:\n");
        message.append("1. Change debug=True to debug=False\n");
        message.append("2. Set DEBUG = False in settings\n");
        message.append("3. Remove debug flags from production configs\n");
        message.append("4. Ensure all configurations are production-ready\n");

        return message.toString();
    }

    private static class Violation {
        final String filePath;
        final int lineNumber;
        final String content;

        Violation(String filePath, int lineNumber, String content) {
            this.filePath = filePath;
            this.lineNumber = lineNumber;
            this.content = content;
        }
    }
}
