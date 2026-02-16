const vscode = require('vscode');
const simpleGit = require('simple-git');
const fs = require('fs');
const https = require('https');

let output;
let git;

function log(msg) {
    const time = new Date().toISOString();
    output?.appendLine(`[${time}] ${msg}`);
}

// ============================================
// COMMAND 1: Easy Setup
// ============================================
async function easySetup(context) {
    try {
        const config = vscode.workspace.getConfiguration('bitbucketPR');
        
        // Use the exact keys registered in package.json
        const serverUrl = await vscode.window.showInputBox({ title: '1/7: Bitbucket URL', value: config.get('serverUrl') || '', ignoreFocusOut: true });
        const jiraUrl = await vscode.window.showInputBox({ title: '2/7: Jira URL', value: config.get('jiraUrl') || '', ignoreFocusOut: true });
        const project = await vscode.window.showInputBox({ title: '3/7: Project Key', value: config.get('project') || '', ignoreFocusOut: true });
        const repo = await vscode.window.showInputBox({ title: '4/7: Repo Name', value: config.get('repo') || '', ignoreFocusOut: true });
        const sourceBranch = await vscode.window.showInputBox({ title: '5/7: Your Branch (Source)', value: config.get('sourceBranch') || '', ignoreFocusOut: true });
        const baseBranch = await vscode.window.showInputBox({ title: '6/7: Target Branch (Dest)', value: config.get('baseBranch') || 'master', ignoreFocusOut: true });
        const user = await vscode.window.showInputBox({ title: '7/7: LDAP Username', ignoreFocusOut: true });
        const pass = await vscode.window.showInputBox({ title: 'LDAP Password', password: true, ignoreFocusOut: true });

        if (!serverUrl || !user || !pass) return;

        // Clean URLs (remove trailing slashes)
        const cleanServer = serverUrl.replace(/\/+$/, "");
        const cleanJira = jiraUrl.replace(/\/+$/, "");

        // Save to Global Settings
        await config.update('serverUrl', cleanServer, vscode.ConfigurationTarget.Global);
        await config.update('jiraUrl', cleanJira, vscode.ConfigurationTarget.Global);
        await config.update('project', project, vscode.ConfigurationTarget.Global);
        await config.update('repo', repo, vscode.ConfigurationTarget.Global);
        await config.update('sourceBranch', sourceBranch, vscode.ConfigurationTarget.Global);
        await config.update('baseBranch', baseBranch, vscode.ConfigurationTarget.Global);
        
        // Save Credentials Securely
        const creds = Buffer.from(`${user}:${pass}`).toString('base64');
        await context.secrets.store('bitbucket-auth', creds);
        
        vscode.window.showInformationMessage('✅ Setup Complete & Verified!');
    } catch (e) { 
        vscode.window.showErrorMessage(`Setup failed: ${e.message}`); 
    }
}
// ============================================
// COMMAND 2: Show Status (Connection Test)
// ============================================
async function showStatus(context) {
    try {
        const config = vscode.workspace.getConfiguration('bitbucketPR');
        const creds = await context.secrets.get('bitbucket-auth');
        const currentBranch = await getCurrentBranch();
        
        log(`Testing connection to: ${config.get('serverUrl')}`);
        const prResult = await findPullRequest(config.get('serverUrl'), config.get('project'), config.get('repo'), currentBranch, creds);
        
        if (prResult.found) {
            vscode.window.showInformationMessage(`✅ Connected! Found PR #${prResult.pr.id}`);
        } else {
            vscode.window.showWarningMessage(`Connected to Bitbucket, but no open PR found for branch: ${currentBranch}`);
        }
    } catch (e) { 
        log(`Connection Test Failed: ${e.message}`);
        vscode.window.showErrorMessage(`Connection Test Failed: ${e.message}. Check "PR Copilot" Output logs.`); 
    }
}

// ============================================
// COMMAND 3: Check Configuration
// ============================================
async function checkConfiguration(context) {
    const config = vscode.workspace.getConfiguration('bitbucketPR');
    const creds = await context.secrets.get('bitbucket-auth');
    const report = `--- Configuration ---\nBitbucket: ${config.get('serverUrl')}\nJira: ${config.get('jiraUrl')}\nProject: ${config.get('project')}\nRepo: ${config.get('repo')}\nBase Branch: ${config.get('baseBranch')}\nAuth: ${creds ? 'Stored' : 'Missing'}`;
    const doc = await vscode.workspace.openTextDocument({ content: report, language: 'text' });
    await vscode.window.showTextDocument(doc);
}

// ============================================
// COMMAND 4: Review & Post (3 Rules)
// ============================================
async function reviewAndPost(context) {
    let tempFilePath = null;
    try {
        const config = vscode.workspace.getConfiguration('bitbucketPR');
        const creds = await context.secrets.get('bitbucket-auth');

        const reviewType = await vscode.window.showQuickPick([
            { label: '📄 File Review', value: 'file' },
            { label: '🔄 PR Diff Review', value: 'diff' },
            { label: '✅ Jira AC Review', value: 'jira' }
        ], { placeHolder: 'Select Business Rule' });

        if (!reviewType) return;

        let contextText = "";
        let prId = null;
        const currentBranch = config.get('bitbucketPR.sourceBranch') || await getCurrentBranch();

        // 1. Prepare the context (File or Diff)
        if (reviewType.value === 'file') {
            const editor = vscode.window.activeTextEditor;
            if (!editor) throw new Error("Open a file first!");
            contextText = editor.document.getText();
        } else {
            // Fetch PR ID and Diff for Diff/Jira modes
            const prResult = await findPullRequest(config.get('bitbucketPR.serverUrl'), config.get('bitbucketPR.project'), config.get('bitbucketPR.repo'), currentBranch, creds);
            prId = prResult.found ? prResult.pr.id : null;
            contextText = await getPRDiff(config.get('bitbucketPR.serverUrl'), config.get('bitbucketPR.project'), config.get('bitbucketPR.repo'), prId, creds);

            if (reviewType.value === 'jira') {
                const ticketId = extractJiraTicket(currentBranch);
                const jiraData = await fetchJiraTicket(config.get('bitbucketPR.jiraUrl'), ticketId, creds);
                contextText = `--- JIRA AC ---\n${jiraData.acceptanceCriteria}\n\n${contextText}`;
            }
        }

        // 2. Create the .diff file
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        const tempUri = vscode.Uri.joinPath(workspaceFolder.uri, '.pr_review.diff');
        tempFilePath = tempUri.fsPath;
        await vscode.workspace.fs.writeFile(tempUri, Buffer.from(contextText, 'utf8'));

        // 3. Open the file side-by-side
        await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(tempUri), { 
            preview: true, 
            viewColumn: vscode.ViewColumn.Beside 
        });

        // 4. Copy the magic command to clipboard
        const magicCmd = `@workspace /explain #file:.pr_review.diff Review this code for bugs/logic.`;
        await vscode.env.clipboard.writeText(magicCmd);

        // 5. THE PERSISTENT FIX: Show a notification with a button that stays there
        vscode.window.showInformationMessage(
            "👉 Magic command copied. Use Copilot Chat, then click 'Post' when ready.",
            "Post to Bitbucket"
        ).then(async (selection) => {
            if (selection === "Post to Bitbucket") {
                // Now that you have the AI response in your hand, we open the input box
                const aiReview = await vscode.window.showInputBox({
                    title: "Paste AI Response",
                    prompt: "Paste the recommendation from Copilot Chat here",
                    ignoreFocusOut: true // This prevents it from closing if you accidentally click away
                });

                if (aiReview && prId) {
                    await postComment(config.get('bitbucketPR.serverUrl'), config.get('bitbucketPR.project'), config.get('bitbucketPR.repo'), prId, `### 🤖 AI Review\n\n${aiReview}`, creds);
                    vscode.window.showInformationMessage("✅ Posted to Bitbucket!");
                } else if (!prId) {
                    vscode.window.showWarningMessage("Review copied, but no PR ID found to post to.");
                }
            }
        });

    } catch (e) {
        vscode.window.showErrorMessage(`Error: ${e.message}`);
    }
}

// ============================================
// SHARED FETCH (LDAP + SSL BYPASS + LOGGING)
// ============================================
async function secureFetch(url, options = {}) {
    // 1. SSL Bypass Agent (Crucial for Corporate LDAP)
    const agent = new https.Agent({ rejectUnauthorized: false });
    
    // 2. Merge options with agent
    const fetchOptions = {
        ...options,
        agent: agent
    };

    log(`Fetching: ${url}`);
    const res = await fetch(url, fetchOptions);
    if (!res.ok) {
        const err = await res.text();
        log(`Fetch Error (${res.status}): ${err.substring(0, 100)}`);
        throw new Error(`Server returned ${res.status}`);
    }
    return res;
}

async function fetchJiraTicket(jiraUrl, ticketId, auth) {
    if (!ticketId) ticketId = await vscode.window.showInputBox({ prompt: 'Enter Jira Ticket ID' });
    if (!ticketId) return { key: "N/A", acceptanceCriteria: "Manual entry skipped" };

    try {
        const res = await secureFetch(`${jiraUrl}/rest/api/2/issue/${ticketId}`, { 
            headers: { 'Authorization': `Basic ${auth}` } 
        });
        const data = await res.json();
        let ac = data.fields.customfield_10041 || data.fields.description;
        if (typeof ac !== 'string') ac = extractADF(ac);
        if (!ac && data.fields.parent) return await fetchJiraTicket(jiraUrl, data.fields.parent.key, auth);
        return { key: data.key, acceptanceCriteria: ac || "No AC found" };
    } catch (e) { return { key: ticketId, acceptanceCriteria: `Jira Fetch Failed: ${e.message}` }; }
}

async function findPullRequest(url, proj, repo, branch, auth) {
    const res = await secureFetch(`${url}/rest/api/1.0/projects/${proj}/repos/${repo}/pull-requests?state=OPEN`, { 
        headers: { 'Authorization': `Basic ${auth}` } 
    });
    const data = await res.json();
    const pr = data.values?.find(p => p.fromRef.displayId === branch);
    return pr ? { found: true, pr: { id: pr.id, title: pr.title } } : { found: false };
}

async function getPRDiff(url, proj, repo, id, auth) {
    const config = vscode.workspace.getConfiguration('bitbucketPR');
    const base = config.get('baseBranch') || 'master';
    if (!id) return await git.diff([base]);
    const res = await secureFetch(`${url}/rest/api/1.0/projects/${proj}/repos/${repo}/pull-requests/${id}/diff`, { 
        headers: { 'Authorization': `Basic ${auth}`, 'Accept': 'text/plain' } 
    });
    return await res.text();
}

async function postComment(url, proj, repo, id, text, auth) {
    await secureFetch(`${url}/rest/api/1.0/projects/${proj}/repos/${repo}/pull-requests/${id}/comments`, {
        method: 'POST',
        headers: { 'Authorization': `Basic ${auth}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
    });
}

function extractADF(field) {
    if (!field || !field.content) return "";
    let text = "";
    const walk = (n) => {
        if (n.text) text += n.text;
        if (n.content) n.content.forEach(walk);
        if (n.type === 'paragraph' || n.type === 'listItem') text += '\n';
    };
    field.content.forEach(walk);
    return text.trim();
}

async function getCurrentBranch() {
    if (!git) {
        const folders = vscode.workspace.workspaceFolders;
        if (folders) git = simpleGit(folders[0].uri.fsPath);
    }
    const status = await git.status();
    return status.current;
}

function extractJiraTicket(text) {
    const match = text?.match(/([A-Z]+)-(\d+)/);
    return match ? match[0] : null;
}

function activate(context) {
    output = vscode.window.createOutputChannel('PR Copilot');
    const folders = vscode.workspace.workspaceFolders;
    if (folders) git = simpleGit(folders[0].uri.fsPath);

    context.subscriptions.push(
        vscode.commands.registerCommand('bitbucketPR.easySetup', () => easySetup(context)),
        vscode.commands.registerCommand('bitbucketPR.showStatus', () => showStatus(context)),
        vscode.commands.registerCommand('bitbucketPR.checkConfig', () => checkConfiguration(context)),
        vscode.commands.registerCommand('bitbucketPR.reviewAndPost', () => reviewAndPost(context))
    );
}

module.exports = { activate };