// extension.js
const vscode = require('vscode');
const simpleGit = require('simple-git');
const crypto = require('crypto');

// ---------- DEFAULTS (overridable via settings) ----------
const DEFAULTS = {
  workspace: 'myworkspace_poc',
  repo: 'myrepo_poc',
  baseBranch: 'main',
};
const SECRET_KEY = 'bitbucket-basic-auth';

// ---------- LOGGING ----------
let output;
function log(msg) {
  try {
    const time = new Date().toISOString();
    output?.appendLine(`[${time}] ${msg}`);
  } catch {}
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

const postedHashes = new Set();
const existingHashesByPR = new Map();

async function initGitAtRepoRoot(startPath) {
  const tmp = simpleGit(startPath);
  const root = (await tmp.revparse(['--show-toplevel'])).trim();
  log(`Git root resolved: ${root}`);
  return simpleGit(root);
}

// ---------- DEBUG COMMANDS ----------
async function cmdDebugEnv() {
  const envEmail = process.env.BITBUCKET_EMAIL;
  const envToken = process.env.BITBUCKET_TOKEN;
  
  const message = `Environment Variables:
BITBUCKET_EMAIL: ${envEmail ? '✓ SET (' + envEmail + ')' : '✗ NOT SET'}
BITBUCKET_TOKEN: ${envToken ? '✓ SET (length: ' + envToken.length + ')' : '✗ NOT SET'}`;
  
  log(message);
  vscode.window.showInformationMessage('Check "BB PR Copilot" output for environment variables status');
}

async function cmdDebugAuth(context) {
  try {
    log('🔐 Testing authentication...');
    
    const authHeader = await getAuthHeader(context);
    log(`Auth header prefix: ${authHeader.substring(0, 25)}...`);
    
    // Test the authentication
    const testUrl = 'https://api.bitbucket.org/2.0/user';
    const response = await fetch(testUrl, {
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      }
    });
    
    if (response.ok) {
      const userData = await response.json();
      const successMsg = `✅ Auth successful! User: ${userData.display_name}`;
      log(successMsg);
      vscode.window.showInformationMessage(successMsg);
      return true;
    } else {
      const errorText = await response.text();
      const errorMsg = `❌ Auth failed: ${response.status} - ${errorText}`;
      log(errorMsg);
      vscode.window.showErrorMessage(errorMsg);
      return false;
    }
  } catch (error) {
    const errorMsg = `❌ Auth error: ${error.message}`;
    log(errorMsg);
    vscode.window.showErrorMessage(errorMsg);
    return false;
  }
}

// ---------- PATH / FILTERS ----------
function toPosix(p) { return p.replace(/\\/g, '/'); }
const EXCLUDE_PATTERNS = [
  /^\.vscode\//, /(^|\/)[^/]*\.code-workspace$/i, /^\.git\//,
  /(^|\/)(dist|build|out)\//, /(^|\/)node_modules\//,
  /(^|\/)package-lock\.json$/i, /(^|\/)yarn\.lock$/i, /(^|\/)pnpm-lock\.yaml$/i,
  /\.(png|jpg|jpeg|gif|svg|ico|pdf|zip|gz|bz2|7z|mp4|mp3|wav|woff2?)$/i
];
const ALLOW_EXTENSIONS = [
  '.js','.jsx','.ts','.tsx','.py','.java','.kt','.go','.rb','.php',
  '.cs','.cpp','.c','.h','.hpp','.json','.yaml','.yml'
];
function hasAllowedExtension(p){ return ALLOW_EXTENSIONS.some(ext => p.toLowerCase().endsWith(ext)); }
function isExcluded(p){ return EXCLUDE_PATTERNS.some(rx => rx.test(p)); }
function isSourceLike(p){ return !isExcluded(p) && hasAllowedExtension(p); }
function normalizeRel(p){ return vscode.workspace.asRelativePath(p).replace(/\\/g, '/'); }

// ---------- AUTH (env-first, then SecretStorage) ----------
// ---------- AUTH (SecretStorage only) ----------
async function getAuthHeader(context) {
  log('🔐 Getting Bitbucket credentials from SecretStorage...');
  
  const sec = context.secrets;
  let basic = await sec.get(SECRET_KEY);
  
  if (!basic) {
    log('No credentials found in SecretStorage, prompting user...');
    
    // Prompt user for credentials
    const email = await vscode.window.showInputBox({ 
      prompt: 'Enter your Bitbucket email', 
      ignoreFocusOut: true,
      placeHolder: 'kemails2006@gmail.com'
    });
    
    if (!email) throw new Error('Email is required');
    
    const token = await vscode.window.showInputBox({ 
      prompt: 'Enter your Bitbucket API Token', 
      password: true, 
      ignoreFocusOut: true,
      placeHolder: 'Paste your API token here'
    });
    
    if (!token) throw new Error('API token is required');
    
    // Store as email:token format
    const credentials = `${email}:${token}`;
    basic = Buffer.from(credentials).toString('base64');
    await sec.store(SECRET_KEY, basic);
    log('✅ Stored Bitbucket credentials in SecretStorage.');
  } else {
    log('Using credentials from SecretStorage.');
  }
  
  const authHeader = `Basic ${basic}`;
  
  // Verify the credentials work
  try {
    log('Testing authentication...');
    const testUrl = 'https://api.bitbucket.org/2.0/user';
    const response = await fetch(testUrl, {
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      }
    });
    
    if (response.ok) {
      const userData = await response.json();
      log(`✅ Authentication successful! User: ${userData.display_name}`);
      return authHeader;
    } else {
      const errorText = await response.text();
      log(`❌ Authentication failed: ${response.status}`);
      
      // Clear invalid credentials
      await sec.delete(SECRET_KEY);
      vscode.window.showErrorMessage(`Authentication failed (${response.status}). Please enter your credentials again.`);
      
      // Retry by calling this function again
      return getAuthHeader(context);
    }
  } catch (error) {
    log(`❌ Authentication error: ${error.message}`);
    throw error;
  }
}
async function clearSecretAuth(context) {
  await context.secrets.delete(SECRET_KEY);
  vscode.window.showInformationMessage('Bitbucket credentials cleared from SecretStorage.');
  log('Cleared Bitbucket credentials from SecretStorage.');
}

// Add this function
async function cmdForceResetAuth(context) {
  await context.secrets.delete(SECRET_KEY);
  vscode.window.showInformationMessage('✅ Bitbucket credentials cleared. You will be prompted for credentials on next use.');
  log('Force reset credentials');
}


async function showEnvHelp() {
  const help =
`Enterprise env setup (recommended):

Windows (PowerShell):
  setx BITBUCKET_EMAIL "you@example.com"
  setx BITBUCKET_TOKEN "app-password-or-token"
  # Restart VS Code to pick up new env

macOS/Linux (bash/zsh):
  export BITBUCKET_EMAIL="you@example.com"
  export BITBUCKET_TOKEN="app-password-or-token"
  # Add to ~/.bashrc or ~/.zshrc for persistence
`;
  log(help);
  vscode.window.showInformationMessage('Environment setup instructions written to "BB PR Copilot" output.');
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
function hashForComment(prId, filePath, toLine, content) {
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

// ---- CLIPBOARD + PARSER HELPERS ----
async function readClipboard() {
  try { return (await vscode.env.clipboard.readText())?.trim() || ''; }
  catch { return ''; }
}

/**
 * Collect ALL open files:
 *  - visible editors
 *  - loaded textDocuments
 *  - ALL tabs (including preview tabs) via window.tabGroups
 */
function getOpenSourceFiles() {
  const set = new Set();

  // Visible editors
  for (const e of vscode.window.visibleTextEditors || []) {
    if (e?.document && !e.document.isUntitled && e.document.uri.scheme === 'file') {
      set.add(normalizeRel(e.document.fileName));
    }
  }

  // Loaded docs
  for (const d of vscode.workspace.textDocuments || []) {
    if (!d.isUntitled && d.uri?.scheme === 'file') {
      set.add(normalizeRel(d.fileName));
    }
  }

  // Tabs (this picks up preview tabs and tabs in background groups)
  try {
    const groups = vscode.window.tabGroups?.all || [];
    for (const g of groups) {
      for (const t of g.tabs || []) {
        const input = t.input;
        // Duck-typed: TabInputText has .uri
        const uri = input?.uri || input?.textUri || null;
        if (uri?.scheme === 'file') {
          set.add(normalizeRel(uri.fsPath));
        }
      }
    }
  } catch (e) {
    log(`TabGroups scan failed: ${e.message}`);
  }

  const all = Array.from(set).filter(isSourceLike);
  log(`Batch discovery: editors=${(vscode.window.visibleTextEditors||[]).length}, docs=${(vscode.workspace.textDocuments||[]).length}, tabs=${(vscode.window.tabGroups?.all||[]).reduce((n,g)=>n+(g.tabs?.length||0),0)} ⇒ openSourceFiles=${JSON.stringify(all)}`);
  return all;
}

/**
 * Parse clipboard into [{file, line|null, feedback}]
 * Supports:
 *  - "src/app.py:25 Some suggestion"
 *  - "src/app.py line 25: Some suggestion"
 *  - "file: src/app.py line: 25" then block lines
 *  - "src/app.py (general): Overall feedback"
 */
function parseClipboardSuggestions(text) {
  const lines = text.split(/\r?\n/);
  const out = [];
  const patInline = /^\s*(.+?)\s*(?::\s*(\d+)|\s*[-\s]\s*line\s*(\d+)|\s*\(general\))?\s*[:\-]\s*(.+)\s*$/i;
  const patHeader = /^\s*file\s*:\s*(.+?)\s*(?:line\s*:\s*(\d+))?\s*$/i;

  let i = 0;
  while (i < lines.length) {
    const L = lines[i];

    const hb = L.match(patHeader);
    if (hb) {
      const file = hb[1].trim();
      const line = hb[2] ? parseInt(hb[2], 10) : null;
      i++;
      const buf = [];
      while (i < lines.length && lines[i].trim() !== '') { buf.push(lines[i]); i++; }
      const feedback = buf.join('\n').trim();
      if (file && feedback) out.push({ file: toPosix(file), line, feedback });
      while (i < lines.length && lines[i].trim() === '') i++;
      continue;
    }

    const m = L.match(patInline);
    if (m) {
      const file = toPosix(m[1].trim());
      const line = m[2] ? parseInt(m[2], 10) : (m[3] ? parseInt(m[3], 10) : null);
      const general = /\(general\)/i.test(L);
      const feedback = (m[4] || '').trim();
      if (file && feedback) out.push({ file, line: general ? null : line, feedback });
      i++; continue;
    }

    i++;
  }
  return out;
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

// ---------- BATCH (manual paste for selected open files) ----------
async function cmdPostBatchForOpenFiles(context) {
  const allOpen = getOpenSourceFiles();
  if (!allOpen.length) {
    log('Batch: no open source files detected');
    return vscode.window.showInformationMessage('No open source files to post for.');
  }

  const pickTargets = await vscode.window.showQuickPick(
    allOpen.map(f => ({ label: f, picked: true })),
    { canPickMany: true, title: 'Batch Post: select open files to include', placeHolder: 'Uncheck files you don’t want in this batch' }
  );
  if (!pickTargets || pickTargets.length === 0) return;
  const files = pickTargets.map(i => i.label);

  const { prId, authHeader } = await ensurePrForCurrentBranch(context);
  if (!prId) return;

  log(`Batch: openFiles=${JSON.stringify(files)}`);

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
      ignoreFocusOut: true,
      validateInput: (v) => v?.trim()?.length ? null : 'Feedback required'
    });
    if (!feedback?.trim()) continue;

    const rel = toPosix(f);
    if (line) {
      plans.push({ kind: 'inline', relPosix: rel, toLine: line, body: makeInlineComment(f, line, feedback.trim()) });
    } else {
      plans.push({ kind: 'general', relPosix: rel, body: makeGeneralComment(f, feedback.trim()) });
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
    } else {
      await postGeneralIfNew(prId, p.body, authHeader);
    }
    posted++;
  }
  vscode.window.showInformationMessage(`✅ Posted ${posted} comment(s) to PR #${prId}`);
}

// ---------- BATCH FROM CLIPBOARD (selected open files) ----------
async function cmdBatchPostFromClipboard(context) {
  const allOpen = getOpenSourceFiles();
  if (!allOpen.length) {
    log('Batch-Clipboard: no open source files');
    return vscode.window.showInformationMessage('No open source files.');
  }

  const pickTargets = await vscode.window.showQuickPick(
    allOpen.map(f => ({ label: f, picked: true })),
    { canPickMany: true, title: 'Clipboard → Batch: select open files to include', placeHolder: 'Uncheck files you don’t want in this batch' }
  );
  if (!pickTargets || pickTargets.length === 0) return;
  const openFiles = pickTargets.map(i => i.label);

  const clip = await readClipboard();
  if (!clip) return vscode.window.showWarningMessage('Clipboard is empty.');
  const parsed = parseClipboardSuggestions(clip);

  const { prId, authHeader } = await ensurePrForCurrentBranch(context);
  if (!prId) return;

  log(`Batch-Clipboard: openFiles=${JSON.stringify(openFiles)}`);
  log(`Batch-Clipboard: parsedEntries=${parsed.length}`);

  const plans = [];
  let matched = 0;
  for (const p of parsed) {
    const rel = normalizeRel(p.file);
    if (!openFiles.includes(rel)) continue;
    matched++;
    if (p.line) {
      plans.push({ kind: 'inline', relPosix: rel, toLine: p.line, body: makeInlineComment(rel, p.line, p.feedback) });
    } else {
      plans.push({ kind: 'general', relPosix: rel, body: makeGeneralComment(rel, p.feedback) });
    }
  }
  log(`Batch-Clipboard: matchedEntries=${matched}`);

  if (!plans.length) {
    const applyAll = await vscode.window.showQuickPick(
      [
        { label: 'Apply clipboard to ALL selected open files (general comment)', val: 'all' },
        { label: 'Cancel', val: 'cancel' }
      ],
      { title: 'No structured matches found', placeHolder: 'Choose how to proceed' }
    );
    if (!applyAll || applyAll.val === 'cancel') return;

    for (const f of openFiles) {
      plans.push({ kind: 'general', relPosix: f, body: makeGeneralComment(f, clip) });
    }
    log(`Batch-Clipboard: fallback applying clipboard to ${openFiles.length} files as general`);
  }

  const items = plans.map(p => ({
    label: p.kind === 'inline' ? `${p.relPosix}:${p.toLine}` : `${p.relPosix} (general)`,
    description: p.kind === 'inline' ? 'Inline' : 'General',
    detail: summarize(p.body),
    picked: true,
    plan: p
  }));
  const picked = await vscode.window.showQuickPick(items, {
    title: 'Clipboard → PR (Selected Open Files)',
    canPickMany: true,
    matchOnDetail: true,
    placeHolder: 'Uncheck anything you do NOT want to post'
  });
  if (!picked?.length) return;

  let posted = 0;
  for (const i of picked) {
    const p = i.plan;
    if (p.kind === 'inline') {
      await postInlineIfNew(prId, p.relPosix, p.toLine, p.body, authHeader);
    } else {
      await postGeneralIfNew(prId, p.body, authHeader);
    }
    posted++;
  }
  vscode.window.showInformationMessage(`✅ Posted ${posted} clipboard comment(s) to PR #${prId}`);
}

// ---------- QUICK WRAPPER ----------
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
  output = vscode.window.createOutputChannel('BB PR Copilot');
  context.subscriptions.push(output);
  output.show(true);
  log('Extension activating…');

  // Register debug commands FIRST
  context.subscriptions.push(
    vscode.commands.registerCommand('bitbucketPRCopilot.debugEnv', () => cmdDebugEnv())
  );
  context.subscriptions.push(
    vscode.commands.registerCommand('bitbucketPRCopilot.debugAuth', () => cmdDebugAuth(context))
  );

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

      // Manual paste flows
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.testGit', () => cmdTestGit()));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postGeneralForCurrentFile', () => cmdPostGeneralForCurrentFile(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postInlineAtSelection', () => cmdPostInlineAtSelection(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postInlineAtLine', () => cmdPostInlineAtLine(context)));

      // Batch flows
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postBatchForOpenFiles', () => cmdPostBatchForOpenFiles(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.batchPostFromClipboard', () => cmdBatchPostFromClipboard(context)));

      // Quick wrapper + auth helpers
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.quickPost', () => cmdQuickPost(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.clearApiToken', async () => clearSecretAuth(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.showEnvHelp', () => showEnvHelp()));
      // Register it in activate function
context.subscriptions.push(
  vscode.commands.registerCommand('bitbucketPRCopilot.forceResetAuth', () => cmdForceResetAuth(context))
);
      log('All commands registered successfully.');
      
      // Test if environment variables are available
      setTimeout(() => {
        const envEmail = process.env.BITBUCKET_EMAIL;
        const envToken = process.env.BITBUCKET_TOKEN;
        if (envEmail && envToken) {
          log('✅ Environment variables detected on startup');
        } else {
          log('ℹ️  Environment variables not detected, will use SecretStorage');
        }
      }, 1000);
      
    } catch (e) {
      vscode.window.showErrorMessage(`Activation failed: ${e.message}`);
      log(`Activation failed: ${e.stack || e.message}`);
    }
  })();
}

function deactivate() {}

module.exports = { activate, deactivate };