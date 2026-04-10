const vscode = require('vscode');
const simpleGit = require('simple-git');
const path = require('path');
const crypto = require('crypto');

// ---------- DEFAULTS (overridable via settings) ----------
const DEFAULTS = {
  workspace: 'AOLDF',
  repo: 'uipoc',
  baseBranch: 'develop',
  mergeBranch: '' // New: branch to merge FROM
};
const SECRET_KEY = 'bitbucket-basic-auth';

// ---------- LOGGING ----------
let output;
function log(msg) {
  try {
    const time = new Date().toISOString();
    output?.appendLine(`[${time}] ${msg}`);
  } catch { /* noop */ }
}

// ---------- SETTINGS (UPDATED WITH MERGE BRANCH) ----------
async function getCfg() {
  const cfg = vscode.workspace.getConfiguration('bitbucketPRCopilot');
  
  let workspace = cfg.get('workspace') || DEFAULTS.workspace;
  let repo = cfg.get('repo') || DEFAULTS.repo;
  let baseBranch = cfg.get('baseBranch') || DEFAULTS.baseBranch;
  let mergeBranch = cfg.get('mergeBranch') || DEFAULTS.mergeBranch;

  // If defaults are being used, prompt user to confirm or change
  if (workspace === DEFAULTS.workspace || repo === DEFAULTS.repo || !mergeBranch) {
    const shouldConfigure = await vscode.window.showInformationMessage(
      `Configure Bitbucket Project/Repo? Current: ${workspace}/${repo} (merge: ${mergeBranch || 'not set'})`,
      'Configure', 'Use Defaults'
    );

    if (shouldConfigure === 'Configure') {
      // Prompt for Project Name
      workspace = await vscode.window.showInputBox({
        prompt: 'Enter Bitbucket Project Name',
        value: workspace,
        placeHolder: 'e.g., AOLDF',
        ignoreFocusOut: true,
        validateInput: (value) => value && value.trim() ? null : 'Project name is required'
      }) || workspace;

      // Prompt for Repo Name
      repo = await vscode.window.showInputBox({
        prompt: 'Enter Bitbucket Repository Name',
        value: repo,
        placeHolder: 'e.g., uipoc',
        ignoreFocusOut: true,
        validateInput: (value) => value && value.trim() ? null : 'Repository name is required'
      }) || repo;

      // Prompt for Base Branch (target branch - where PR will be merged TO)
      baseBranch = await vscode.window.showInputBox({
        prompt: 'Enter Target Branch for PRs (where PR will be merged TO)',
        value: baseBranch,
        placeHolder: 'e.g., develop, feature/oct_copilot_2',
        ignoreFocusOut: true,
        validateInput: (value) => value && value.trim() ? null : 'Target branch is required'
      }) || baseBranch;

      // Prompt for Merge Branch (source branch - where PR will be merged FROM)
      mergeBranch = await vscode.window.showInputBox({
        prompt: 'Enter Source Branch for PRs (where PR will be merged FROM)',
        value: mergeBranch,
        placeHolder: 'e.g., feature/oct_copilot_1, main',
        ignoreFocusOut: true,
        validateInput: (value) => value && value.trim() ? null : 'Source branch is required'
      }) || mergeBranch;

      // Save to settings
      await cfg.update('workspace', workspace, vscode.ConfigurationTarget.Global);
      await cfg.update('repo', repo, vscode.ConfigurationTarget.Global);
      await cfg.update('baseBranch', baseBranch, vscode.ConfigurationTarget.Global);
      await cfg.update('mergeBranch', mergeBranch, vscode.ConfigurationTarget.Global);
      
      log(`Configuration saved: ${workspace}/${repo} | Merge: ${mergeBranch} -> ${baseBranch}`);
    }
  }

  return { workspace, repo, baseBranch, mergeBranch };
}

// ---------- WORKSPACE ----------
const workspaceFolders = vscode.workspace.workspaceFolders;
const repoPath = workspaceFolders?.[0]?.uri.fsPath;
let git = null;
const postedHashes = new Set();
const existingHashesByPR = new Map();

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
    const username = await vscode.window.showInputBox({ 
      prompt: 'Bitbucket Username', 
      ignoreFocusOut: true 
    });
    const password = await vscode.window.showInputBox({ 
      prompt: 'Bitbucket Password', 
      password: true, 
      ignoreFocusOut: true 
    });
    if (!username || !password) throw new Error('Bitbucket credentials are required.');
    basic = Buffer.from(`${username}:${password}`).toString('base64');
    await sec.store(SECRET_KEY, basic);
    log('Stored Bitbucket credentials in SecretStorage.');
  }
  return `Basic ${basic}`;
}

// ---------- HTTP HELPERS ----------
async function bbFetch(url, { method='GET', headers={}, body, authHeader }, retries = 2) {
  const options = {
    method,
    headers: { 
      'Accept': 'application/json', 
      'Content-Type': 'application/json', 
      'Authorization': authHeader, 
      ...headers 
    },
    body
  };
  
  log(`Making ${method} request to: ${url}`);
  const res = await fetch(url, options);
  
  if (res.status === 401) throw new Error('Unauthorized (401). Check Bitbucket credentials.');
  if (res.status === 429 && retries > 0) {
    const wait = parseInt(res.headers.get('Retry-After') || '2', 10) * 1000;
    log(`Rate limited; retrying in ${wait} ms`);
    await new Promise(r => setTimeout(r, wait));
    return bbFetch(url, { method, headers, body, authHeader }, retries - 1);
  }
  
  if (!res.ok) {
    const errorText = await res.text();
    log(`HTTP ${res.status} Error for ${url}: ${errorText}`);
    throw new Error(`${method} ${url} failed: ${res.status} ${errorText}`);
  }
  
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : res.text();
}

async function bbPaginate(url, opts) {
  const values = [];
  let next = url;
  let start = 0;
  
  while (next) {
    const page = await bbFetch(next, opts);
    values.push(...(page.values || []));
    
    if (page.isLastPage === true || !page.nextPageStart) {
      break;
    }
    start = page.nextPageStart;
    next = `${url}${url.includes('?') ? '&' : '?'}start=${start}`;
  }
  return values;
}

// ---------- BITBUCKET DATA CENTER HELPERS ----------
function prBase(workspace, repo) {
  return `https://scm.horizon.dif.bankofamerica.com/rest/api/latest/projects/${workspace}/repos/${repo}/pull-requests`;
}

async function getPRById(workspace, repo, prId, authHeader) {
  const url = `${prBase(workspace, repo)}/${prId}`;
  log(`Getting PR directly by ID: ${url}`);
  
  try {
    const pr = await bbFetch(url, { authHeader });
    log(`Direct PR fetch successful: ${pr.id} - ${pr.title}`);
    return pr;
  } catch (error) {
    log(`Direct PR fetch failed: ${error.message}`);
    return null;
  }
}

async function findPRForBranch(workspace, repo, baseBranch, branch, authHeader) {
  log(`=== DEBUG: Finding PR for ${workspace}/${repo} branch ${branch} -> ${baseBranch} ===`);
  
  // STRATEGY 1: Try direct access to common PR numbers
  const commonPRNumbers = [3, 1, 2, 4, 5];
  for (const prNumber of commonPRNumbers) {
    const pr = await getPRById(workspace, repo, prNumber, authHeader);
    if (pr && pr.state === 'OPEN') {
      const fromRef = pr.fromRef;
      const toRef = pr.toRef;
      const sourceBranch = fromRef?.displayId || fromRef?.id?.replace('refs/heads/', '');
      const targetBranch = toRef?.displayId || toRef?.id?.replace('refs/heads/', '');
      
      log(`Checking PR #${prNumber}: ${sourceBranch} -> ${targetBranch}`);
      
      if (sourceBranch === branch && targetBranch === baseBranch) {
        log(`✓ Found matching PR via direct access: #${pr.id}`);
        return pr.id;
      }
    }
  }
  
  // STRATEGY 2: Try REST API search
  log(`Trying REST API search...`);
  const searchUrl = `${prBase(workspace, repo)}?state=OPEN&limit=50`;
  try {
    const prs = await bbFetch(searchUrl, { authHeader });
    const values = prs.values || [];
    log(`REST API found ${values.length} open PRs`);
    
    for (const pr of values) {
      const fromRef = pr.fromRef;
      const toRef = pr.toRef;
      const sourceBranch = fromRef?.displayId || fromRef?.id?.replace('refs/heads/', '');
      const targetBranch = toRef?.displayId || toRef?.id?.replace('refs/heads/', '');
      
      log(`Checking PR #${pr.id}: ${sourceBranch} -> ${targetBranch}`);
      
      if (sourceBranch === branch && targetBranch === baseBranch) {
        log(`✓ Found matching PR via search: #${pr.id}`);
        return pr.id;
      }
    }
  } catch (error) {
    log(`REST API search failed: ${error.message}`);
  }
  
  // STRATEGY 3: Let user manually enter PR ID
  log(`No PR found automatically. Prompting user...`);
  const prId = await vscode.window.showInputBox({
    prompt: `No PR found for branch ${branch}. Enter existing PR ID (or leave empty to create new):`,
    placeHolder: 'e.g., 3',
    ignoreFocusOut: true
  });
  
  if (prId && prId.trim()) {
    const pr = await getPRById(workspace, repo, prId.trim(), authHeader);
    if (pr && pr.state === 'OPEN') {
      const fromRef = pr.fromRef;
      const toRef = pr.toRef;
      const sourceBranch = fromRef?.displayId || fromRef?.id?.replace('refs/heads/', '');
      
      if (sourceBranch === branch) {
        log(`✓ Using manually entered PR: #${pr.id}`);
        return pr.id;
      } else {
        vscode.window.showWarningMessage(`PR #${prId} is for branch "${sourceBranch}", not "${branch}"`);
      }
    } else {
      vscode.window.showWarningMessage(`PR #${prId} not found or not open`);
    }
  }
  
  log(`✗ No PR found for ${branch}`);
  return null;
}

async function createPullRequest(workspace, repo, baseBranch, sourceBranch, authHeader, title, description) {
  const url = prBase(workspace, repo);
  
  const body = {
    title: title || `Auto PR: ${sourceBranch} → ${baseBranch}`,
    description: description || 'Created by Bitbucket PR Copilot.',
    fromRef: {
      id: `refs/heads/${sourceBranch}`,
      repository: {
        slug: repo,
        project: { key: workspace }
      }
    },
    toRef: {
      id: `refs/heads/${baseBranch}`,
      repository: {
        slug: repo,
        project: { key: workspace }
      }
    }
  };
  
  log(`Creating PR: ${JSON.stringify(body, null, 2)}`);
  
  try {
    const pr = await bbFetch(url, { method: 'POST', body: JSON.stringify(body), authHeader });
    log(`PR creation response: ${JSON.stringify(pr)}`);
    
    if (pr && pr.id) {
      vscode.window.showInformationMessage(`✅ Created PR #${pr.id}`);
      return { id: pr.id };
    } else {
      throw new Error(`PR creation failed: No ID in response. Full response: ${JSON.stringify(pr)}`);
    }
  } catch (error) {
    log(`PR creation error: ${error.message}`);
    vscode.window.showErrorMessage(`❌ Failed to create PR: ${error.message}`);
    throw error;
  }
}

async function postPRComment(workspace, repo, prId, content, authHeader) {
  log(`Posting general comment to PR #${prId}`);
  const url = `${prBase(workspace, repo)}/${prId}/comments`;
  
  const payload = { 
    text: content
  };
  
  return bbFetch(url, { method: 'POST', body: JSON.stringify(payload), authHeader });
}

async function postInlinePRComment(workspace, repo, prId, pathRel, toLine, content, authHeader) {
  log(`Posting inline comment to ${pathRel} at line ${toLine} in PR #${prId}`);
  const url = `${prBase(workspace, repo)}/${prId}/comments`;
  
  const payload = { 
    text: content,
    anchor: {
      path: pathRel,
      line: toLine,
      lineType: 'ADDED',
      fileType: 'TO'
    }
  };
  
  log(`Inline comment payload: ${JSON.stringify(payload)}`);
  
  return bbFetch(url, { method: 'POST', body: JSON.stringify(payload), authHeader });
}

async function listPRComments(workspace, repo, prId, authHeader, filePath = null) {
  let url;
  
  if (filePath) {
    url = `${prBase(workspace, repo)}/${prId}/comments?path=${encodeURIComponent(filePath)}&limit=100`;
  } else {
    url = `${prBase(workspace, repo)}/${prId}/comments?limit=100`;
  }
  
  try {
    return await bbPaginate(url, { authHeader });
  } catch (error) {
    if (error.message.includes('path query parameter is required') && !filePath) {
      log('Bitbucket requires path parameter. Falling back to activities API...');
      
      const activitiesUrl = `${prBase(workspace, repo)}/${prId}/activities?limit=100`;
      const activities = await bbPaginate(activitiesUrl, { authHeader });
      
      const comments = activities.filter(activity => 
        activity.action === 'COMMENTED' && activity.comment
      ).map(activity => activity.comment);
      
      log(`Extracted ${comments.length} comments from activities API`);
      return comments;
    }
    throw error;
  }
}

// ---------- FIXED PR DIFF PARSING FOR src:// dst:// FORMAT ----------
async function getPRDiff(workspace, repo, prId, authHeader) {
  const url = `${prBase(workspace, repo)}/${prId}/diff`;
  log(`Fetching PR diff for #${prId}`);
  
  try {
    const diffResponse = await bbFetch(url, { 
      authHeader,
      headers: {
        'Accept': 'text/plain'
      }
    });
    
    log(`Diff response type: ${typeof diffResponse}`);
    log(`First 500 chars of diff: ${typeof diffResponse === 'string' ? diffResponse.substring(0, 500) : 'Not a string'}`);
    
    if (typeof diffResponse === 'string') {
      log(`Got string diff: ${diffResponse.length} characters`);
      return diffResponse;
    } else {
      const diffText = JSON.stringify(diffResponse);
      log(`Converted object to string: ${diffText.length} characters`);
      return diffText;
    }
  } catch (error) {
    log(`Failed to fetch PR diff: ${error.message}`);
    throw error;
  }
}

function parseDiffToChunks(diffText) {
  const chunks = [];
  const lines = diffText.split('\n');
  let currentFile = null;
  let currentChunk = null;
  
  log(`Parsing diff with ${lines.length} lines`);
  
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
        log(`Found file with src://dst:// format: ${currentFile}`);
      } else {
        const standardMatch = line.match(/diff --git a\/(.+?) b\/(.+)/);
        if (standardMatch) {
          currentFile = standardMatch[2];
          currentChunk = { file: currentFile, lines: [line] };
          log(`Found file with standard a/b format: ${currentFile}`);
        }
      }
    }
    else if (line.startsWith('new file mode') && currentChunk) {
      currentChunk.lines.push(line);
    }
    else if (line.startsWith('index') && currentChunk) {
      currentChunk.lines.push(line);
    }
    else if (line.startsWith('---')) {
      if (currentChunk) {
        currentChunk.lines.push(line);
      }
      const srcMatch = line.match(/--- src:\/\/(.+)/);
      if (srcMatch && !currentFile) {
        currentFile = srcMatch[1];
      }
    }
    else if (line.startsWith('+++')) {
      if (currentChunk) {
        currentChunk.lines.push(line);
      }
      const dstMatch = line.match(/\+\+\+ dst:\/\/(.+)/);
      if (dstMatch) {
        currentFile = dstMatch[1];
        if (!currentChunk) {
          currentChunk = { file: currentFile, lines: [line] };
        } else if (currentChunk.file !== currentFile) {
          currentChunk.file = currentFile;
        }
        log(`Set file from +++ line: ${currentFile}`);
      }
    }
    else if (line.startsWith('@@')) {
      if (currentChunk) {
        currentChunk.lines.push(line);
      } else if (currentFile) {
        currentChunk = { file: currentFile, lines: [line] };
      }
    }
    else if (currentChunk) {
      currentChunk.lines.push(line);
    }
  }
  
  if (currentChunk && currentChunk.lines.length > 0) {
    chunks.push(currentChunk);
  }
  
  log(`Parsed ${chunks.length} diff chunks from PR`);
  return chunks;
}

function formatDiffForCopilot(chunks) {
  if (chunks.length === 0) {
    log('No chunks to format for Copilot');
    return 'No changes found in PR diff.';
  }
  
  const sections = [];
  
  for (const chunk of chunks) {
    if (chunk.lines.length > 0 && chunk.file) {
      sections.push(`## File: ${chunk.file}`);
      sections.push('```diff');
      sections.push(...chunk.lines);
      sections.push('```');
      sections.push('');
    }
  }
  
  const result = sections.join('\n');
  log(`Formatted diff for Copilot: ${result.length} characters, ${sections.filter(s => s.includes('## File:')).length} files`);
  
  return result;
}

// ---------- PR SESSION ----------
async function ensurePrForCurrentBranch(context) {
  const authHeader = await getAuthHeader(context);
  const status = await git.status();
  const branch = status.current;
  log(`Current branch=${branch}`);

  const { workspace, repo, baseBranch, mergeBranch } = await getCfg();

  const sourceBranch = mergeBranch || branch;

  if (branch === baseBranch && !mergeBranch) {
    vscode.window.showWarningMessage(`You're on ${baseBranch}. Switch to a feature branch or set merge branch.`);
    return { prId: null, authHeader, workspace, repo, baseBranch, sourceBranch };
  }

  let prId = await findPRForBranch(workspace, repo, baseBranch, sourceBranch, authHeader);
  if (!prId) {
    log(`No PR found for ${sourceBranch}. Prompting to create new PR.`);
    const confirm = await vscode.window.showInformationMessage(
      `No PR found for ${sourceBranch}. Create new PR to ${baseBranch} in ${workspace}/${repo}?`, 
      'Create PR', 
      'Cancel'
    );
    
    if (confirm !== 'Create PR') {
      log(`User cancelled PR creation`);
      return { prId: null, authHeader, workspace, repo, baseBranch, sourceBranch };
    }
    
    try {
      const pr = await createPullRequest(workspace, repo, baseBranch, sourceBranch, authHeader);
      prId = pr.id;
      log(`Successfully created PR #${prId}`);
    } catch (error) {
      log(`PR creation failed: ${error.message}`);
      return { prId: null, authHeader, workspace, repo, baseBranch, sourceBranch };
    }
  } else {
    log(`Using existing PR #${prId}`);
    vscode.window.showInformationMessage(`📝 Using PR #${prId} in ${workspace}/${repo} (${sourceBranch} -> ${baseBranch})`);
  }
  
  return { prId, authHeader, workspace, repo, baseBranch, sourceBranch };
}

// ---------- DEDUPE ----------
function hashForComment(prId, filePath, toLine, content) {
  const target = `${prId}|${filePath || ''}|${toLine || 0}|${content}`;
  return crypto.createHash('sha1').update(target).digest('hex');
}

async function ensureExistingCommentHashes(workspace, repo, prId, authHeader) {
  if (existingHashesByPR.has(prId)) return existingHashesByPR.get(prId);
  
  const values = await listPRComments(workspace, repo, prId, authHeader);
  const set = new Set();
  
  for (const c of values) {
    const content = c?.text || '';
    const anchor = c?.anchor || {};
    const p = anchor.path ? toPosix(anchor.path.toString()) : null;
    const to = typeof anchor.line === 'number' ? anchor.line : null;
    const sig = hashForComment(prId, p, to, content);
    set.add(sig);
  }
  
  existingHashesByPR.set(prId, set);
  log(`Loaded ${set.size} existing comment signatures from PR #${prId}`);
  return set;
}

async function postInlineIfNew(workspace, repo, prId, pathRel, toLine, content, authHeader) {
  const existing = await ensureExistingCommentHashes(workspace, repo, prId, authHeader);
  const sig = hashForComment(prId, pathRel, toLine, content);
  if (postedHashes.has(sig) || existing.has(sig)) {
    log(`Deduped inline comment (already exists): ${pathRel}@${toLine}`);
    return;
  }
  await postInlinePRComment(workspace, repo, prId, pathRel, toLine, content, authHeader);
  postedHashes.add(sig);
  existing.add(sig);
}

async function postGeneralIfNew(workspace, repo, prId, content, authHeader) {
  const existing = await ensureExistingCommentHashes(workspace, repo, prId, authHeader);
  const sig = hashForComment(prId, null, null, content);
  if (postedHashes.has(sig) || existing.has(sig)) {
    log(`Deduped general comment (already exists)`);
    return;
  }
  await postPRComment(workspace, repo, prId, content, authHeader);
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

// ---------- COLLECT OPEN SOURCE FILES ----------
function collectOpenSourceFiles() {
  const rel = (uri) => vscode.workspace.asRelativePath(uri.fsPath);
  const set = new Set();

  try {
    for (const group of vscode.window.tabGroups?.all || []) {
      for (const tab of group.tabs || []) {
        const input = tab.input;
        const uri = input?.uri || input?.['uri'];
        if (uri?.scheme === 'file') set.add(rel(uri));
      }
    }
  } catch (_) { /* ignore */ }

  for (const ed of vscode.window.visibleTextEditors || []) {
    const uri = ed.document?.uri;
    if (uri?.scheme === 'file') set.add(rel(uri));
  }

  for (const doc of vscode.workspace.textDocuments || []) {
    const uri = doc?.uri;
    if (uri?.scheme === 'file') set.add(rel(uri));
  }

  return [...set].filter(isSourceLike);
}

// ---------- CORE COMMANDS ----------
async function cmdTestGit() {
  const status = await git.status();
  const { workspace, repo, baseBranch, mergeBranch } = await getCfg();
  const branchInfo = `Current branch: ${status.current} | Project: ${workspace}/${repo} | Merge: ${mergeBranch || 'Current'} -> ${baseBranch}`;
  vscode.window.showInformationMessage(branchInfo);
  log(`TestGit: ${branchInfo}`);
}

async function cmdPostGeneralForCurrentFile(context) {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return vscode.window.showWarningMessage('Open a file first.');
  const filePath = vscode.workspace.asRelativePath(editor.document.fileName);
  if (!isSourceLike(filePath)) return vscode.window.showWarningMessage('Not a source file.');

  const { prId, authHeader, workspace, repo, sourceBranch, baseBranch } = await ensurePrForCurrentBranch(context);
  if (!prId) return;

  const feedback = await vscode.window.showInputBox({
    prompt: `Paste Copilot/Chat feedback for ${filePath} (general PR comment)`,
    ignoreFocusOut: true,
    validateInput: (v) => v?.trim()?.length ? null : 'Feedback required'
  });
  if (!feedback) return;

  const body = makeGeneralComment(filePath, feedback);
  const confirm = await vscode.window.showQuickPick(
    [{ label: `Post general review to PR #${prId} (${sourceBranch} -> ${baseBranch})`, detail: summarize(body), picked: true }],
    { canPickMany: false, title: 'Preview general comment' }
  );
  if (!confirm) return;

  await postGeneralIfNew(workspace, repo, prId, body, authHeader);
  vscode.window.showInformationMessage('✅ Posted general comment.');
}

async function cmdPostInlineAtSelection(context) {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return vscode.window.showWarningMessage('Open a file first.');
  const filePath = vscode.workspace.asRelativePath(editor.document.fileName);
  if (!isSourceLike(filePath)) return vscode.window.showWarningMessage('Not a source file.');
  if (editor.selection.isEmpty) return vscode.window.showWarningMessage('Select the code where you want to attach the comment.');

  const { prId, authHeader, workspace, repo, sourceBranch, baseBranch } = await ensurePrForCurrentBranch(context);
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
    [{ label: `Post inline to ${rel}:${line} in PR #${prId} (${sourceBranch} -> ${baseBranch})`, detail: summarize(body), picked: true }],
    { canPickMany: false, title: 'Preview inline comment' }
  );
  if (!confirm) return;

  await postInlineIfNew(workspace, repo, prId, rel, line, body, authHeader);
  vscode.window.showInformationMessage('✅ Posted inline comment.');
}

async function cmdPostInlineAtLine(context) {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return vscode.window.showWarningMessage('Open a file first.');
  const filePath = vscode.workspace.asRelativePath(editor.document.fileName);
  if (!isSourceLike(filePath)) return vscode.window.showWarningMessage('Not a source file.');

  const { prId, authHeader, workspace, repo, sourceBranch, baseBranch } = await ensurePrForCurrentBranch(context);
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
    [{ label: `Post inline to ${rel}:${line} in PR #${prId} (${sourceBranch} -> ${baseBranch})`, detail: summarize(body), picked: true }],
    { canPickMany: false, title: 'Preview inline comment' }
  );
  if (!confirm) return;

  await postInlineIfNew(workspace, repo, prId, rel, line, body, authHeader);
  vscode.window.showInformationMessage('✅ Posted inline comment.');
}

async function cmdPostBatchForOpenFiles(context) {
  const files = collectOpenSourceFiles();
  if (!files.length) {
    return vscode.window.showInformationMessage('No open source files to post for.');
  }

  const { prId, authHeader, workspace, repo, sourceBranch, baseBranch } = await ensurePrForCurrentBranch(context);
  if (!prId) return;

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
      await postInlineIfNew(workspace, repo, prId, p.relPosix, p.toLine, p.body, authHeader);
      posted++;
    } else {
      await postGeneralIfNew(workspace, repo, prId, p.body, authHeader);
      posted++;
    }
  }
  vscode.window.showInformationMessage(`✅ Posted ${posted} comment(s) to PR #${prId} (${sourceBranch} -> ${baseBranch})`);
}

// ---------- QUICK POST ----------
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

// ---------- CONFIGURATION MANAGEMENT ----------
async function cmdConfigureSettings() {
  const cfg = vscode.workspace.getConfiguration('bitbucketPRCopilot');
  
  const workspace = await vscode.window.showInputBox({
    prompt: 'Enter Bitbucket Project Name',
    value: cfg.get('workspace') || DEFAULTS.workspace,
    placeHolder: 'e.g., AOLDF',
    ignoreFocusOut: true,
    validateInput: (value) => value && value.trim() ? null : 'Project name is required'
  });

  if (!workspace) return;

  const repo = await vscode.window.showInputBox({
    prompt: 'Enter Bitbucket Repository Name',
    value: cfg.get('repo') || DEFAULTS.repo,
    placeHolder: 'e.g., uipoc',
    ignoreFocusOut: true,
    validateInput: (value) => value && value.trim() ? null : 'Repository name is required'
  });

  if (!repo) return;

  const baseBranch = await vscode.window.showInputBox({
    prompt: 'Enter Target Branch for PRs (where PR will be merged TO)',
    value: cfg.get('baseBranch') || DEFAULTS.baseBranch,
    placeHolder: 'e.g., develop, feature/oct_copilot_2',
    ignoreFocusOut: true,
    validateInput: (value) => value && value.trim() ? null : 'Target branch is required'
  });

  if (!baseBranch) return;

  const mergeBranch = await vscode.window.showInputBox({
    prompt: 'Enter Source Branch for PRs (where PR will be merged FROM)',
    value: cfg.get('mergeBranch') || DEFAULTS.mergeBranch,
    placeHolder: 'e.g., feature/oct_copilot_1, main',
    ignoreFocusOut: true,
    validateInput: (value) => value && value.trim() ? null : 'Source branch is required'
  });

  if (!mergeBranch) return;

  await cfg.update('workspace', workspace, vscode.ConfigurationTarget.Global);
  await cfg.update('repo', repo, vscode.ConfigurationTarget.Global);
  await cfg.update('baseBranch', baseBranch, vscode.ConfigurationTarget.Global);
  await cfg.update('mergeBranch', mergeBranch, vscode.ConfigurationTarget.Global);
  
  vscode.window.showInformationMessage(`✅ Configuration saved: ${workspace}/${repo} | Merge: ${mergeBranch} -> ${baseBranch}`);
  log(`Configuration updated: ${workspace}/${repo} | Merge: ${mergeBranch} -> ${baseBranch}`);
}

async function cmdCleanAllSettings() {
  const cfg = vscode.workspace.getConfiguration('bitbucketPRCopilot');
  
  const confirm = await vscode.window.showWarningMessage(
    'Are you sure you want to reset ALL settings to defaults? This will clear project, repo, and branch configurations.',
    'Yes, Reset All',
    'Cancel'
  );

  if (confirm === 'Yes, Reset All') {
    await cfg.update('workspace', DEFAULTS.workspace, vscode.ConfigurationTarget.Global);
    await cfg.update('repo', DEFAULTS.repo, vscode.ConfigurationTarget.Global);
    await cfg.update('baseBranch', DEFAULTS.baseBranch, vscode.ConfigurationTarget.Global);
    await cfg.update('mergeBranch', DEFAULTS.mergeBranch, vscode.ConfigurationTarget.Global);
    
    vscode.window.showInformationMessage('✅ All settings reset to defaults');
    log('All settings reset to defaults');
  }
}

async function cmdShowCurrentConfig() {
  const cfg = vscode.workspace.getConfiguration('bitbucketPRCopilot');
  
  const workspace = cfg.get('workspace') || DEFAULTS.workspace;
  const repo = cfg.get('repo') || DEFAULTS.repo;
  const baseBranch = cfg.get('baseBranch') || DEFAULTS.baseBranch;
  const mergeBranch = cfg.get('mergeBranch') || DEFAULTS.mergeBranch;
  
  const configInfo = `
📋 Current Configuration:

Project: ${workspace}
Repository: ${repo}
Target Branch (merge TO): ${baseBranch}
Source Branch (merge FROM): ${mergeBranch || 'Current branch'}

PR Flow: ${mergeBranch || 'Current branch'} → ${baseBranch}
  `.trim();

  vscode.window.showInformationMessage(configInfo, { modal: true });
  log(`Current config: ${workspace}/${repo} | ${mergeBranch || 'Current'} -> ${baseBranch}`);
}

// ---------- ENHANCED COPILOT INTEGRATION ----------

// Patterns for suggestion type detection
const SUGGESTION_PATTERNS = {
  security: /security|vulnerability|injection|xss|auth|permission|sanitize|validate|exploit|hack|breach/i,
  performance: /performance|optimize|slow|bottleneck|memory|leak|efficient|speed|latency|timeout/i,
  bug: /bug|error|fix|issue|problem|defect|crash|exception|fail|broken/i,
  style: /style|format|convention|readability|maintainability|refactor|clean|consistent|indent|naming/i,
  test: /test|coverage|assert|mock|stub|spy|unit|integration|e2e|spec/i,
  logic: /logic|algorithm|condition|loop|recursion|iteration|complexity|race|deadlock|starvation/i
};

// NEW: Smart Copilot suggestion parser that extracts ONLY actionable items
function parseCopilotSuggestions(copilotResponse, chunks) {
  const suggestions = [];
  const lines = copilotResponse.split('\n');
  
  let currentFile = null;
  let currentLine = null;
  let collectingSuggestion = false;
  let suggestionLines = [];
  let suggestionType = null;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    
    // Skip empty lines at start
    if (!line && !collectingSuggestion) continue;
    
    // Detect file references (looking for actual file mentions)
    const fileMatch = line.match(/File:\s*["']?(.+?)["']?(?:\s*\(?Line\s*(\d+)\)?)?/i) ||
                     line.match(/##\s*["']?(.+?)["']?(?:\s*\(?Line\s*(\d+)\)?)?/i) ||
                     line.match(/In\s+["']?(.+?)["']?(?:\s*\(?line\s*(\d+)\)?)?/i) ||
                     line.match(/`(.+?)`(?:\s*\(?line\s*(\d+)\)?)?/i);
    
    if (fileMatch) {
      const fileName = fileMatch[1].replace(/`/g, '').trim();
      // Check if this is a real file from the diff chunks
      const isRealFile = chunks.some(chunk => 
        chunk.file.includes(fileName) || fileName.includes(chunk.file)
      );
      
      if (isRealFile) {
        // Save previous suggestion if exists
        if (collectingSuggestion && suggestionLines.length > 0 && currentFile) {
          const suggestion = createSuggestionObject(currentFile, currentLine, suggestionLines, suggestionType);
          if (suggestion) suggestions.push(suggestion);
        }
        
        currentFile = fileName;
        currentLine = fileMatch[2] ? parseInt(fileMatch[2]) : null;
        collectingSuggestion = false;
        suggestionLines = [];
        suggestionType = null;
        continue;
      }
    }
    
    // Detect line number references
    const lineMatch = line.match(/Line\s*(\d+)/i) || 
                     line.match(/at\s+line\s*(\d+)/i) ||
                     line.match(/\(line\s*(\d+)\)/i);
    
    if (lineMatch && currentFile) {
      // Save previous suggestion
      if (collectingSuggestion && suggestionLines.length > 0) {
        const suggestion = createSuggestionObject(currentFile, currentLine, suggestionLines, suggestionType);
        if (suggestion) suggestions.push(suggestion);
      }
      
      currentLine = parseInt(lineMatch[1]);
      collectingSuggestion = false;
      suggestionLines = [];
      suggestionType = null;
      continue;
    }
    
    // Detect suggestion markers (bullet points, numbered lists, etc.)
    const isSuggestionStart = line.match(/^(?:•|-|\d+\.|👉|💡|✅|❌|⚠️|🛑|📝|🔍)\s*/) || 
                             line.toLowerCase().includes('suggestion:') ||
                             line.toLowerCase().includes('recommendation:') ||
                             line.toLowerCase().includes('consider:') ||
                             line.toLowerCase().includes('issue:') ||
                             line.toLowerCase().includes('fix:') ||
                             line.toLowerCase().includes('improvement:') ||
                             line.toLowerCase().includes('problem:');
    
    if (isSuggestionStart && currentFile) {
      // Save previous suggestion
      if (collectingSuggestion && suggestionLines.length > 0) {
        const suggestion = createSuggestionObject(currentFile, currentLine, suggestionLines, suggestionType);
        if (suggestion) suggestions.push(suggestion);
      }
      
      // Start new suggestion
      collectingSuggestion = true;
      suggestionLines = [line];
      
      // Determine suggestion type
      suggestionType = determineSuggestionType(line);
      
      continue;
    }
    
    // If we're collecting a suggestion, add lines until we hit a break
    if (collectingSuggestion && currentFile) {
      // Check for break conditions
      const isBreak = line === '' && suggestionLines.length > 2 ||
                     line.startsWith('##') ||
                     line.startsWith('---') ||
                     line.toLowerCase().startsWith('file:') ||
                     line.toLowerCase().includes('overall') ||
                     line.toLowerCase().includes('summary');
      
      if (isBreak) {
        // End of this suggestion
        const suggestion = createSuggestionObject(currentFile, currentLine, suggestionLines, suggestionType);
        if (suggestion) suggestions.push(suggestion);
        
        collectingSuggestion = false;
        suggestionLines = [];
        suggestionType = null;
      } else if (line && !line.match(/^#{1,3}\s/) && !line.includes('```')) {
        // Add line to current suggestion (skip code blocks)
        suggestionLines.push(line);
      }
    }
  }
  
  // Save the last suggestion
  if (collectingSuggestion && suggestionLines.length > 0 && currentFile) {
    const suggestion = createSuggestionObject(currentFile, currentLine, suggestionLines, suggestionType);
    if (suggestion) suggestions.push(suggestion);
  }
  
  // Filter out low-quality suggestions and duplicates
  return filterSuggestions(suggestions);
}

function createSuggestionObject(file, line, suggestionLines, type) {
  // Join lines and clean up
  let content = suggestionLines
    .map(line => line.replace(/^(?:•|-|\d+\.|👉|💡|✅|❌|⚠️|🛑|📝|🔍)\s*/, ''))
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();
  
  // Skip if too short or just noise
  if (content.length < 10 || 
      content.toLowerCase().includes('no issues found') ||
      content.toLowerCase().includes('looks good') ||
      content.toLowerCase().includes('well done')) {
    return null;
  }
  
  // Add type emoji
  const emoji = type === 'security' ? '🔒' :
                type === 'performance' ? '⚡' :
                type === 'bug' ? '🐛' :
                type === 'style' ? '🎨' :
                type === 'test' ? '🧪' :
                type === 'logic' ? '🤔' : '💡';
  
  // Format the suggestion content
  const formattedContent = `${emoji} **${type ? type.charAt(0).toUpperCase() + type.slice(1) + ' Suggestion' : 'Suggestion'}**\n\n${content}`;
  
  return {
    file: file,
    line: line,
    content: formattedContent,
    type: type || 'general'
  };
}

function determineSuggestionType(line) {
  const lowerLine = line.toLowerCase();
  
  for (const [type, pattern] of Object.entries(SUGGESTION_PATTERNS)) {
    if (pattern.test(lowerLine)) {
      return type;
    }
  }
  
  return 'general';
}

function filterSuggestions(suggestions) {
  const seen = new Set();
  const filtered = [];
  
  for (const suggestion of suggestions) {
    if (!suggestion) continue;
    
    // Create a hash to detect duplicates
    const hash = `${suggestion.file}|${suggestion.line}|${suggestion.content.substring(0, 50)}`;
    
    if (!seen.has(hash) && suggestion.content.length > 20) {
      seen.add(hash);
      filtered.push(suggestion);
    }
  }
  
  return filtered;
}

function formatSuggestionPreview(suggestion) {
  const preview = suggestion.content
    .replace(/\*\*/g, '')
    .replace(/\n/g, ' ')
    .substring(0, 60);
  
  return suggestion.line 
    ? `Line ${suggestion.line}: ${preview}...`
    : `${preview}...`;
}

// NEW: Parse and post only specific suggestions
async function parseAndPostCopilotResponse(context, copilotResponse) {
  try {
    const prContext = context.globalState.get('currentPRContext');
    if (!prContext) {
      vscode.window.showWarningMessage('No PR context found. Please use "Send PR Diff to Copilot" first.');
      return;
    }

    const { prId, authHeader, workspace, repo, chunks } = prContext;
    
    // Parse the Copilot response to extract ONLY suggestions
    const suggestions = parseCopilotSuggestions(copilotResponse, chunks);
    
    if (suggestions.length === 0) {
      vscode.window.showWarningMessage('No actionable suggestions found in Copilot response.');
      return;
    }

    // Show preview and let user select which suggestions to post
    const suggestionItems = suggestions.map((suggestion, index) => ({
      label: `${suggestion.file}${suggestion.line ? `:${suggestion.line}` : ''}`,
      description: suggestion.type || 'Suggestion',
      detail: formatSuggestionPreview(suggestion),
      picked: true,
      suggestion
    }));

    const selectedSuggestions = await vscode.window.showQuickPick(suggestionItems, {
      title: 'Select specific Copilot suggestions to post',
      canPickMany: true,
      placeHolder: 'Choose which actionable suggestions to post to Bitbucket'
    });

    if (!selectedSuggestions || selectedSuggestions.length === 0) return;

    // Post selected suggestions
    let postedCount = 0;
    for (const item of selectedSuggestions) {
      const suggestion = item.suggestion;
      
      if (suggestion.line && suggestion.line > 0) {
        // Inline comment at specific line
        await postInlineIfNew(workspace, repo, prId, suggestion.file, suggestion.line, suggestion.content, authHeader);
      } else {
        // General comment for file (if no specific line)
        await postGeneralIfNew(workspace, repo, prId, suggestion.content, authHeader);
      }
      postedCount++;
      
      // Small delay to avoid rate limiting
      await new Promise(resolve => setTimeout(resolve, 300));
    }

    vscode.window.showInformationMessage(`✅ Posted ${postedCount} specific suggestions to PR #${prId}`);
    
  } catch (error) {
    vscode.window.showErrorMessage(`Failed to post Copilot suggestions: ${error.message}`);
    log(`Post Copilot suggestions error: ${error.message}`);
  }
}

// Enhanced Auto Copilot Review with direct posting
async function cmdAutoCopilotReview(context) {
  const { prId, authHeader, workspace, repo, sourceBranch, baseBranch } = await ensurePrForCurrentBranch(context);
  if (!prId) return;

  const reviewType = await vscode.window.showQuickPick([
    { label: 'Comprehensive Review', description: 'Security, performance, and best practices' },
    { label: 'Security Focus', description: 'Focus on security vulnerabilities' },
    { label: 'Performance Focus', description: 'Focus on performance issues' },
    { label: 'Code Quality', description: 'Focus on code standards and best practices' }
  ], {
    placeHolder: 'What type of automated review do you want?'
  });

  if (!reviewType) return;

  try {
    const diffText = await getPRDiff(workspace, repo, prId, authHeader);
    const chunks = parseDiffToChunks(diffText);
    
    if (chunks.length === 0) {
      vscode.window.showWarningMessage('No changes found in PR.');
      return;
    }

    // Store PR context for later use
    const prContext = { prId, authHeader, workspace, repo, chunks };
    context.globalState.update('currentPRContext', prContext);

    let promptPrefix = '';
    switch (reviewType.label) {
      case 'Security Focus':
        promptPrefix = `Review this pull request for SECURITY issues ONLY. Focus on:

🔒 CRITICAL SECURITY CHECKS:
- Input validation vulnerabilities
- Authentication/authorization flaws
- SQL injection possibilities
- XSS and injection vulnerabilities
- Insecure data storage/transmission
- Security misconfigurations

For each security issue found, provide:
1. The exact file and line number
2. The specific security problem
3. The suggested fix

DO NOT include entire file contents. Only point to specific issues.`;
        break;
      case 'Performance Focus':
        promptPrefix = `Review this pull request for PERFORMANCE issues ONLY. Focus on:

⚡ PERFORMANCE ASPECTS:
- Algorithm efficiency (time/space complexity)
- Memory leaks or inefficient resource usage
- Database query optimization opportunities
- Caching possibilities
- Bottlenecks in code execution

For each performance issue found, provide:
1. The exact file and line number
2. The specific performance problem
3. The suggested optimization

DO NOT include entire file contents. Only point to specific issues.`;
        break;
      case 'Code Quality':
        promptPrefix = `Review this pull request for CODE QUALITY issues ONLY. Focus on:

📋 CODE STANDARDS:
- Code readability and maintainability
- Consistency with project patterns
- Proper error handling
- Code duplication (DRY principle)
- Single responsibility principle
- Proper naming conventions

For each code quality issue found, provide:
1. The exact file and line number
2. The specific quality problem
3. The suggested improvement

DO NOT include entire file contents. Only point to specific issues.`;
        break;
      default:
        promptPrefix = `Review this pull request and provide SPECIFIC, ACTIONABLE suggestions. Focus on:

🔒 Security best practices
⚡ Performance optimizations
📋 Code quality and standards

For each issue found, provide:
1. The exact file and line number
2. The specific problem
3. The suggested fix

DO NOT include entire file contents. Only point to specific issues.`;
    }

    const fullPrompt = `${promptPrefix}\n\n${formatDiffForCopilot(chunks)}\n\nIMPORTANT: Provide suggestions as bullet points with file and line references. DO NOT paste entire files.`;

    // Auto-paste in Copilot chat
    await vscode.commands.executeCommand('workbench.panel.chat.view.copilot.focus');
    
    setTimeout(async () => {
      await vscode.env.clipboard.writeText(fullPrompt);
      await vscode.commands.executeCommand('editor.action.clipboardPasteAction');
      
      vscode.window.showInformationMessage(
        `Auto-review prompt pasted in Copilot! After getting response, use "Post Copilot Response".`,
        'Post Copilot Response',
        'Show Prompt'
      ).then((selection) => {
        if (selection === 'Post Copilot Response') {
          vscode.commands.executeCommand('bitbucketPRCopilot.postCopilotResponse');
        }
      });
    }, 1000);

  } catch (error) {
    vscode.window.showErrorMessage(`Failed to prepare automated review: ${error.message}`);
    log(`Auto review error: ${error.message}`);
  }
}

// Send PR diff to Copilot Chat
async function cmdSendDiffToCopilotChat(context) {
  const { prId, authHeader, workspace, repo, sourceBranch, baseBranch } = await ensurePrForCurrentBranch(context);
  if (!prId) return;

  try {
    await vscode.window.withProgress({
      location: vscode.ProgressLocation.Notification,
      title: `Preparing PR #${prId} for Copilot Review...`,
      cancellable: false
    }, async (progress) => {
      // Get PR diff
      progress.report({ message: 'Fetching diff from Bitbucket...' });
      const diffText = await getPRDiff(workspace, repo, prId, authHeader);
      
      // Parse diff
      progress.report({ message: 'Analyzing changes...' });
      const chunks = parseDiffToChunks(diffText);
      const copilotPrompt = formatDiffForCopilot(chunks);
      
      if (!copilotPrompt.trim()) {
        vscode.window.showWarningMessage('No changes found in PR diff.');
        return;
      }

      // Create review prompt that asks for specific suggestions
      const automatedPrompt = `Please review this pull request and provide SPECIFIC, ACTIONABLE suggestions.

IMPORTANT: DO NOT include entire file contents in your response. Only provide:
1. Specific issues found (security, performance, bugs, etc.)
2. Exact file and line number for each issue
3. The specific problem
4. The suggested fix

Format your response like this:
• File: example.js (Line 42) - Issue: [brief description] - Suggestion: [specific fix]

If no issues are found, simply say "No issues found."

Code Changes to Review:
${copilotPrompt}`;
      
      // Store PR context for later use
      const prContext = { prId, authHeader, workspace, repo, chunks };
      context.globalState.update('currentPRContext', prContext);
      
      // Auto-paste in Copilot chat
      progress.report({ message: 'Opening Copilot Chat...' });
      
      await vscode.commands.executeCommand('workbench.panel.chat.view.copilot.focus');
      
      setTimeout(async () => {
        await vscode.env.clipboard.writeText(automatedPrompt);
        await vscode.commands.executeCommand('editor.action.clipboardPasteAction');
        
        log(`Auto-pasted PR #${prId} review prompt in Copilot Chat`);
        
        vscode.window.showInformationMessage(
          `PR #${prId} review prompt auto-pasted in Copilot Chat!`,
          'Post Comments to Bitbucket',
          'Show Prompt'
        ).then(async (selection) => {
          if (selection === 'Post Comments to Bitbucket') {
            vscode.commands.executeCommand('bitbucketPRCopilot.postCopilotResponse');
          }
        });
      }, 1000);
    });
    
  } catch (error) {
    vscode.window.showErrorMessage(`Failed to prepare Copilot review: ${error.message}`);
    log(`Copilot review error: ${error.message}`);
  }
}

// Post Copilot Response command
async function cmdPostCopilotResponse(context) {
  const clipboardText = await vscode.env.clipboard.readText();
  
  if (!clipboardText.trim()) {
    vscode.window.showWarningMessage('No text in clipboard. Copy Copilot response first.');
    return;
  }

  const action = await vscode.window.showQuickPick([
    { 
      label: 'Parse and post specific suggestions', 
      description: 'Extract only actionable suggestions (no file dumps)'
    },
    { 
      label: 'Post as summary comment', 
      description: 'Post only a summary without specific details'
    }
  ], {
    placeHolder: 'How do you want to post the Copilot response?'
  });

  if (!action) return;

  if (action.label === 'Parse and post specific suggestions') {
    await parseAndPostCopilotResponse(context, clipboardText);
  } else {
    // Post as summary comment
    const prContext = context.globalState.get('currentPRContext');
    if (!prContext) {
      vscode.window.showWarningMessage('No PR context found. Please use "Send PR Diff to Copilot" first.');
      return;
    }

    const { prId, authHeader, workspace, repo } = prContext;
    
    // Create a concise summary
    const summary = createSummaryFromCopilotResponse(clipboardText);
    
    await postGeneralIfNew(workspace, repo, prId, summary, authHeader);
    vscode.window.showInformationMessage(`✅ Posted Copilot summary to PR #${prId}`);
  }
}

function createSummaryFromCopilotResponse(response) {
  // Count issues by type
  const issues = {
    security: (response.match(/security|vulnerability|injection|xss|auth/gi) || []).length,
    performance: (response.match(/performance|optimize|slow|bottleneck/gi) || []).length,
    bugs: (response.match(/bug|error|fix|issue/gi) || []).length,
    style: (response.match(/style|format|convention|readability/gi) || []).length
  };
  
  const summaryLines = ['🤖 **Copilot Review Summary**', ''];
  
  if (issues.security > 0) summaryLines.push(`🔒 **Security issues:** ${issues.security}`);
  if (issues.performance > 0) summaryLines.push(`⚡ **Performance suggestions:** ${issues.performance}`);
  if (issues.bugs > 0) summaryLines.push(`🐛 **Potential bugs:** ${issues.bugs}`);
  if (issues.style > 0) summaryLines.push(`🎨 **Style improvements:** ${issues.style}`);
  
  if (issues.security + issues.performance + issues.bugs + issues.style === 0) {
    summaryLines.push('✅ **No issues found.** Code looks good!');
  }
  
  summaryLines.push('');
  summaryLines.push('*Specific suggestions have been posted as inline comments.*');
  
  return summaryLines.join('\n');
}

// ---------- JIRA STORY REVIEW ----------
async function cmdReviewAgainstJiraStory(context) {
  const { prId, authHeader, workspace, repo, sourceBranch, baseBranch } = await ensurePrForCurrentBranch(context);
  if (!prId) return;

  try {
    await vscode.window.withProgress({
      location: vscode.ProgressLocation.Notification,
      title: 'Preparing Jira Story Review...',
      cancellable: false
    }, async (progress) => {
      
      // Step 1: Get Jira Story Details from user
      progress.report({ message: 'Gathering Jira story information...' });
      
      const jiraStoryId = await vscode.window.showInputBox({
        prompt: 'Enter Jira Story ID (e.g., PROJ-1234)',
        placeHolder: 'PROJ-1234',
        ignoreFocusOut: true,
        validateInput: (value) => value && value.trim() ? null : 'Jira Story ID is required'
      });
      
      if (!jiraStoryId) return;
      
      const acceptanceCriteria = await vscode.window.showInputBox({
        prompt: 'Paste Acceptance Criteria from Jira story',
        placeHolder: 'AC1: User can login...\nAC2: Error messages display...',
        ignoreFocusOut: true,
        validateInput: (value) => value && value.trim() ? null : 'Acceptance criteria is required'
      });
      
      if (!acceptanceCriteria) return;
      
      // Step 2: Get PR diff
      progress.report({ message: 'Fetching PR diff from Bitbucket...' });
      const diffText = await getPRDiff(workspace, repo, prId, authHeader);
      const chunks = parseDiffToChunks(diffText);
      const copilotPrompt = formatDiffForCopilot(chunks);
      
      if (!copilotPrompt.trim()) {
        vscode.window.showWarningMessage('No changes found in PR diff.');
        return;
      }
      
      // Step 3: Create Jira-focused review prompt
      const jiraReviewPrompt = `JIRA STORY REVIEW: ${jiraStoryId}

ACCEPTANCE CRITERIA:
${acceptanceCriteria}

REVIEW TASK:
Review this pull request against the acceptance criteria above. For each criteria:
1. Indicate if it's ✅ Fully Met, ⚠️ Partially Met, or ❌ Not Met
2. Provide specific code references that satisfy the criteria
3. Identify any gaps
4. Suggest test scenarios

IMPORTANT: DO NOT paste entire files. Only provide specific references.

CODE CHANGES:
${copilotPrompt}

FORMAT YOUR RESPONSE:
• For each acceptance criteria, provide a bullet point with status and specific code references`;
      
      // Step 4: Store PR context for later posting
      const prContext = { prId, authHeader, workspace, repo, chunks };
      context.globalState.update('currentPRContext', prContext);
      
      // Step 5: Auto-paste in Copilot chat
      progress.report({ message: 'Opening Copilot Chat...' });
      
      await vscode.commands.executeCommand('workbench.panel.chat.view.copilot.focus');
      
      setTimeout(async () => {
        await vscode.env.clipboard.writeText(jiraReviewPrompt);
        await vscode.commands.executeCommand('editor.action.clipboardPasteAction');
        
        log(`Auto-pasted Jira story review prompt for ${jiraStoryId}`);
        
        vscode.window.showInformationMessage(
          `Jira story ${jiraStoryId} review prompt pasted in Copilot!`,
          'Post Review to Bitbucket',
          'Show Prompt'
        ).then((selection) => {
          if (selection === 'Post Review to Bitbucket') {
            vscode.commands.executeCommand('bitbucketPRCopilot.postCopilotResponse');
          }
        });
      }, 1000);
    });
    
  } catch (error) {
    vscode.window.showErrorMessage(`Failed to prepare Jira review: ${error.message}`);
    log(`Jira review error: ${error.message}`);
  }
}

// ---------- DEBUG COMMANDS ----------
async function cmdDebugPR(context) {
  try {
    const { prId, authHeader, workspace, repo, sourceBranch, baseBranch } = await ensurePrForCurrentBranch(context);
    
    if (!prId) {
      vscode.window.showWarningMessage('No PR found for current branch');
      return;
    }

    const pr = await getPRById(workspace, repo, prId, authHeader);
    const diffText = await getPRDiff(workspace, repo, prId, authHeader);
    const chunks = parseDiffToChunks(diffText);
    
    const debugInfo = `
🔍 PR Debug Information:

PR ID: ${prId}
Title: ${pr.title}
State: ${pr.state}
Source: ${sourceBranch} -> Target: ${baseBranch}
Project: ${workspace}/${repo}

DIFF ANALYSIS:
• Raw diff length: ${diffText.length} characters
• Number of files/chunks: ${chunks.length}
• Files changed: ${chunks.map(c => c.file).join(', ') || 'None'}
    `.trim();

    log(`Debug PR #${prId}: ${JSON.stringify({
      id: pr.id,
      title: pr.title,
      state: pr.state,
      diffLength: diffText.length,
      chunksFound: chunks.length,
      files: chunks.map(c => c.file)
    })}`);

    vscode.window.showInformationMessage(debugInfo, { modal: true });
    
  } catch (error) {
    vscode.window.showErrorMessage(`Debug PR failed: ${error.message}`);
    log(`Debug PR error: ${error.stack}`);
  }
}

async function cmdSuperDebug(context) {
  try {
    vscode.window.showInformationMessage('🚀 Starting Super Debug...');
    
    const status = await git.status();
    const cfg = vscode.workspace.getConfiguration('bitbucketPRCopilot');
    const config = {
      workspace: cfg.get('workspace'),
      repo: cfg.get('repo'),
      baseBranch: cfg.get('baseBranch'),
      mergeBranch: cfg.get('mergeBranch')
    };

    let authStatus = 'Not tested';
    try {
      const authHeader = await getAuthHeader(context);
      authStatus = 'OK';
    } catch (e) {
      authStatus = `Failed: ${e.message}`;
    }

    let prStatus = 'Not tested';
    try {
      const { prId } = await ensurePrForCurrentBranch(context);
      prStatus = prId ? `Found PR #${prId}` : 'No PR found';
    } catch (e) {
      prStatus = `Failed: ${e.message}`;
    }

    const superDebugInfo = `
🚀 SUPER DEBUG REPORT

GIT:
• Current Branch: ${status.current}
• Tracking: ${status.tracking || 'None'}
• Modified Files: ${status.files?.length || 0}

CONFIGURATION:
• Project: ${config.workspace}
• Repository: ${config.repo}
• Target Branch: ${config.baseBranch}
• Source Branch: ${config.mergeBranch || 'Current'}

AUTHENTICATION: ${authStatus}

PR DETECTION: ${prStatus}
    `.trim();

    log('=== SUPER DEBUG COMPLETE ===');
    log(superDebugInfo);

    vscode.window.showInformationMessage(superDebugInfo, { modal: true })
      .then(() => {
        output.show(true);
      });

  } catch (error) {
    vscode.window.showErrorMessage(`Super Debug failed: ${error.message}`);
    log(`Super Debug error: ${error.stack}`);
  }
}

async function cmdListCommands() {
  const commands = [
    '🔧 Configuration:',
    '• bitbucketPRCopilot.configureSettings - Configure project/repo/branches',
    '• bitbucketPRCopilot.showCurrentConfig - Show current configuration',
    '• bitbucketPRCopilot.cleanAllSettings - Reset all settings to defaults',
    '',
    '📝 PR Commenting:',
    '• bitbucketPRCopilot.quickPost - Quick post for active file',
    '• bitbucketPRCopilot.batchPost - Batch post for all open files',
    '• bitbucketPRCopilot.sendDiffToCopilot - Send PR diff to Copilot Chat',
    '• bitbucketPRCopilot.autoCopilotReview - Auto Copilot review with different types',
    '• bitbucketPRCopilot.reviewAgainstJiraStory - Review PR against Jira acceptance criteria',
    '• bitbucketPRCopilot.postCopilotResponse - Post Copilot response to Bitbucket',
    '',
    '🐛 Debugging:',
    '• bitbucketPRCopilot.debugPR - Debug current PR',
    '• bitbucketPRCopilot.superDebug - Comprehensive debug report',
    '• bitbucketPRCopilot.listCommands - This command list',
    '• bitbucketPRCopilot.testGit - Test Git integration',
    '• bitbucketPRCopilot.showLog - Show extension log',
    '',
    '🔐 Authentication:',
    '• bitbucketPRCopilot.clearApiToken - Clear stored credentials'
  ].join('\n');

  const quickActions = await vscode.window.showQuickPick([
    { label: '$(gear) Configure Settings', description: 'Set up project/repo/branches', command: 'configureSettings' },
    { label: '$(rocket) Quick Post', description: 'Post comment for current file', command: 'quickPost' },
    { label: '$(copilot) Send to Copilot', description: 'Send PR diff to Copilot Chat', command: 'sendDiffToCopilot' },
    { label: '$(tasklist) Review vs Jira', description: 'Review against Jira acceptance criteria', command: 'reviewAgainstJiraStory' },
    { label: '$(copilot) Auto Review', description: 'Auto Copilot review with different types', command: 'autoCopilotReview' },
    { label: '$(bug) Debug PR', description: 'Debug current PR', command: 'debugPR' },
    { label: '$(output) Show Log', description: 'Open extension output', command: 'showLog' }
  ], {
    placeHolder: 'Choose a command to run, or close to see full list...'
  });

  if (quickActions) {
    await vscode.commands.executeCommand(`bitbucketPRCopilot.${quickActions.command}`);
  } else {
    vscode.window.showInformationMessage(commands, { modal: true });
  }

  log('Command list displayed');
}

// ---------- CHAT PARTICIPANT HANDLER ----------
async function bitbucketPrChatHandler(request, chatContext, stream, token) {
  const cmd = request.command;
  const say = (text) => {
    if (stream && typeof stream.markdown === 'function') {
      stream.markdown(text + '\n');
    }
  };

  log(`Chat participant invoked with command: ${cmd || '<none>'}`);

  if (!cmd) {
    say('Use one of: `/reviewPR`, `/postComments`, `/jiraReview`, `/debugPR`, `/configure`.');
    return { metadata: { command: 'help' } };
  }

  try {
    switch (cmd) {
      case 'reviewPR':
        say('🚀 Sending current PR diff to Copilot for review…');
        await vscode.commands.executeCommand('bitbucketPRCopilot.sendDiffToCopilot');
        return { metadata: { command: 'reviewPR' } };

      case 'postComments':
        say('📝 Posting Copilot review response back to Bitbucket PR…');
        await vscode.commands.executeCommand('bitbucketPRCopilot.postCopilotResponse');
        return { metadata: { command: 'postComments' } };

      case 'jiraReview':
        say('📋 Starting Jira story–based review for current PR…');
        await vscode.commands.executeCommand('bitbucketPRCopilot.reviewAgainstJiraStory');
        return { metadata: { command: 'jiraReview' } };

      case 'debugPR':
        say('🐛 Running PR debug…');
        await vscode.commands.executeCommand('bitbucketPRCopilot.debugPR');
        return { metadata: { command: 'debugPR' } };

      case 'configure':
        say('⚙️ Opening Bitbucket PR Copilot configuration…');
        await vscode.commands.executeCommand('bitbucketPRCopilot.configureSettings');
        return { metadata: { command: 'configure' } };

      default:
        say(`Unknown command: \`/${cmd}\`. Try: \`/reviewPR\`, \`/postComments\`, \`/jiraReview\`, \`/debugPR\`, \`/configure\`.`);
        return { metadata: { command: 'unknown' } };
    }
  } catch (err) {
    const msg = err?.message || String(err);
    log(`Error handling chat command "${cmd}": ${msg}`);
    say(`❌ Error while running \`/${cmd}\`: ${msg}`);
    return { metadata: { command: cmd, error: msg } };
  }
}

// ---------- ACTIVATE ----------
function activate(context) {
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

      // Register all commands
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.testGit', () => cmdTestGit()));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postGeneralForCurrentFile', () => cmdPostGeneralForCurrentFile(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postInlineAtSelection', () => cmdPostInlineAtSelection(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postInlineAtLine', () => cmdPostInlineAtLine(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postBatchForOpenFiles', () => cmdPostBatchForOpenFiles(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.quickPost', () => cmdQuickPost(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.batchPost', () => cmdPostBatchForOpenFiles(context)));
      
      // Configuration management commands
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.configureSettings', () => cmdConfigureSettings()));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.cleanAllSettings', () => cmdCleanAllSettings()));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.showCurrentConfig', () => cmdShowCurrentConfig()));

      // Copilot Chat integration commands
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.sendDiffToCopilot', () => cmdSendDiffToCopilotChat(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.autoCopilotReview', () => cmdAutoCopilotReview(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.reviewAgainstJiraStory', () => cmdReviewAgainstJiraStory(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postCopilotResponse', () => cmdPostCopilotResponse(context)));

      // Debug commands
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.debugPR', () => cmdDebugPR(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.superDebug', () => cmdSuperDebug(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.listCommands', () => cmdListCommands()));

      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.clearApiToken', async () => {
        await context.secrets.delete(SECRET_KEY);
        vscode.window.showInformationMessage('Bitbucket credentials cleared.');
        log('Cleared Bitbucket credentials.');
      }));

      // Register chat participant
      if (vscode.chat && typeof vscode.chat.createChatParticipant === 'function') {
        try {
          const chatParticipant = vscode.chat.createChatParticipant(
            'bitbucketPRCopilot.chat',
            bitbucketPrChatHandler
          );
          context.subscriptions.push(chatParticipant);
          log('Chat participant bitbucketPRCopilot.chat registered for / commands.');
        } catch (e) {
          log(`Failed to register chat participant: ${e.message}`);
        }
      } else {
        log('vscode.chat API not available; chat / commands not registered.');
      }

      log('All commands registered successfully.');
    } catch (e) {
      vscode.window.showErrorMessage(`Activation failed: ${e.message}`);
      log(`Activation failed: ${e.stack || e.message}`);
    }
  })();
}

function deactivate() {}

module.exports = { activate, deactivate };