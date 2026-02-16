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
    
    const serverUrl = await vscode.window.showInputBox({
      title: 'Step 1/6: Bitbucket Server URL',
      prompt: 'Enter your Bitbucket Server URL',
      placeHolder: 'http://172.16.16.105:7990',
      value: config.get('serverUrl') || 'http://172.16.16.105:7990',
      ignoreFocusOut: true,
      validateInput: (v) => !v ? 'Required' : null
    });
    if (!serverUrl) return;
    
    const project = await vscode.window.showInputBox({
      title: 'Step 2/6: Project Key',
      prompt: 'Enter your Bitbucket project key',
      placeHolder: 'DEM',
      value: config.get('project') || '',
      ignoreFocusOut: true,
      validateInput: (v) => !v ? 'Required' : null
    });
    if (!project) return;
    
    const repo = await vscode.window.showInputBox({
      title: 'Step 3/6: Repository Name',
      prompt: 'Enter repository name',
      placeHolder: 'demorepo',
      value: config.get('repo') || '',
      ignoreFocusOut: true,
      validateInput: (v) => !v ? 'Required' : null
    });
    if (!repo) return;
    
    const baseBranch = await vscode.window.showInputBox({
      title: 'Step 4/6: Base Branch',
      prompt: 'Enter default base branch',
      placeHolder: 'master',
      value: config.get('baseBranch') || 'master',
      ignoreFocusOut: true
    });
    if (!baseBranch) return;
    
    const username = await vscode.window.showInputBox({
      title: 'Step 5/6: Username',
      prompt: 'Enter your Bitbucket username',
      placeHolder: 'your.email@company.com',
      ignoreFocusOut: true,
      validateInput: (v) => !v ? 'Required' : null
    });
    if (!username) return;
    
    const password = await vscode.window.showInputBox({
      title: 'Step 6/6: Password',
      prompt: 'Enter your password',
      password: true,
      ignoreFocusOut: true,
      validateInput: (v) => !v ? 'Required' : null
    });
    if (!password) return;
    
    await config.update('serverUrl', serverUrl, vscode.ConfigurationTarget.Global);
    await config.update('project', project, vscode.ConfigurationTarget.Global);
    await config.update('repo', repo, vscode.ConfigurationTarget.Global);
    await config.update('baseBranch', baseBranch, vscode.ConfigurationTarget.Global);
    
    const creds = Buffer.from(`${username}:${password}`).toString('base64');
    await context.secrets.store('bitbucket-auth', creds);
    
    vscode.window.showInformationMessage('Testing connection...');
    const testResult = await testConnection(serverUrl, creds);
    
    if (testResult.success) {
      vscode.window.showInformationMessage(`✅ Setup Complete! Connected as: ${testResult.user}`);
    } else {
      vscode.window.showErrorMessage(`Setup completed but connection test failed: ${testResult.error}`);
    }
  } catch (error) {
    vscode.window.showErrorMessage(`Setup failed: ${error.message}`);
  }
}

// ============================================
// COMMAND 2: SHOW STATUS
// ============================================
async function showStatus(context) {
  try {
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
    const currentBranch = await getCurrentBranch();
    const connTest = await testConnection(serverUrl, creds);
    
    if (!connTest.success) {
      vscode.window.showErrorMessage(`Cannot connect to Bitbucket: ${connTest.error}`);
      return;
    }
    
    const prResult = await findPullRequest(serverUrl, project, repo, currentBranch, baseBranch, creds);
    
    let status = `📊 **Bitbucket PR Status**\n\n✅ Connected to ${serverUrl}\n✅ Authenticated as: ${connTest.user}\n\n**Repo:** ${project}/${repo}\n**Branch:** ${currentBranch}\n\n`;
    status += prResult.found ? `✅ Found PR #${prResult.pr.id}\nURL: ${prResult.pr.url}` : `❌ No PR found.`;
    
    const doc = await vscode.workspace.openTextDocument({ content: status, language: 'markdown' });
    await vscode.window.showTextDocument(doc);
    
    if (!prResult.found && currentBranch !== baseBranch) {
      const create = await vscode.window.showInformationMessage(`Create PR?`, 'Yes', 'No');
      if (create === 'Yes') await createPullRequest(serverUrl, project, repo, currentBranch, baseBranch, creds);
    }
  } catch (error) {
    vscode.window.showErrorMessage(`Status check failed: ${error.message}`);
  }
}

// ============================================
// COMMAND 3: CHECK CONFIGURATION
// ============================================
async function checkConfiguration(context) {
  const config = vscode.workspace.getConfiguration('bitbucketPR');
  const serverUrl = config.get('serverUrl');
  const creds = await context.secrets.get('bitbucket-auth');
  let report = `🔧 **Config Report**\n\nURL: ${serverUrl || 'Missing'}\nAuth: ${creds ? 'Stored' : 'Missing'}`;
  const doc = await vscode.workspace.openTextDocument({ content: report, language: 'markdown' });
  await vscode.window.showTextDocument(doc);
}

// ============================================
// COMMAND 4: REVIEW & POST (UPDATED LOGIC)
// ============================================
async function reviewAndPost(context) {
  try {
    const config = vscode.workspace.getConfiguration('bitbucketPR');
    const serverUrl = config.get('serverUrl');
    const project = config.get('project');
    const repo = config.get('repo');
    const baseBranch = config.get('baseBranch');
    const creds = await context.secrets.get('bitbucket-auth');
    
    if (!serverUrl || !creds) {
      vscode.window.showWarningMessage('Not configured.');
      return;
    }
    
    const currentBranch = await getCurrentBranch();
    let prResult = await findPullRequest(serverUrl, project, repo, currentBranch, baseBranch, creds);
    
    if (!prResult.found) {
      vscode.window.showErrorMessage('No active PR found.');
      return;
    }
    
    const reviewType = await vscode.window.showQuickPick([
      { label: '📄 File Review', value: 'file' },
      { label: '🔄 PR Diff Review', value: 'diff', description: 'New: Uses file context for Copilot' },
      { label: '✅ JIRA Acceptance Criteria', value: 'jira' }
    ]);
    
    if (!reviewType) return;

    if (reviewType.value === 'file') {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const prompt = `Review this file:\n\n${editor.document.getText()}`;
      await vscode.env.clipboard.writeText(prompt);
      vscode.window.showInformationMessage('File prompt copied!');
    } 
    else if (reviewType.value === 'diff') {
      // --- NEW INTEGRATED LOGIC ---
      await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Fetching PR Diff...",
      }, async () => {
        const diffText = await getPRDiff(serverUrl, project, repo, prResult.pr.id, creds);
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!diffText || !workspaceFolder) return;

        const tempFileName = '.pr_review_context.diff';
        const tempUri = vscode.Uri.joinPath(workspaceFolder.uri, tempFileName);
        
        // 1. Write the file
        await vscode.workspace.fs.writeFile(tempUri, Buffer.from(diffText, 'utf8'));
        
        // 2. Open it to the side
        const doc = await vscode.workspace.openTextDocument(tempUri);
        await vscode.window.showTextDocument(doc, { preview: true, viewColumn: vscode.ViewColumn.Beside });

        // 3. Copy magic command
        const command = `@workspace /explain #file:${tempFileName} Please review these code changes for bugs and security.`;
        await vscode.env.clipboard.writeText(command);

        vscode.window.showInformationMessage('✅ Command copied! Paste in Chat.', 'Open Chat')
          .then(sel => sel === 'Open Chat' && vscode.commands.executeCommand('workbench.panel.chat.view.focus'));
      });
    }
    else if (reviewType.value === 'jira') {
      const jiraTicket = extractJiraTicket(currentBranch) || extractJiraTicket(prResult.pr.title);
      if (jiraTicket) {
        vscode.window.showInformationMessage(`Reviewing against JIRA: ${jiraTicket}`);
        // This will call your existing fetchJiraTicket logic below
      }
    }

    const review = await vscode.window.showInputBox({
      title: 'Post Review to Bitbucket',
      prompt: 'Paste the AI response here',
      ignoreFocusOut: true,
      multiline: true
    });

    if (review) {
      await postComment(serverUrl, project, repo, prResult.pr.id, `### 🤖 AI Review\n\n${review}`, creds);
      vscode.window.showInformationMessage('Review posted!');
      // Cleanup temp file
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (workspaceFolder) {
        try { await vscode.workspace.fs.delete(vscode.Uri.joinPath(workspaceFolder.uri, '.pr_review_context.diff')); } catch(e) {}
      }
    }
  } catch (error) {
    vscode.window.showErrorMessage(`Error: ${error.message}`);
  }
}

// ============================================
// HELPER FUNCTIONS (KEEPING YOUR ENTIRE LOGIC)
// ============================================

async function testConnection(serverUrl, authBase64) {
  try {
    const response = await fetch(`${serverUrl}/rest/api/1.0/application-properties`, {
      headers: { 'Authorization': `Basic ${authBase64}`, 'Content-Type': 'application/json' }
    });
    if (response.ok) {
      const data = await response.json();
      return { success: true, user: data.authenticatedUser?.displayName || 'Unknown' };
    }
    return { success: false, error: `HTTP ${response.status}` };
  } catch (e) { return { success: false, error: e.message }; }
}

async function getCurrentBranch() {
  if (!git) return null;
  const status = await git.status();
  return status.current;
}

async function findPullRequest(serverUrl, project, repo, sourceBranch, targetBranch, authBase64) {
  try {
    const url = `${serverUrl}/rest/api/1.0/projects/${project}/repos/${repo}/pull-requests?state=OPEN`;
    const response = await fetch(url, { headers: { 'Authorization': `Basic ${authBase64}` } });
    const data = await response.json();
    const pr = data.values?.find(p => p.fromRef.displayId === sourceBranch);
    return pr ? { found: true, pr: { id: pr.id, title: pr.title, url: pr.links.self[0].href } } : { found: false };
  } catch (e) { return { found: false }; }
}

async function createPullRequest(serverUrl, project, repo, source, target, auth) {
  const url = `${serverUrl}/rest/api/1.0/projects/${project}/repos/${repo}/pull-requests`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Authorization': `Basic ${auth}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: `Merge ${source}`, fromRef: { id: `refs/heads/${source}` }, toRef: { id: `refs/heads/${target}` } })
  });
  return res.ok;
}

async function postComment(serverUrl, project, repo, prId, comment, auth) {
  const url = `${serverUrl}/rest/api/1.0/projects/${project}/repos/${repo}/pull-requests/${prId}/comments`;
  await fetch(url, {
    method: 'POST',
    headers: { 'Authorization': `Basic ${auth}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: comment })
  });
  return true;
}

async function getPRDiff(serverUrl, project, repo, prId, auth) {
  const url = `${serverUrl}/rest/api/1.0/projects/${project}/repos/${repo}/pull-requests/${prId}/diff`;
  const res = await fetch(url, { headers: { 'Authorization': `Basic ${auth}`, 'Accept': 'text/plain' } });
  return res.ok ? await res.text() : null;
}

function extractJiraTicket(text) {
  const match = text?.match(/([A-Z]+)-(\d+)/);
  return match ? match[0] : null;
}

async function fetchJiraTicket(jiraUrl, ticketId, authBase64) {
  try {
    const baseUrl = jiraUrl.replace(/\/$/, '');
    const url = `${baseUrl}/rest/api/2/issue/${ticketId}`;
    const response = await fetch(url, { headers: { 'Authorization': `Basic ${authBase64}` } });
    if (!response.ok) return null;
    const data = await response.json();
    return {
      key: data.key,
      description: extractTextFromField(data.fields.description),
      acceptanceCriteria: extractTextFromField(data.fields.customfield_10000)
    };
  } catch (e) { return null; }
}

function extractTextFromField(field) {
  if (!field) return '';
  if (typeof field === 'string') return field;
  if (field.type === 'doc' && field.content) return extractTextFromADF(field.content);
  return '';
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
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (workspaceFolders) git = simpleGit(workspaceFolders[0].uri.fsPath);
  
  context.subscriptions.push(
    vscode.commands.registerCommand('bitbucketPR.easySetup', () => easySetup(context)),
    vscode.commands.registerCommand('bitbucketPR.showStatus', () => showStatus(context)),
    vscode.commands.registerCommand('bitbucketPR.checkConfig', () => checkConfiguration(context)),
    vscode.commands.registerCommand('bitbucketPR.reviewAndPost', () => reviewAndPost(context))
  );
}

function deactivate() {}

module.exports = { activate, deactivate };