// ============================================
// SIMPLIFIED BITBUCKET PR COPILOT
// Just 4 commands that actually work
// ============================================

const vscode = require('vscode');
const simpleGit = require('simple-git');

let output;
let git;

// ============================================
// LOGGING
// ============================================
function log(msg) {
  const time = new Date().toISOString();
  output?.appendLine(`[${time}] ${msg}`);
  console.log(msg);
}

// ============================================
// COMMAND 1: EASY SETUP
// ============================================
async function easySetup(context) {
  try {
    log('Starting Easy Setup...');
    
    vscode.window.showInformationMessage('Welcome! Let\'s set up Bitbucket PR Copilot.');
    
    const config = vscode.workspace.getConfiguration('bitbucketPR');
    
    // Step 1: Server URL
    const serverUrl = await vscode.window.showInputBox({
      title: 'Step 1/6: Bitbucket Server URL',
      prompt: 'Enter your Bitbucket Server URL',
      placeHolder: 'http://172.16.16.105:7990',
      value: config.get('serverUrl') || 'http://172.16.16.105:7990',
      ignoreFocusOut: true,
      validateInput: (v) => !v ? 'Required' : null
    });
    if (!serverUrl) return;
    
    // Step 2: Project
    const project = await vscode.window.showInputBox({
      title: 'Step 2/6: Project Key',
      prompt: 'Enter your Bitbucket project key',
      placeHolder: 'DEM',
      value: config.get('project') || '',
      ignoreFocusOut: true,
      validateInput: (v) => !v ? 'Required' : null
    });
    if (!project) return;
    
    // Step 3: Repository
    const repo = await vscode.window.showInputBox({
      title: 'Step 3/6: Repository Name',
      prompt: 'Enter repository name',
      placeHolder: 'demorepo',
      value: config.get('repo') || '',
      ignoreFocusOut: true,
      validateInput: (v) => !v ? 'Required' : null
    });
    if (!repo) return;
    
    // Step 4: Base Branch
    const baseBranch = await vscode.window.showInputBox({
      title: 'Step 4/6: Base Branch',
      prompt: 'Enter default base branch',
      placeHolder: 'master',
      value: config.get('baseBranch') || 'master',
      ignoreFocusOut: true
    });
    if (!baseBranch) return;
    
    // Step 5: Username
    const username = await vscode.window.showInputBox({
      title: 'Step 5/6: Username',
      prompt: 'Enter your Bitbucket username',
      placeHolder: 'your.email@company.com',
      ignoreFocusOut: true,
      validateInput: (v) => !v ? 'Required' : null
    });
    if (!username) return;
    
    // Step 6: Password
    const password = await vscode.window.showInputBox({
      title: 'Step 6/6: Password',
      prompt: 'Enter your password',
      password: true,
      ignoreFocusOut: true,
      validateInput: (v) => !v ? 'Required' : null
    });
    if (!password) return;
    
    // Save configuration
    await config.update('serverUrl', serverUrl, vscode.ConfigurationTarget.Global);
    await config.update('project', project, vscode.ConfigurationTarget.Global);
    await config.update('repo', repo, vscode.ConfigurationTarget.Global);
    await config.update('baseBranch', baseBranch, vscode.ConfigurationTarget.Global);
    
    // Save credentials
    const creds = Buffer.from(`${username}:${password}`).toString('base64');
    await context.secrets.store('bitbucket-auth', creds);
    
    log(`Configuration saved: ${serverUrl}, ${project}/${repo}`);
    
    // Test connection
    vscode.window.showInformationMessage('Testing connection...');
    
    const testResult = await testConnection(serverUrl, creds);
    
    if (testResult.success) {
      const msg = `✅ Setup Complete!

Server: ${serverUrl}
Project: ${project}
Repository: ${repo}
Base Branch: ${baseBranch}
Connected as: ${testResult.user}

Ready to use! 🎉`;
      
      vscode.window.showInformationMessage(msg);
      log('Setup successful!');
    } else {
      vscode.window.showErrorMessage(`Setup completed but connection test failed: ${testResult.error}`);
      log(`Connection test failed: ${testResult.error}`);
    }
    
  } catch (error) {
    vscode.window.showErrorMessage(`Setup failed: ${error.message}`);
    log(`Setup error: ${error.message}`);
  }
}

// ============================================
// COMMAND 2: SHOW STATUS
// ============================================
async function showStatus(context) {
  try {
    log('Checking status...');
    
    const config = vscode.workspace.getConfiguration('bitbucketPR');
    const serverUrl = config.get('serverUrl');
    const project = config.get('project');
    const repo = config.get('repo');
    const baseBranch = config.get('baseBranch');
    
    if (!serverUrl || !project || !repo) {
      vscode.window.showWarningMessage('Not configured. Run "PR Copilot: Easy Setup" first.');
      return;
    }
    
    const creds = await context.secrets.get('bitbucket-auth');
    if (!creds) {
      vscode.window.showWarningMessage('No credentials. Run "PR Copilot: Easy Setup" first.');
      return;
    }
    
    // Get current branch
    const currentBranch = await getCurrentBranch();
    
    // Test connection
    vscode.window.showInformationMessage('Testing connection...');
    const connTest = await testConnection(serverUrl, creds);
    
    if (!connTest.success) {
      vscode.window.showErrorMessage(`Cannot connect to Bitbucket: ${connTest.error}`);
      return;
    }
    
    // Check for PR
    vscode.window.showInformationMessage('Checking for pull request...');
    const prResult = await findPullRequest(serverUrl, project, repo, currentBranch, baseBranch, creds);
    
    // Build status message
    let status = `📊 **Bitbucket PR Status**

**Connection:**
✅ Connected to ${serverUrl}
✅ Authenticated as: ${connTest.user}

**Repository:**
• Project: ${project}
• Repository: ${repo}
• Current Branch: ${currentBranch}
• Base Branch: ${baseBranch}

**Pull Request:**
`;
    
    if (prResult.found) {
      status += `✅ Found PR #${prResult.pr.id}
• Title: ${prResult.pr.title}
• Source: ${prResult.pr.source}
• Destination: ${prResult.pr.destination}
• Status: ${prResult.pr.state}
• URL: ${prResult.pr.url}`;
    } else {
      status += `❌ No pull request found for branch "${currentBranch}"`;
    }
    
    // Show in document
    const doc = await vscode.workspace.openTextDocument({
      content: status,
      language: 'markdown'
    });
    await vscode.window.showTextDocument(doc);
    
    // Offer to create PR if none exists
    if (!prResult.found && currentBranch !== baseBranch) {
      const create = await vscode.window.showInformationMessage(
        `No PR found for branch "${currentBranch}". Create one?`,
        'Yes, Create PR',
        'No'
      );
      
      if (create === 'Yes, Create PR') {
        await createPullRequest(serverUrl, project, repo, currentBranch, baseBranch, creds);
      }
    }
    
  } catch (error) {
    vscode.window.showErrorMessage(`Status check failed: ${error.message}`);
    log(`Status error: ${error.message}`);
  }
}

// ============================================
// COMMAND 3: CHECK CONFIGURATION
// ============================================
async function checkConfiguration(context) {
  try {
    log('Checking configuration...');
    
    const config = vscode.workspace.getConfiguration('bitbucketPR');
    const serverUrl = config.get('serverUrl');
    const project = config.get('project');
    const repo = config.get('repo');
    const baseBranch = config.get('baseBranch');
    const creds = await context.secrets.get('bitbucket-auth');
    
    let report = `🔧 **Configuration Report**

**Settings:**
`;
    
    report += serverUrl ? `✅ Server URL: ${serverUrl}\n` : `❌ Server URL: Not set\n`;
    report += project ? `✅ Project: ${project}\n` : `❌ Project: Not set\n`;
    report += repo ? `✅ Repository: ${repo}\n` : `❌ Repository: Not set\n`;
    report += baseBranch ? `✅ Base Branch: ${baseBranch}\n` : `❌ Base Branch: Not set\n`;
    report += creds ? `✅ Credentials: Stored\n` : `❌ Credentials: Not stored\n`;
    
    report += `\n**Connection Test:**\n`;
    
    if (serverUrl && creds) {
      const test = await testConnection(serverUrl, creds);
      if (test.success) {
        report += `✅ Successfully connected as: ${test.user}\n`;
        report += `✅ Server is reachable\n`;
      } else {
        report += `❌ Connection failed: ${test.error}\n`;
      }
    } else {
      report += `⚠️ Cannot test - missing server URL or credentials\n`;
    }
    
    report += `\n**Git Repository:**\n`;
    const currentBranch = await getCurrentBranch();
    if (currentBranch) {
      report += `✅ Current branch: ${currentBranch}\n`;
    } else {
      report += `❌ Not in a Git repository\n`;
    }
    
    // Show report
    const doc = await vscode.workspace.openTextDocument({
      content: report,
      language: 'markdown'
    });
    await vscode.window.showTextDocument(doc);
    
    // Summary notification
    const allGood = serverUrl && project && repo && baseBranch && creds;
    if (allGood) {
      vscode.window.showInformationMessage('✅ Configuration is complete and valid!');
    } else {
      vscode.window.showWarningMessage('⚠️ Configuration incomplete. Run "PR Copilot: Easy Setup"');
    }
    
  } catch (error) {
    vscode.window.showErrorMessage(`Configuration check failed: ${error.message}`);
    log(`Check config error: ${error.message}`);
  }
}

// ============================================
// COMMAND 4: REVIEW & POST
// ============================================
async function reviewAndPost(context) {
  try {
    log('Starting review and post...');
    
    // 1. Check configuration
    const config = vscode.workspace.getConfiguration('bitbucketPR');
    const serverUrl = config.get('serverUrl');
    const project = config.get('project');
    const repo = config.get('repo');
    const baseBranch = config.get('baseBranch');
    const creds = await context.secrets.get('bitbucket-auth');
    
    if (!serverUrl || !project || !repo || !creds) {
      vscode.window.showWarningMessage('Not configured. Run "PR Copilot: Easy Setup" first.');
      return;
    }
    
    // 2. Get current branch
    const currentBranch = await getCurrentBranch();
    if (!currentBranch) {
      vscode.window.showErrorMessage('Not in a Git repository');
      return;
    }
    
    // 3. Find or create PR
    vscode.window.showInformationMessage('Looking for pull request...');
    let prResult = await findPullRequest(serverUrl, project, repo, currentBranch, baseBranch, creds);
    
    if (!prResult.found) {
      const create = await vscode.window.showInformationMessage(
        `No PR found. Create one first?`,
        'Yes, Create PR',
        'Cancel'
      );
      
      if (create !== 'Yes, Create PR') {
        return;
      }
      
      const created = await createPullRequest(serverUrl, project, repo, currentBranch, baseBranch, creds);
      if (!created) {
        vscode.window.showErrorMessage('Failed to create PR');
        return;
      }
      
      // Fetch the newly created PR
      prResult = await findPullRequest(serverUrl, project, repo, currentBranch, baseBranch, creds);
      if (!prResult.found) {
        vscode.window.showErrorMessage('PR created but could not retrieve it');
        return;
      }
    }
    
    // 4. Choose review type
    const reviewType = await vscode.window.showQuickPick([
      {
        label: '📄 File Review',
        description: 'Review current open file with Copilot Chat',
        value: 'file'
      },
      {
        label: '🔄 PR Diff Review',
        description: 'Seamless integration using a temporary diff file',
        value: 'diff'
      },
      {
        label: '✅ JIRA Acceptance Criteria',
        description: 'Compare PR against JIRA acceptance criteria',
        value: 'jira'
      }
    ], {
      title: 'Select Review Type',
      placeHolder: 'How do you want to review this PR?'
    });
    
    if (!reviewType) {
      return;
    }
    
    let reviewTitle = '';
    
    // 5. Execute the selected review type
    if (reviewType.value === 'file') {
      // File Review
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showErrorMessage('No file open. Please open a file to review.');
        return;
      }
      
      const fileName = vscode.workspace.asRelativePath(editor.document.fileName);
      const fileContent = editor.document.getText();
      
      reviewTitle = `📄 File Review: ${fileName}`;
      
      vscode.window.showInformationMessage(
        'Copy this prompt to Copilot Chat, then paste the response back here.',
        'Copy Prompt'
      ).then(async (action) => {
        if (action === 'Copy Prompt') {
          const prompt = `Please review this file for:
- Code quality issues
- Security vulnerabilities
- Performance problems
- Best practices violations
- Potential bugs

File: ${fileName}

\`\`\`
${fileContent}
\`\`\`

Provide specific, actionable feedback with line numbers where applicable.`;
          
          await vscode.env.clipboard.writeText(prompt);
          vscode.window.showInformationMessage('✅ Prompt copied! Paste it in Copilot Chat, then come back here.');
          
          // Wait for user to get review from Copilot
          const review = await vscode.window.showInputBox({
            title: 'Paste Copilot Chat Response',
            prompt: 'Paste the review from Copilot Chat here',
            placeHolder: 'Paste Copilot response...',
            ignoreFocusOut: true,
            multiline: true
          });
          
          if (review) {
            const formattedComment = `## ${reviewTitle}

${review}

---
*Review generated by Copilot Chat and posted via PR Copilot Extension*`;
            
            await postComment(serverUrl, project, repo, prResult.pr.id, formattedComment, creds);
            vscode.window.showInformationMessage(
              `✅ File review posted to PR #${prResult.pr.id}!`,
              'Open PR'
            ).then(action => {
              if (action === 'Open PR') {
                vscode.env.openExternal(vscode.Uri.parse(prResult.pr.url));
              }
            });
          }
        }
      });
      
    } else if (reviewType.value === 'diff') {
      // --- INTEGRATED SEAMLESS DIFF LOGIC ---
      vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Fetching PR Diff Context...",
        cancellable: false
      }, async (progress) => {
        try {
          const diffText = await getPRDiff(serverUrl, project, repo, prResult.pr.id, creds);
          
          if (!diffText) {
            vscode.window.showErrorMessage('Failed to get PR diff.');
            return;
          }

          const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
          if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder open.');
            return;
          }

          // 1. Create a temporary file in the workspace
          const tempFileName = '.pr_review_context.diff';
          const tempUri = vscode.Uri.joinPath(workspaceFolder.uri, tempFileName);
          await vscode.workspace.fs.writeFile(tempUri, Buffer.from(diffText, 'utf8'));

          // 2. Open the file to give Copilot immediate visibility
          const doc = await vscode.workspace.openTextDocument(tempUri);
          await vscode.window.showTextDocument(doc, { preview: true, viewColumn: vscode.ViewColumn.Beside });

          // 3. Prepare the Magic Command
          const chatCommand = `@workspace /explain #file:${tempFileName} Please perform a code review of this PR diff. Look for bugs, security risks, and performance issues.`;
          await vscode.env.clipboard.writeText(chatCommand);

          reviewTitle = `🔄 PR Diff Review: ${prResult.pr.title}`;

          vscode.window.showInformationMessage(
            `✅ Diff context ready! Command copied to clipboard.`,
            'Open Chat'
          ).then(selection => {
            if (selection === 'Open Chat') {
              vscode.commands.executeCommand('workbench.panel.chat.view.focus');
            }
          });

          // 4. Capture response
          const review = await vscode.window.showInputBox({
            title: 'Paste Copilot Chat Response',
            prompt: 'After Copilot finishes, paste the review here to post to Bitbucket',
            ignoreFocusOut: true,
            multiline: true
          });

          if (review) {
            const formattedComment = `## ${reviewTitle}\n\n${review}\n\n---\n*Review via PR Copilot*`;
            const posted = await postComment(serverUrl, project, repo, prResult.pr.id, formattedComment, creds);
            
            if (posted) {
              vscode.window.showInformationMessage(`✅ Review posted to PR #${prResult.pr.id}!`);
              // Cleanup
              try { await vscode.workspace.fs.delete(tempUri); } catch(e) {}
            }
          }
        } catch (err) {
          log(`Diff Review Error: ${err.message}`);
          vscode.window.showErrorMessage('Review failed: ' + err.message);
        }
      });
      // --- END SEAMLESS DIFF LOGIC ---
      
    } else if (reviewType.value === 'jira') {
      // JIRA Acceptance Criteria Review
      const jiraTicket = extractJiraTicket(currentBranch) || extractJiraTicket(prResult.pr.title);
      
      if (!jiraTicket) {
        vscode.window.showWarningMessage('No JIRA ticket found in branch name or PR title.');
        return;
      }
      
      let jiraUrl = config.get('jiraUrl');
      if (!jiraUrl) {
        jiraUrl = await vscode.window.showInputBox({
          title: 'JIRA Configuration',
          prompt: 'Enter your JIRA instance URL',
          ignoreFocusOut: true,
          validateInput: (v) => !v ? 'JIRA URL is required' : null
        });
        if (!jiraUrl) return;
        await config.update('jiraUrl', jiraUrl, vscode.ConfigurationTarget.Global);
      }
      
      let jiraCreds = await context.secrets.get('jira-auth');
      if (!jiraCreds) {
        const jiraUsername = await vscode.window.showInputBox({ title: 'JIRA Username', prompt: 'Enter JIRA username', ignoreFocusOut: true });
        if (!jiraUsername) return;
        const jiraPassword = await vscode.window.showInputBox({ title: 'JIRA Password', prompt: 'Enter password/token', password: true, ignoreFocusOut: true });
        if (!jiraPassword) return;
        const jiraCredsBase64 = Buffer.from(`${jiraUsername}:${jiraPassword}`).toString('base64');
        await context.secrets.store('jira-auth', jiraCredsBase64);
        jiraCreds = jiraCredsBase64;
      }
      
      vscode.window.showInformationMessage(`Fetching JIRA ticket ${jiraTicket}...`);
      const jiraData = await fetchJiraTicket(jiraUrl, jiraTicket, jiraCreds);
      
      if (!jiraData) {
        vscode.window.showErrorMessage(`Failed to fetch JIRA ticket ${jiraTicket}.`);
        return;
      }
      
      const acceptanceCriteria = jiraData.acceptanceCriteria || jiraData.description || 'No criteria found';
      const diff = await getPRDiff(serverUrl, project, repo, prResult.pr.id, creds);
      
      reviewTitle = `✅ JIRA Acceptance Criteria Review: ${jiraTicket}`;
      
      vscode.window.showInformationMessage('Copy prompt to Copilot Chat', 'Copy Prompt').then(async (action) => {
        if (action === 'Copy Prompt') {
          const prompt = `Compare this PR against JIRA criteria:\n\nJIRA: ${jiraTicket}\nAC:\n${acceptanceCriteria}\n\nPR Diff:\n\`\`\`diff\n${diff}\n\`\`\``;
          await vscode.env.clipboard.writeText(prompt);
          const review = await vscode.window.showInputBox({ title: 'Paste Copilot Response', multiline: true, ignoreFocusOut: true });
          if (review) {
            const formattedComment = `## ${reviewTitle}\n\n${review}\n\n---\n*JIRA Review via PR Copilot*`;
            await postComment(serverUrl, project, repo, prResult.pr.id, formattedComment, creds);
            vscode.window.showInformationMessage('✅ JIRA review posted!');
          }
        }
      });
    }
    
  } catch (error) {
    vscode.window.showErrorMessage(`Review & post failed: ${error.message}`);
    log(`Review error: ${error.message}`);
  }
}

// ============================================
// HELPER FUNCTIONS
// ============================================

async function testConnection(serverUrl, authBase64) {
  try {
    const response = await fetch(`${serverUrl}/rest/api/1.0/application-properties`, {
      headers: {
        'Authorization': `Basic ${authBase64}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      return { 
        success: true, 
        user: data.authenticatedUser?.displayName || 'Unknown' 
      };
    } else {
      return { 
        success: false, 
        error: `HTTP ${response.status}` 
      };
    }
  } catch (error) {
    return { 
      success: false, 
      error: error.message 
    };
  }
}

async function getCurrentBranch() {
  try {
    if (!git) return null;
    const status = await git.status();
    return status.current;
  } catch (error) {
    log(`Get branch error: ${error.message}`);
    return null;
  }
}

async function findPullRequest(serverUrl, project, repo, sourceBranch, targetBranch, authBase64) {
  try {
    const url = `${serverUrl}/rest/api/1.0/projects/${project}/repos/${repo}/pull-requests?state=OPEN`;
    
    const response = await fetch(url, {
      headers: {
        'Authorization': `Basic ${authBase64}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      return { found: false, error: `HTTP ${response.status}` };
    }
    
    const data = await response.json();
    const prs = data.values || [];
    
    const pr = prs.find(p => 
      p.fromRef.displayId === sourceBranch && 
      p.toRef.displayId === targetBranch
    );
    
    if (pr) {
      return {
        found: true,
        pr: {
          id: pr.id,
          title: pr.title,
          source: pr.fromRef.displayId,
          destination: pr.toRef.displayId,
          state: pr.state,
          url: pr.links.self[0].href
        }
      };
    }
    
    return { found: false };
  } catch (error) {
    return { found: false, error: error.message };
  }
}

async function createPullRequest(serverUrl, project, repo, sourceBranch, targetBranch, authBase64) {
  try {
    const title = await vscode.window.showInputBox({
      prompt: 'Enter PR title',
      placeHolder: `Merge ${sourceBranch} into ${targetBranch}`,
      ignoreFocusOut: true
    });
    
    if (!title) return false;
    
    const description = await vscode.window.showInputBox({
      prompt: 'Enter PR description (optional)',
      placeHolder: 'Description...',
      ignoreFocusOut: true
    });
    
    const url = `${serverUrl}/rest/api/1.0/projects/${project}/repos/${repo}/pull-requests`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Basic ${authBase64}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        title,
        description: description || '',
        fromRef: { id: `refs/heads/${sourceBranch}` },
        toRef: { id: `refs/heads/${targetBranch}` }
      })
    });
    
    if (response.ok) {
      const pr = await response.json();
      vscode.window.showInformationMessage(`✅ PR #${pr.id} created!`);
      log(`PR created: ${pr.id}`);
      return true;
    } else {
      const error = await response.text();
      vscode.window.showErrorMessage(`Failed to create PR: ${error}`);
      return false;
    }
  } catch (error) {
    vscode.window.showErrorMessage(`Create PR error: ${error.message}`);
    return false;
  }
}

async function postComment(serverUrl, project, repo, prId, comment, authBase64) {
  try {
    const url = `${serverUrl}/rest/api/1.0/projects/${project}/repos/${repo}/pull-requests/${prId}/comments`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Basic ${authBase64}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ text: comment })
    });
    
    if (response.ok) {
      log(`Comment posted to PR ${prId}`);
      return true;
    } else {
      const error = await response.text();
      log(`Post comment failed: ${error}`);
      return false;
    }
  } catch (error) {
    log(`Post comment error: ${error.message}`);
    return false;
  }
}

async function getPRDiff(serverUrl, project, repo, prId, authBase64) {
  try {
    const url = `${serverUrl}/rest/api/1.0/projects/${project}/repos/${repo}/pull-requests/${prId}/diff`;
    
    log(`Fetching PR diff from: ${url}`);
    
    const response = await fetch(url, {
      headers: {
        'Authorization': `Basic ${authBase64}`,
        'Accept': 'text/plain'
      }
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      log(`Failed to get diff: ${response.status} - ${errorText}`);
      return null;
    }
    
    const diffResponse = await response.text();
    
    if (!diffResponse || diffResponse.length === 0) {
      log('WARNING: Diff is empty!');
      return 'No changes in this PR (empty diff)';
    }
    
    return diffResponse;
    
  } catch (error) {
    log(`Get diff error: ${error.message}`);
    return null;
  }
}

function parseDiffToChunks(diffText) {
  const chunks = [];
  const lines = diffText.split('\n');
  let currentFile = null;
  let currentChunk = null;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    if (line.startsWith('diff --git')) {
      if (currentChunk && currentChunk.lines.length > 0) {
        chunks.push(currentChunk);
      }
      const fileMatch = line.match(/diff --git src:\/\/(.+?) dst:\/\/(.+)/);
      if (fileMatch) {
        currentFile = fileMatch[2];
        currentChunk = { file: currentFile, lines: [line] };
      } else {
        const standardMatch = line.match(/diff --git a\/(.+?) b\/(.+)/);
        if (standardMatch) {
          currentFile = standardMatch[2];
          currentChunk = { file: currentFile, lines: [line] };
        }
      }
    }
    else if (currentChunk) {
      currentChunk.lines.push(line);
    }
  }
  
  if (currentChunk && currentChunk.lines.length > 0) {
    chunks.push(currentChunk);
  }
  
  return chunks;
}

function formatDiffForCopilot(chunks) {
  if (chunks.length === 0) return 'No changes found in PR diff.';
  const sections = [];
  for (const chunk of chunks) {
    if (chunk.lines.length > 0 && chunk.file) {
      sections.push(`## File: ${chunk.file}`);
      sections.push('```diff');
      sections.push(...chunk.lines);
      sections.push('```\n');
    }
  }
  return sections.join('\n');
}

function extractJiraTicket(text) {
  if (!text) return null;
  const match = text.match(/([A-Z]+)-(\d+)/);
  return match ? match[0] : null;
}

async function fetchJiraTicket(jiraUrl, ticketId, authBase64) {
  try {
    const baseUrl = jiraUrl.replace(/\/$/, '');
    const endpoints = [`${baseUrl}/rest/api/3/issue/${ticketId}`, `${baseUrl}/rest/api/2/issue/${ticketId}`];
    let response, data;
    
    for (const url of endpoints) {
      try {
        response = await fetch(url, { headers: { 'Authorization': `Basic ${authBase64}`, 'Content-Type': 'application/json' } });
        if (response.ok) { data = await response.json(); break; }
      } catch (e) { continue; }
    }
    
    if (!data) return null;
    const fields = data.fields;
    return {
      key: data.key,
      summary: fields.summary,
      description: fields.description ? extractTextFromField(fields.description) : '',
      acceptanceCriteria: extractTextFromField(fields.customfield_10000) || 'No criteria found',
      status: fields.status.name
    };
  } catch (e) { return null; }
}

function extractTextFromField(field) {
  if (!field) return '';
  if (typeof field === 'string') return field;
  if (field.type === 'doc' && field.content) return extractTextFromADF(field.content);
  return JSON.stringify(field);
}

function extractTextFromADF(content) {
  let text = '';
  for (const node of content) {
    if (node.type === 'paragraph' && node.content) {
      for (const item of node.content) if (item.text) text += item.text;
      text += '\n';
    }
  }
  return text.trim();
}

function activate(context) {
  output = vscode.window.createOutputChannel('PR Copilot');
  log('PR Copilot activated');
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (workspaceFolders) git = simpleGit(workspaceFolders[0].uri.fsPath);
  
  context.subscriptions.push(
    vscode.commands.registerCommand('bitbucketPR.easySetup', () => easySetup(context)),
    vscode.commands.registerCommand('bitbucketPR.showStatus', () => showStatus(context)),
    vscode.commands.registerCommand('bitbucketPR.checkConfig', () => checkConfiguration(context)),
    vscode.commands.registerCommand('bitbucketPR.reviewAndPost', () => reviewAndPost(context))
  );
}

function deactivate() { log('PR Copilot deactivated'); }

module.exports = { activate, deactivate };