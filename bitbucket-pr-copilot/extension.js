// extension.js
const vscode = require('vscode');
const simpleGit = require('simple-git');
const path = require('path');
const crypto = require('crypto');

// ---------- DEFAULTS (overridable via settings) ----------
const DEFAULTS = {
  workspace: 'myworkspace_poc',
  repo: 'myrepo_poc',
  baseBranch: 'main', // only used if we create a PR
};
const SECRET_KEY = 'bitbucket-basic-auth'; // stores base64(email:token)

// ---------- LOGGING ----------
let output; // created in activate()
function log(msg) {
  try {
    const time = new Date().toISOString();
    output?.appendLine(`[${time}] ${msg}`);
  } catch { /* noop */ }
}

// ---------- SETTINGS ----------
function getCfg() {
  const cfg = vscode.workspace.getConfiguration('bitbucketPRCopilot');
  return {
    workspace: cfg.get('workspace') || DEFAULTS.workspace,
    repo: cfg.get('repo') || DEFAULTS.repo,
    baseBranch: cfg.get('baseBranch') || DEFAULTS.baseBranch,
  };
}

// ---------- WORKSPACE ----------
const workspaceFolders = vscode.workspace.workspaceFolders;
const repoPath = workspaceFolders?.[0]?.uri.fsPath;

/** @type import('simple-git').SimpleGit */
let git = null;

// Dedupe store (per run) + cross-run de-dupe via existing PR comments
const postedHashes = new Set();
const existingHashesByPR = new Map();

// Resolve and re-root simple-git at the real .git top level
async function initGitAtRepoRoot(startPath) {
  const tmp = simpleGit(startPath);
  const root = (await tmp.revparse(['--show-toplevel'])).trim();
  log(`Git root resolved: ${root}`);
  return simpleGit(root);
}

// ---------- PATH / FILTERS ----------
function toPosix(p) {
  return p.replace(/\\/g, '/');
}
const EXCLUDE_PATTERNS = [
  /^\.vscode\//,
  /(^|\/)[^/]*\.code-workspace$/i,
  /^\.git\//,
  /(^|\/)(dist|build|out)\//,
  /(^|\/)node_modules\//,
  /(^|\/)package-lock\.json$/i,
  /(^|\/)yarn\.lock$/i,
  /(^|\/)pnpm-lock\.yaml$/i,
  /\.(png|jpg|jpeg|gif|svg|ico|pdf|zip|gz|bz2|7z|mp4|mp3|wav|woff2?)$/i
];
const ALLOW_EXTENSIONS = [
  '.js','.jsx','.ts','.tsx',
  '.py','.java','.kt','.go','.rb','.php',
  '.cs','.cpp','.c','.h','.hpp',
  '.json','.yaml','.yml'
];
function hasAllowedExtension(p) { return ALLOW_EXTENSIONS.some(ext => p.toLowerCase().endsWith(ext)); }
function isExcluded(p) { return EXCLUDE_PATTERNS.some(rx => rx.test(p)); }
function isSourceLike(p) { return !isExcluded(p) && hasAllowedExtension(p); }

// ---------- AUTH ----------
async function getAuthHeader(context) {
  const sec = context.secrets;
  let basic = await sec.get(SECRET_KEY);
  if (!basic) {
    const email = await vscode.window.showInputBox({ prompt: 'Bitbucket email', ignoreFocusOut: true });
    const token = await vscode.window.showInputBox({ prompt: 'Bitbucket App Password / API Token', password: true, ignoreFocusOut: true });
    if (!email || !token) throw new Error('Bitbucket credentials are required.');
    basic = Buffer.from(`${email}:${token}`).toString('base64');
    await sec.store(SECRET_KEY, basic);
    log('Stored Bitbucket credentials in SecretStorage.');
  }
  return `Basic ${basic}`;
}

// ---------- HTTP HELPERS ----------
async function bbFetch(url, { method='GET', headers={}, body, authHeader }, retries = 2) {
  const res = await fetch(url, {
    method,
    headers: { 'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': authHeader, ...headers },
    body
  });
  if (res.status === 401) throw new Error('Unauthorized (401). Check Bitbucket token scopes.');
  if (res.status === 429 && retries > 0) {
    const wait = parseInt(res.headers.get('Retry-After') || '2', 10) * 1000;
    log(`Rate limited by Bitbucket; retrying in ${wait} ms`);
    await new Promise(r => setTimeout(r, wait));
    return bbFetch(url, { method, headers, body, authHeader }, retries - 1);
  }
  if (!res.ok) throw new Error(`${method} ${url} failed: ${res.status} ${await res.text()}`);
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : res.text();
}
async function bbPaginate(url, opts) {
  const values = [];
  let next = url;
  while (true) {
    const page = await bbFetch(next, opts);
    values.push(...(page.values || []));
    if (!page.next) break;
    next = page.next;
  }
  return values;
}

// ---------- BITBUCKET HELPERS ----------
function prBase() {
  const { workspace, repo } = getCfg();
  return `https://api.bitbucket.org/2.0/repositories/${workspace}/${repo}/pullrequests`;
}

async function findPRForBranch(branch, authHeader) {
  const { baseBranch } = getCfg();
  const q = `source.branch.name="${branch}" AND state="OPEN" AND destination.branch.name="${baseBranch}"`;
  const url = `${prBase()}?q=${encodeURIComponent(q)}&fields=values.id,values.title`;
  const vals = await bbPaginate(url, { authHeader });
  log(`findPRForBranch: branch=${branch}, openPRs=${vals.length}`);
  return vals[0]?.id || null;
}

async function createPullRequest(sourceBranch, authHeader, title, description) {
  const { baseBranch } = getCfg();
  const url = prBase();
  const body = {
    title: title || `Auto PR: ${sourceBranch} → ${baseBranch}`,
    description: description || 'Created by Bitbucket PR Copilot.',
    source: { branch: { name: sourceBranch } },
    destination: { branch: { name: baseBranch } },
    close_source_branch: false
  };
  log(`Creating PR for branch=${sourceBranch}`);
  return bbFetch(url, { method: 'POST', body: JSON.stringify(body), authHeader });
}

async function postPRComment(prId, content, authHeader) {
  log(`Posting general comment to PR #${prId}`);
  const url = `${prBase()}/${prId}/comments`;
  const payload = { content: { raw: content } };
  return bbFetch(url, { method: 'POST', body: JSON.stringify(payload), authHeader });
}

async function postInlinePRComment(prId, pathRel, toLine, content, authHeader) {
  log(`Posting inline comment to ${pathRel} at line ${toLine} in PR #${prId}`);
  const url = `${prBase()}/${prId}/comments`;
  const payload = { content: { raw: content }, inline: { path: pathRel, to: toLine } };
  return bbFetch(url, { method: 'POST', body: JSON.stringify(payload), authHeader });
}

async function listPRComments(prId, authHeader) {
  const url = `${prBase()}/${prId}/comments?pagelen=100`;
  return bbPaginate(url, { authHeader });
}

// ---------- PR SESSION ----------
async function ensurePrForCurrentBranch(context) {
  const authHeader = await getAuthHeader(context);
  const status = await git.status();
  const branch = status.current;
  log(`Current branch=${branch}`);

  const { baseBranch } = getCfg();

  if (branch === baseBranch) {
    vscode.window.showWarningMessage(`You're on ${baseBranch}. Switch to a feature branch to open a PR.`);
    return { prId: null, authHeader };
  }

  let prId = await findPRForBranch(branch, authHeader);
  if (!prId) {
    log(`No open PR for ${branch}. Prompting to create.`);
    const confirm = await vscode.window.showInformationMessage(
      `No PR found for ${branch}. Create PR to ${baseBranch}?`, 'Create PR', 'Cancel'
    );
    if (confirm !== 'Create PR') return { prId: null, authHeader };
    const pr = await createPullRequest(branch, authHeader);
    prId = pr.id;
    vscode.window.showInformationMessage(`Created PR #${prId}.`);
  }
  log(`Using PR #${prId}`);
  return { prId, authHeader };
}

// ---------- DEDUPE ----------
function hashForComment(prId, filePath, toLine /* may be null for general */, content) {
  const target = `${prId}|${filePath || ''}|${toLine || 0}|${content}`;
  return crypto.createHash('sha1').update(target).digest('hex');
}

async function ensureExistingCommentHashes(prId, authHeader) {
  if (existingHashesByPR.has(prId)) return existingHashesByPR.get(prId);
  const values = await listPRComments(prId, authHeader);
  const set = new Set();
  for (const c of values) {
    const content = c?.content?.raw || '';
    const inline = c?.inline || {};
    const p = inline.path ? toPosix(inline.path.toString()) : null;
    const to = typeof inline.to === 'number' ? inline.to : null;
    const sig = hashForComment(prId, p, to, content);
    set.add(sig);
  }
  existingHashesByPR.set(prId, set);
  log(`Loaded ${set.size} existing comment signatures from PR #${prId}`);
  return set;
}

async function postInlineIfNew(prId, pathRel, toLine, content, authHeader) {
  const existing = await ensureExistingCommentHashes(prId, authHeader);
  const sig = hashForComment(prId, pathRel, toLine, content);
  if (postedHashes.has(sig) || existing.has(sig)) {
    log(`Deduped inline comment (already exists): ${pathRel}@${toLine}`);
    return;
  }
  await postInlinePRComment(prId, pathRel, toLine, content, authHeader);
  postedHashes.add(sig);
  existing.add(sig);
}

async function postGeneralIfNew(prId, content, authHeader) {
  const existing = await ensureExistingCommentHashes(prId, authHeader);
  const sig = hashForComment(prId, null, null, content);
  if (postedHashes.has(sig) || existing.has(sig)) {
    log(`Deduped general comment (already exists)`);
    return;
  }
  await postPRComment(prId, content, authHeader);
  postedHashes.add(sig);
  existing.add(sig);
}

// ---------- UI HELPERS ----------
function summarize(body, max = 140) {
  const line = body.split(/\r?\n/).find(l => l.trim().length);
  const s = (line || body).replace(/\s+/g, ' ').trim();
  return s.length > max ? s.slice(0, max - 1) + '…' : s;
}

function makeGeneralComment(filePath, feedback) {
  return [`🤖 **Copilot/Chat Review for \`${filePath}\`**`, '', feedback].join('\n');
}

function makeInlineComment(filePath, toLine, feedback) {
  return [`🤖 **Copilot/Chat note @ line ~${toLine} in \`${filePath}\`**`, '', feedback].join('\n');
}

// ---------- NEW: collect ALL open source files (tabs + visible + loaded) ----------
function collectOpenSourceFiles() {
  const rel = (uri) => vscode.workspace.asRelativePath(uri.fsPath);
  const set = new Set();

  // Tabs in all groups (works even if not visible)
  try {
    for (const group of vscode.window.tabGroups?.all || []) {
      for (const tab of group.tabs || []) {
        const input = tab.input;
        const uri = input?.uri || input?.['uri']; // TabInputText-like
        if (uri?.scheme === 'file') set.add(rel(uri));
      }
    }
  } catch (_) { /* ignore */ }

  // Visible editors (old behavior)
  for (const ed of vscode.window.visibleTextEditors || []) {
    const uri = ed.document?.uri;
    if (uri?.scheme === 'file') set.add(rel(uri));
  }

  // Any loaded text documents (hidden/previewed)
  for (const doc of vscode.workspace.textDocuments || []) {
    const uri = doc?.uri;
    if (uri?.scheme === 'file') set.add(rel(uri));
  }

  return [...set].filter(isSourceLike);
}

// ---------- CORE COMMANDS ----------
async function cmdTestGit() {
  const status = await git.status();
  vscode.window.showInformationMessage(`Current branch: ${status.current}`);
  log(`TestGit: branch=${status.current}`);
}

async function cmdPostGeneralForCurrentFile(context) {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return vscode.window.showWarningMessage('Open a file first.');
  const filePath = vscode.workspace.asRelativePath(editor.document.fileName);
  if (!isSourceLike(filePath)) return vscode.window.showWarningMessage('Not a source file.');

  const { prId, authHeader } = await ensurePrForCurrentBranch(context);
  if (!prId) return;

  const feedback = await vscode.window.showInputBox({
    prompt: `Paste Copilot/Chat feedback for ${filePath} (general PR comment)`,
    ignoreFocusOut: true,
    validateInput: (v) => v?.trim()?.length ? null : 'Feedback required'
  });
  if (!feedback) return;

  const body = makeGeneralComment(filePath, feedback);
  const confirm = await vscode.window.showQuickPick(
    [{ label: `Post general review to PR #${prId}`, detail: summarize(body), picked: true }],
    { canPickMany: false, title: 'Preview general comment' }
  );
  if (!confirm) return;

  await postGeneralIfNew(prId, body, authHeader);
  vscode.window.showInformationMessage('✅ Posted general comment.');
}

async function cmdPostInlineAtSelection(context) {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return vscode.window.showWarningMessage('Open a file first.');
  const filePath = vscode.workspace.asRelativePath(editor.document.fileName);
  if (!isSourceLike(filePath)) return vscode.window.showWarningMessage('Not a source file.');
  if (editor.selection.isEmpty) return vscode.window.showWarningMessage('Select the code where you want to attach the comment.');

  const { prId, authHeader } = await ensurePrForCurrentBranch(context);
  if (!prId) return;

  const line = editor.selection.start.line + 1;
  const feedback = await vscode.window.showInputBox({
    prompt: `Paste Copilot/Chat suggestion for ${filePath}:${line}`,
    ignoreFocusOut: true,
    validateInput: (v) => v?.trim()?.length ? null : 'Feedback required'
  });
  if (!feedback) return;

  const body = makeInlineComment(filePath, line, feedback);
  const rel = toPosix(filePath);
  const confirm = await vscode.window.showQuickPick(
    [{ label: `Post inline to ${rel}:${line}`, detail: summarize(body), picked: true }],
    { canPickMany: false, title: 'Preview inline comment' }
  );
  if (!confirm) return;

  await postInlineIfNew(prId, rel, line, body, authHeader);
  vscode.window.showInformationMessage('✅ Posted inline comment.');
}

async function cmdPostInlineAtLine(context) {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return vscode.window.showWarningMessage('Open a file first.');
  const filePath = vscode.workspace.asRelativePath(editor.document.fileName);
  if (!isSourceLike(filePath)) return vscode.window.showWarningMessage('Not a source file.');

  const { prId, authHeader } = await ensurePrForCurrentBranch(context);
  if (!prId) return;

  const lineStr = await vscode.window.showInputBox({
    prompt: `Line number in ${filePath} to attach the inline comment`,
    validateInput: (v) => /^\d+$/.test(v || '') ? null : 'Enter a positive integer'
  });
  if (!lineStr) return;
  const line = parseInt(lineStr, 10);

  const feedback = await vscode.window.showInputBox({
    prompt: `Paste Copilot/Chat suggestion for ${filePath}:${line}`,
    ignoreFocusOut: true,
    validateInput: (v) => v?.trim()?.length ? null : 'Feedback required'
  });
  if (!feedback) return;

  const body = makeInlineComment(filePath, line, feedback);
  const rel = toPosix(filePath);
  const confirm = await vscode.window.showQuickPick(
    [{ label: `Post inline to ${rel}:${line}`, detail: summarize(body), picked: true }],
    { canPickMany: false, title: 'Preview inline comment' }
  );
  if (!confirm) return;

  await postInlineIfNew(prId, rel, line, body, authHeader);
  vscode.window.showInformationMessage('✅ Posted inline comment.');
}

async function cmdPostBatchForOpenFiles(context) {
  // NEW: gather from all tabs + visible editors + loaded docs
  const files = collectOpenSourceFiles();
  if (!files.length) {
    return vscode.window.showInformationMessage('No open source files to post for.');
  }

  const { prId, authHeader } = await ensurePrForCurrentBranch(context);
  if (!prId) return;

  /** @type {{ kind:'inline'|'general', relPosix:string, toLine?:number, body:string }[]} */
  const plans = [];
  for (const f of files) {
    const action = await vscode.window.showQuickPick(
      [
        { label: `Inline comment for ${f}`, val: 'inline' },
        { label: `General comment for ${f}`, val: 'general' },
        { label: `Skip ${f}`, val: 'skip' }
      ],
      { placeHolder: `Choose how to post for ${f}` }
    );
    if (!action || action.val === 'skip') continue;

    let line = null;
    if (action.val === 'inline') {
      const lineStr = await vscode.window.showInputBox({
        prompt: `Line number in ${f} for inline comment`,
        validateInput: (v) => /^\d+$/.test(v || '') ? null : 'Enter a positive integer'
      });
      if (!lineStr) continue;
      line = parseInt(lineStr, 10);
    }

    const feedback = await vscode.window.showInputBox({
      prompt: `Paste Copilot/Chat feedback for ${f}${line ? `:${line}` : ''}`,
      ignoreFocusOut: true
    });
    if (!feedback?.trim()) continue;

    const rel = toPosix(f);
    if (line) {
      plans.push({
        kind: 'inline',
        relPosix: rel,
        toLine: line,
        body: makeInlineComment(f, line, feedback.trim())
      });
    } else {
      plans.push({
        kind: 'general',
        relPosix: rel,
        body: makeGeneralComment(f, feedback.trim())
      });
    }
  }

  if (!plans.length) {
    vscode.window.showInformationMessage('Nothing to post.');
    return;
  }

  const items = plans.map(p => ({
    label: p.kind === 'inline' ? `${p.relPosix}:${p.toLine}` : `${p.relPosix} (general)`,
    description: p.kind === 'inline' ? 'Inline' : 'General',
    detail: summarize(p.body),
    picked: true,
    plan: p
  }));

  const picked = await vscode.window.showQuickPick(items, {
    title: 'Preview: comments to post',
    canPickMany: true,
    matchOnDetail: true,
    placeHolder: 'Uncheck anything you do NOT want to post, then press Enter'
  });
  if (!picked) return;

  let posted = 0;
  for (const i of picked) {
    const p = i.plan;
    if (p.kind === 'inline') {
      await postInlineIfNew(prId, p.relPosix, p.toLine, p.body, authHeader);
      posted++;
    } else {
      await postGeneralIfNew(prId, p.body, authHeader);
      posted++;
    }
  }
  vscode.window.showInformationMessage(`✅ Posted ${posted} comment(s) to PR #${prId}`);
}

// ---------- NEW: Quick Post (wrapper) ----------
async function cmdQuickPost(context) {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return vscode.window.showWarningMessage('Open a file first.');
  const filePath = vscode.workspace.asRelativePath(editor.document.fileName);
  if (!isSourceLike(filePath)) return vscode.window.showWarningMessage('Not a source file.');

  const choice = await vscode.window.showQuickPick(
    [
      { label: 'Inline @ selection (recommended)', val: 'sel', detail: 'Use current selection as the anchor line' },
      { label: 'Inline @ specific line', val: 'line', detail: 'Pick a line number' },
      { label: 'General comment for file', val: 'gen', detail: 'Post a non-inline PR comment' }
    ],
    { title: 'Quick Post – choose how to post for active file' }
  );
  if (!choice) return;

  if (choice.val === 'sel') return cmdPostInlineAtSelection(context);
  if (choice.val === 'line') return cmdPostInlineAtLine(context);
  if (choice.val === 'gen') return cmdPostGeneralForCurrentFile(context);
}

// ---------- ACTIVATE ----------
function activate(context) {
  // Output channel & log command (always available)
  output = vscode.window.createOutputChannel('BB PR Copilot');
  context.subscriptions.push(output);
  output.show(true);
  log('Extension activating…');

  context.subscriptions.push(
    vscode.commands.registerCommand('bitbucketPRCopilot.showLog', () => {
      try {
        output.show(true);
        output.appendLine(`[${new Date().toISOString()}] Log opened manually.`);
        vscode.window.showInformationMessage('Opened "BB PR Copilot" output.');
      } catch (e) {
        vscode.window.showErrorMessage(`Could not open log: ${e.message}`);
      }
    })
  );

  // If no folder open, keep only the log command
  if (!repoPath) {
    vscode.window.showErrorMessage('Open a folder in VS Code with your Git repo!');
    log('No workspace folder. Commands that need git will not be registered.');
    return;
  }

  (async () => {
    try {
      try {
        git = await initGitAtRepoRoot(repoPath);
        log('Git initialized at repo root.');
      } catch (e) {
        log(`Git root resolve failed, falling back to workspace folder: ${e.message}`);
        git = simpleGit(repoPath);
      }

      // Register streamlined commands
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.testGit', () => cmdTestGit()));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postGeneralForCurrentFile', () => cmdPostGeneralForCurrentFile(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postInlineAtSelection', () => cmdPostInlineAtSelection(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postInlineAtLine', () => cmdPostInlineAtLine(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postBatchForOpenFiles', () => cmdPostBatchForOpenFiles(context)));

      // Command IDs referenced by package.json
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.quickPost', () => cmdQuickPost(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.batchPost', () => cmdPostBatchForOpenFiles(context)));

      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.clearApiToken', async () => {
        await context.secrets.delete(SECRET_KEY);
        vscode.window.showInformationMessage('Bitbucket credentials cleared.');
        log('Cleared Bitbucket credentials.');
      }));

      log('Commands registered.');
    } catch (e) {
      vscode.window.showErrorMessage(`Activation failed: ${e.message}`);
      log(`Activation failed: ${e.stack || e.message}`);
    }
  })();
}

function deactivate() {}

module.exports = { activate, deactivate };
