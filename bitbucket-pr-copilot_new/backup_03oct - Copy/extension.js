// extension.js
const vscode = require('vscode');
const simpleGit = require('simple-git');
const crypto = require('crypto');

// ---------- DEFAULTS (fallback only) ----------
const DEFAULTS = {
  workspace: null, // Will be auto-detected
  repo: null,      // Will be auto-detected  
  baseBranch: 'main',
};
const SECRET_KEY = 'bitbucket-basic-auth';

// ---------- RATE LIMITER ----------
class RateLimiter {
  constructor(requestsPerMinute = 10) {
    this.requests = [];
    this.limit = requestsPerMinute;
  }
  
  async acquire() {
    const now = Date.now();
    const windowStart = now - 60000; // 1 minute
    
    // Remove old requests
    this.requests = this.requests.filter(time => time > windowStart);
    
    if (this.requests.length >= this.limit) {
      const waitTime = Math.max(1000, this.requests[0] - windowStart);
      log(`Rate limit reached, waiting ${waitTime}ms...`);
      await new Promise(resolve => setTimeout(resolve, waitTime));
      return this.acquire();
    }
    
    this.requests.push(now);
  }
}

const rateLimiter = new RateLimiter(10);

// ---------- COMMENT TEMPLATES ----------
const COMMENT_TEMPLATES = {
  default: {
    inline: `🤖 **Copilot/Chat note @ line ~{line} in \`{file}\`**\n\n{feedback}`,
    general: `🤖 **Copilot/Chat Review for \`{file}\`**\n\n{feedback}`
  },
  concise: {
    inline: `💡 **Suggestion @ line {line}**\n\n{feedback}`,
    general: `📝 **Review notes for {file}**\n\n{feedback}`
  },
  professional: {
    inline: `**AI Review Note (line {line})**\n\n{feedback}`,
    general: `**AI Code Review: {file}**\n\n{feedback}`
  }
};

// ---------- LOGGING ----------
let output;
function log(msg) {
  try {
    const time = new Date().toISOString();
    output?.appendLine(`[${time}] ${msg}`);
  } catch {}
}

// ---------- PROGRESS UTILS ----------
async function withProgress(title, task) {
  return vscode.window.withProgress({
    location: vscode.ProgressLocation.Notification,
    title: title,
    cancellable: false
  }, async (progress) => {
    progress.report({ increment: 0 });
    const result = await task(progress);
    progress.report({ increment: 100 });
    return result;
  });
}

// ---------- SETTINGS (Auto-detected from Git) ----------
async function getAutoConfig() {
  try {
    // Get git remote URL
    const remoteUrl = await git.remote(['get-url', 'origin']);
    log(`Detected remote URL: ${remoteUrl}`);
    
    // Parse Bitbucket URL to extract workspace and repo
    const { workspace, repo } = parseBitbucketUrl(remoteUrl);
    
    if (!workspace || !repo) {
      throw new Error('Could not detect workspace/repo from Git remote');
    }
    
    return {
      workspace,
      repo,
      baseBranch: await getDefaultBranch()
    };
  } catch (error) {
    log(`Auto-config failed: ${error.message}. Using defaults.`);
    return DEFAULTS;
  }
}

function parseBitbucketUrl(remoteUrl) {
  // Support multiple URL formats:
  // HTTPS: https://bitbucket.org/myworkspace_poc/myrepo_poc.git
  // HTTPS with auth: https://kemails2006@gmail.com@bitbucket.org/myworkspace_poc/myrepo_poc.git
  // HTTPS with username: https://gangaramani@bitbucket.org/myworkspace_poc/myrepo_poc.git
  // SSH: git@bitbucket.org:myworkspace_poc/myrepo_poc.git
  
  log(`Parsing remote URL: ${remoteUrl}`);
  
  const patterns = [
    // SSH format: git@bitbucket.org:workspace/repo.git
    /git@bitbucket\.org:([^\/]+)\/([^\/\.]+)(?:\.git)?/,
    
    // HTTPS format with username in URL: https://username@bitbucket.org/workspace/repo.git
    /https:\/\/([^@]+)@bitbucket\.org\/([^\/]+)\/([^\/\.]+)(?:\.git)?/,
    
    // HTTPS format without username: https://bitbucket.org/workspace/repo.git
    /https:\/\/(?:[^@]+@)?bitbucket\.org\/([^\/]+)\/([^\/\.]+)(?:\.git)?/
  ];
  
  for (const pattern of patterns) {
    const match = remoteUrl.trim().match(pattern);
    if (match) {
      log(`Pattern matched: ${pattern}`);
      log(`Match groups: ${JSON.stringify(match)}`);
      
      // For SSH/HTTPS without username: match[1] = workspace, match[2] = repo
      if (pattern.toString().includes('git@bitbucket') || 
          pattern.toString().includes('bitbucket.org/([^/]+)/([^/\.])')) {
        return { workspace: match[1], repo: match[2] };
      }
      // For HTTPS with username: match[2] = workspace, match[3] = repo
      else if (pattern.toString().includes('([^@]+)@bitbucket')) {
        return { workspace: match[2], repo: match[3] };
      }
    }
  }
  
  log(`No pattern matched for URL: ${remoteUrl}`);
  return { workspace: null, repo: null };
}

async function getDefaultBranch() {
  try {
    // Try to get default branch from git
    const symbolicRef = await git.raw(['symbolic-ref', 'refs/remotes/origin/HEAD']);
    const match = symbolicRef.match(/refs\/remotes\/origin\/(.+)/);
    return match ? match[1] : 'main';
  } catch {
    return 'main'; // Fallback
  }
}

// Update getCfg to use auto-detection
async function getCfg() {
  try {
    const cfg = vscode.workspace.getConfiguration('bitbucketPRCopilot');
    const autoConfig = await getAutoConfig();
    
    const config = {
      workspace: cfg.get('workspace') || autoConfig.workspace || DEFAULTS.workspace,
      repo: cfg.get('repo') || autoConfig.repo || DEFAULTS.repo,
      baseBranch: cfg.get('baseBranch') || autoConfig.baseBranch || DEFAULTS.baseBranch,
      commentStyle: cfg.get('commentStyle') || 'default',
      enableRateLimiting: cfg.get('enableRateLimiting') !== false, // default true
      maxRetries: cfg.get('maxRetries') || 3
    };
    
    // Validate required fields
    if (!config.workspace || !config.repo) {
      log(`Configuration validation failed: workspace=${config.workspace}, repo=${config.repo}`);
      throw new Error('Workspace and repository configuration is required');
    }
    
    return config;
  } catch (error) {
    log(`Error in getCfg: ${error.message}`);
    throw error;
  }
}

// ---------- CONFIGURATION VALIDATION ----------
async function validateConfiguration(context) {
  const config = await getCfg();
  const errors = [];
  
  if (!config.workspace) errors.push('Workspace not configured');
  if (!config.repo) errors.push('Repository not configured');
  
  // Test repository access if we have credentials
  try {
    const authHeader = await getAuthHeader(context);
    const repoUrl = `https://api.bitbucket.org/2.0/repositories/${config.workspace}/${config.repo}`;
    await bbFetch(repoUrl, { authHeader });
  } catch (error) {
    if (!error.message.includes('getAuthHeader')) {
      errors.push(`Cannot access repository: ${error.message}`);
    }
  }
  
  return errors;
}

async function setupConfigurationWizard(context) {
  const steps = [
    {
      title: 'Bitbucket Workspace',
      prompt: 'Enter your Bitbucket workspace ID',
      field: 'workspace',
      validate: (value) => value && value.length > 0 ? null : 'Workspace is required'
    },
    {
      title: 'Repository', 
      prompt: 'Enter your repository name',
      field: 'repo',
      validate: (value) => value && value.length > 0 ? null : 'Repository name is required'
    },
    {
      title: 'Base Branch',
      prompt: 'Enter the base branch for PRs',
      field: 'baseBranch',
      default: 'main',
      validate: (value) => value && value.length > 0 ? null : 'Base branch is required'
    }
  ];
  
  const config = vscode.workspace.getConfiguration('bitbucketPRCopilot');
  
  for (const step of steps) {
    const currentValue = config.get(step.field);
    const value = await vscode.window.showInputBox({
      title: step.title,
      prompt: step.prompt,
      value: currentValue || step.default,
      ignoreFocusOut: true,
      validateInput: step.validate
    });
    
    if (value === undefined) {
      // User cancelled
      return false;
    }
    
    if (value) {
      await config.update(step.field, value, vscode.ConfigurationTarget.Global);
    }
  }
  
  // Test configuration
  vscode.window.showInformationMessage('Configuration saved. Testing connection...');
  await cmdDebugAuth(context);
  await cmdDebugConfig();
  
  return true;
}

// ---------- WORKSPACE ----------
const workspaceFolders = vscode.workspace.workspaceFolders;
const repoPath = workspaceFolders?.[0]?.uri.fsPath;

/** @type import('simple-git').SimpleGit */
let git = null;

const postedHashes = new Set();
const existingHashesByPR = new Map();

// Cache with TTL (1 hour)
const cacheTTL = 60 * 60 * 1000;
const cacheTimestamps = new Map();

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

async function cmdDebugConfig() {
  try {
    const config = await getCfg();
    const remoteUrl = await git.remote(['get-url', 'origin']).catch(() => 'Not available');
    const currentBranch = (await git.status()).current;
    
    const message = `Current Configuration:
Remote URL: ${remoteUrl}
Workspace: ${config.workspace}
Repository: ${config.repo} 
Base Branch: ${config.baseBranch}
Current Branch: ${currentBranch}
Comment Style: ${config.commentStyle}
Rate Limiting: ${config.enableRateLimiting ? 'enabled' : 'disabled'}
Max Retries: ${config.maxRetries}`;
    
    log(message);
    vscode.window.showInformationMessage('Check "BB PR Copilot" output for configuration details');
  } catch (error) {
    log(`Debug config failed: ${error.message}`);
    vscode.window.showErrorMessage('Debug config failed: ' + error.message);
  }
}

async function cmdDebugAPI(context) {
  try {
    const authHeader = await getAuthHeader(context);
    const config = await getCfg();
    
    log(`=== API DEBUG ===`);
    log(`Workspace: ${config.workspace}`);
    log(`Repo: ${config.repo}`);
    log(`Base Branch: ${config.baseBranch}`);
    
    // Test PR base URL
    const prBaseUrl = await prBase();
    log(`PR Base URL: ${prBaseUrl}`);
    
    // Test repository access
    const repoUrl = `https://api.bitbucket.org/2.0/repositories/${config.workspace}/${config.repo}`;
    log(`Testing repo access: ${repoUrl}`);
    
    const repoResponse = await fetch(repoUrl, {
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      }
    });
    
    if (repoResponse.ok) {
      const repoData = await repoResponse.json();
      log(`✅ Repository access successful: ${repoData.name}`);
      vscode.window.showInformationMessage(`✅ Repository access: ${repoData.name}`);
    } else {
      const errorText = await repoResponse.text();
      log(`❌ Repository access failed: ${repoResponse.status} - ${errorText}`);
      vscode.window.showErrorMessage(`Repository access failed: ${repoResponse.status}`);
    }
    
  } catch (error) {
    log(`❌ API debug failed: ${error.message}`);
    vscode.window.showErrorMessage(`API debug failed: ${error.message}`);
  }
}

async function cmdDebugFull(context) {
  try {
    const authHeader = await getAuthHeader(context);
    const config = await getCfg();
    const status = await git.status();
    
    log(`=== FULL DEBUG ===`);
    log(`Workspace: ${config.workspace}`);
    log(`Repository: ${config.repo}`);
    log(`Base Branch: ${config.baseBranch}`);
    log(`Current Branch: ${status.current}`);
    
    // Test repository access
    const repoUrl = `https://api.bitbucket.org/2.0/repositories/${config.workspace}/${config.repo}`;
    log(`Testing repository access: ${repoUrl}`);
    
    const repoResponse = await fetch(repoUrl, {
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      }
    });
    
    if (repoResponse.ok) {
      const repoData = await repoResponse.json();
      log(`✅ Repository access successful: ${repoData.name}`);
    } else {
      const errorText = await repoResponse.text();
      log(`❌ Repository access failed: ${repoResponse.status} - ${errorText}`);
    }
    
    // Test PR access
    const prsUrl = `${await prBase()}?pagelen=5`;
    const prsResponse = await fetch(prsUrl, {
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      }
    });
    
    if (prsResponse.ok) {
      const prsData = await prsResponse.json();
      log(`✅ PR access successful: ${prsData.values?.length || 0} PRs found`);
    } else {
      const errorText = await prsResponse.text();
      log(`❌ PR access failed: ${prsResponse.status} - ${errorText}`);
    }
    
  } catch (error) {
    log(`❌ Full debug failed: ${error.message}`);
  }
}

async function cmdCompareRequests(context) {
  try {
    const authHeader = await getAuthHeader(context);
    const config = await getCfg();
    const status = await git.status();
    const branch = status.current;
    const prBaseUrl = await prBase();
    
    log(`=== COMPARING REQUESTS ===`);
    log(`Workspace: ${config.workspace}`);
    log(`Repo: ${config.repo}`);
    log(`Current Branch: ${branch}`);
    log(`Base Branch: ${config.baseBranch}`);
    
    // Test 1: The working curl URL
    const curlUrl = `https://api.bitbucket.org/2.0/repositories/myworkspace_poc/myrepo_poc/pullrequests?q=source.branch.name=%22feature/test1%22%20AND%20state=%22OPEN%22%20AND%20destination.branch.name=%22main%22&fields=values.id,values.title`;
    log(`🔍 Testing CURL URL: ${curlUrl}`);
    
    const curlResponse = await fetch(curlUrl, {
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      }
    });
    
    if (curlResponse.ok) {
      const curlData = await curlResponse.json();
      log(`✅ CURL URL works: ${curlData.values?.length || 0} PRs found`);
    } else {
      log(`❌ CURL URL failed: ${curlResponse.status}`);
    }
    
    // Test 2: The extension's generated URL
    const extensionUrl = `${prBaseUrl}?q=source.branch.name="${branch}" AND state="OPEN" AND destination.branch.name="${config.baseBranch}"&fields=values.id,values.title`;
    log(`🔍 Testing Extension URL: ${extensionUrl}`);
    
    const extensionResponse = await fetch(extensionUrl, {
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      }
    });
    
    if (extensionResponse.ok) {
      const extensionData = await extensionResponse.json();
      log(`✅ Extension URL works: ${extensionData.values?.length || 0} PRs found`);
    } else {
      const errorText = await extensionResponse.text();
      log(`❌ Extension URL failed: ${extensionResponse.status} - ${errorText}`);
    }
    
    // Compare the URLs
    log(`🔍 URL Comparison:`);
    log(`   CURL:    ${curlUrl}`);
    log(`   Extension: ${extensionUrl}`);
    log(`   Match: ${curlUrl === extensionUrl ? '✅ IDENTICAL' : '❌ DIFFERENT'}`);
    
  } catch (error) {
    log(`❌ Compare requests failed: ${error.message}`);
  }
}

async function cmdClearCommentCache() {
  postedHashes.clear();
  existingHashesByPR.clear();
  cacheTimestamps.clear();
  vscode.window.showInformationMessage('✅ Comment cache cleared. Deduplication will start fresh.');
  log('Comment cache cleared');
}

async function cmdValidateConfig(context) {
  const errors = await validateConfiguration(context);
  if (errors.length === 0) {
    vscode.window.showInformationMessage('✅ Configuration is valid!');
    log('Configuration validation: ✅ All checks passed');
  } else {
    const errorMsg = `Configuration issues found:\n${errors.join('\n• ')}`;
    vscode.window.showErrorMessage(errorMsg, 'Run Setup Wizard').then(selection => {
      if (selection === 'Run Setup Wizard') {
        setupConfigurationWizard(context);
      }
    });
    log(`Configuration validation: ❌ Issues found:\n${errors.join('\n')}`);
  }
}

async function cmdDebugRemoteUrl() {
  try {
    const remoteUrl = await git.remote(['get-url', 'origin']);
    log(`Raw remote URL: ${remoteUrl}`);
    
    const parsed = parseBitbucketUrl(remoteUrl);
    log(`Parsed result: workspace=${parsed.workspace}, repo=${parsed.repo}`);
    
    vscode.window.showInformationMessage(
      `Remote URL Analysis:\nURL: ${remoteUrl}\nWorkspace: ${parsed.workspace}\nRepo: ${parsed.repo}`
    );
  } catch (error) {
    log(`Debug remote URL failed: ${error.message}`);
    vscode.window.showErrorMessage(`Debug failed: ${error.message}`);
  }
}

async function cmdDebugPRSearch(context) {
  try {
    const authHeader = await getAuthHeader(context);
    const config = await getCfg();
    const status = await git.status();
    const branch = status.current;
    const prBaseUrl = await prBase();
    
    log(`=== DEBUG PR SEARCH ===`);
    log(`Workspace: ${config.workspace}`);
    log(`Repo: ${config.repo}`);
    log(`Current Branch: ${branch}`);
    log(`Base Branch: ${config.baseBranch}`);
    
    // Test the exact query we're using
    const q = `source.branch.name="${branch}" AND state="OPEN" AND destination.branch.name="${config.baseBranch}"`;
    const url = `${prBaseUrl}?q=${encodeURIComponent(q)}&fields=values.id,values.title,values.source,values.destination`;
    
    log(`PR Search URL: ${url}`);
    
    const response = await fetch(url, {
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      log(`✅ PR search successful: ${data.values?.length || 0} PRs found`);
      
      if (data.values && data.values.length > 0) {
        data.values.forEach(pr => {
          log(`Found PR: #${pr.id} - "${pr.title}"`);
          log(`  Source: ${pr.source.branch.name} -> Destination: ${pr.destination.branch.name}`);
        });
      } else {
        log(`No PRs found for query: ${q}`);
        
        // Let's also search for any PRs from this branch to see what exists
        const allPrsUrl = `${prBaseUrl}?q=source.branch.name="${branch}"&fields=values.id,values.title,values.state,values.source,values.destination&pagelen=10`;
        log(`Searching for any PRs from branch: ${allPrsUrl}`);
        
        const allPrsResponse = await fetch(allPrsUrl, {
          headers: {
            'Authorization': authHeader,
            'Content-Type': 'application/json'
          }
        });
        
        if (allPrsResponse.ok) {
          const allPrsData = await allPrsResponse.json();
          log(`Found ${allPrsData.values?.length || 0} total PRs from branch ${branch}:`);
          if (allPrsData.values) {
            allPrsData.values.forEach(pr => {
              log(`  PR #${pr.id}: "${pr.title}" [${pr.state}] - ${pr.source.branch.name} -> ${pr.destination.branch.name}`);
            });
          }
        }
      }
    } else {
      const errorText = await response.text();
      log(`❌ PR search failed: ${response.status} - ${errorText}`);
    }
    
  } catch (error) {
    log(`❌ PR search debug failed: ${error.message}`);
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
      placeHolder: 'your.email@company.com',
      validateInput: (value) => value && value.includes('@') ? null : 'Please enter a valid email'
    });
    
    if (!email) throw new Error('Email is required');
    
    const token = await vscode.window.showInputBox({ 
      prompt: 'Enter your Bitbucket API Token', 
      password: true, 
      ignoreFocusOut: true,
      placeHolder: 'Paste your API token here',
      validateInput: (value) => value && value.length > 0 ? null : 'API token is required'
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

Token Scopes Required:
  • Account: Read
  • Workspace membership: Read  
  • Projects: Read
  • Repositories: Read & Write
  • Pull requests: Read & Write
`;
  log(help);
  vscode.window.showInformationMessage('Environment setup instructions written to "BB PR Copilot" output.');
}

// ---------- HTTP HELPERS ----------
async function bbFetch(url, { method='GET', headers={}, body, authHeader }, retries = 2) {
  const config = await getCfg();
  const maxRetries = retries === 2 ? config.maxRetries : retries;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      if (config.enableRateLimiting) {
        await rateLimiter.acquire();
      }
      
      const res = await fetch(url, {
        method,
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': authHeader, ...headers },
        body
      });
      
      if (res.status === 401) throw new Error('Unauthorized (401). Check Bitbucket token scopes.');
      if (res.status === 429 && attempt < maxRetries) {
        const wait = parseInt(res.headers.get('Retry-After') || '2', 10) * 1000;
        log(`Rate limited by Bitbucket; retrying in ${wait} ms (attempt ${attempt}/${maxRetries})`);
        await new Promise(r => setTimeout(r, wait));
        continue;
      }
      
      // Handle network errors with retry
      if (!res.ok && attempt < maxRetries) {
        const errorText = await res.text();
        if (res.status >= 500 || res.status === 429) {
          log(`Server error ${res.status}, retrying... (attempt ${attempt}/${maxRetries})`);
          await new Promise(r => setTimeout(r, 1000 * attempt));
          continue;
        }
        throw new Error(`${method} ${url} failed: ${res.status} ${errorText}`);
      }
      
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`${method} ${url} failed: ${res.status} ${errorText}`);
      }
      
      const ct = res.headers.get('content-type') || '';
      return ct.includes('application/json') ? res.json() : res.text();
      
    } catch (error) {
      if (attempt === maxRetries) throw error;
      
      // Retry on network errors
      if (error.message.includes('ETIMEDOUT') || error.message.includes('ENOTFOUND') || error.message.includes('ECONNRESET')) {
        log(`Network error (${error.message}), retrying... (attempt ${attempt}/${maxRetries})`);
        await new Promise(r => setTimeout(r, 1000 * attempt));
        continue;
      }
      throw error;
    }
  }
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
async function prBase() {
  const config = await getCfg();
  return `https://api.bitbucket.org/2.0/repositories/${config.workspace}/${config.repo}/pullrequests`;
}

async function getCommentTemplate(type, filePath, line = null, feedback) {
  const config = await getCfg();
  const templateType = config.commentStyle || 'default';
  const template = COMMENT_TEMPLATES[templateType]?.[type] || COMMENT_TEMPLATES.default[type];
  
  return template
    .replace(/{file}/g, filePath)
    .replace(/{line}/g, line)
    .replace(/{feedback}/g, feedback);
}

async function findPRForBranch(branch, authHeader) {
  try {
    const { baseBranch } = await getCfg();
    const prBaseUrl = await prBase();
    
    log(`🔍 Searching for PR: ${branch} -> ${baseBranch}`);
    
    // Use the exact same query that works in curl
    const q = `source.branch.name="${branch}" AND state="OPEN" AND destination.branch.name="${baseBranch}"`;
    const url = `${prBaseUrl}?q=${encodeURIComponent(q)}&fields=values.id,values.title`;
    
    log(`🔍 PR Search URL: ${url}`);
    
    const response = await fetch(url, {
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      log(`❌ PR search failed: ${response.status} - ${errorText}`);
      throw new Error(`PR search failed: ${response.status}`);
    }
    
    const data = await response.json();
    log(`✅ PR search successful: ${data.values?.length || 0} PRs found`);
    
    return data.values?.[0]?.id || null;
  } catch (error) {
    log(`❌ Error in findPRForBranch: ${error.message}`);
    throw error;
  }
}

async function createPullRequest(sourceBranch, authHeader, title, description) {
  const { baseBranch } = await getCfg();
  const url = await prBase();
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
  const url = `${await prBase()}/${prId}/comments`;
  const payload = { content: { raw: content } };
  return bbFetch(url, { method: 'POST', body: JSON.stringify(payload), authHeader });
}

async function postInlinePRComment(prId, pathRel, toLine, content, authHeader) {
  log(`Posting inline comment to ${pathRel} at line ${toLine} in PR #${prId}`);
  const url = `${await prBase()}/${prId}/comments`;
  const payload = { content: { raw: content }, inline: { path: pathRel, to: toLine } };
  return bbFetch(url, { method: 'POST', body: JSON.stringify(payload), authHeader });
}

async function listPRComments(prId, authHeader) {
  const url = `${await prBase()}/${prId}/comments?pagelen=100`;
  return bbPaginate(url, { authHeader });
}

// ---------- PR SESSION ----------
async function ensurePrForCurrentBranch(context) {
  const authHeader = await getAuthHeader(context);
  const status = await git.status();
  const branch = status.current;
  log(`Current branch=${branch}`);

  const { baseBranch } = await getCfg();
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
  const now = Date.now();
  const cached = existingHashesByPR.get(prId);
  const cacheTime = cacheTimestamps.get(prId);
  
  // Use cache if it's less than 1 hour old
  if (cached && cacheTime && (now - cacheTime) < cacheTTL) {
    return cached;
  }
  
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
  cacheTimestamps.set(prId, now);
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
async function makeGeneralComment(filePath, feedback) {
  return getCommentTemplate('general', filePath, null, feedback);
}
async function makeInlineComment(filePath, toLine, feedback) {
  return getCommentTemplate('inline', filePath, toLine, feedback);
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

// Enhanced clipboard parsing with multiple format support
function parseClipboardSuggestionsEnhanced(text) {
  const parsers = [
    // GitHub Copilot format: file:line:column: message
    (text) => {
      const matches = text.match(/(.+?):(\d+):(\d+):\s*(.+)/);
      if (matches) {
        return [{
          file: matches[1],
          line: parseInt(matches[2]),
          feedback: matches[4]
        }];
      }
    },
    
    // VS Code Chat format  
    (text) => {
      const lines = text.split('\n');
      if (lines.length >= 3) {
        const fileMatch = lines[0].match(/File:\s*(.+)/i);
        const lineMatch = lines[1].match(/Line:\s*(\d+)/i);
        
        if (fileMatch) {
          return [{
            file: fileMatch[1],
            line: lineMatch ? parseInt(lineMatch[1]) : null,
            feedback: lines.slice(2).join('\n').trim()
          }];
        }
      }
    }
  ];
  
  for (const parser of parsers) {
    const result = parser(text);
    if (result) return result;
  }
  
  // Fall back to original parser
  return parseClipboardSuggestions(text);
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

  const body = await makeGeneralComment(filePath, feedback);
  const confirm = await vscode.window.showQuickPick(
    [{ label: `Post general review to PR #${prId}`, detail: summarize(body), picked: true }],
    { canPickMany: false, title: 'Preview general comment' }
  );
  if (!confirm) return;

  await withProgress('Posting general comment...', async () => {
    await postGeneralIfNew(prId, body, authHeader);
  });
  
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

  const body = await makeInlineComment(filePath, line, feedback);
  const rel = toPosix(filePath);
  const confirm = await vscode.window.showQuickPick(
    [{ label: `Post inline to ${rel}:${line}`, detail: summarize(body), picked: true }],
    { canPickMany: false, title: 'Preview inline comment' }
  );
  if (!confirm) return;

  await withProgress('Posting inline comment...', async () => {
    await postInlineIfNew(prId, rel, line, body, authHeader);
  });
  
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

  const body = await makeInlineComment(filePath, line, feedback);
  const rel = toPosix(filePath);
  const confirm = await vscode.window.showQuickPick(
    [{ label: `Post inline to ${rel}:${line}`, detail: summarize(body), picked: true }],
    { canPickMany: false, title: 'Preview inline comment' }
  );
  if (!confirm) return;

  await withProgress('Posting inline comment...', async () => {
    await postInlineIfNew(prId, rel, line, body, authHeader);
  });
  
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
    { canPickMany: true, title: 'Batch Post: select open files to include', placeHolder: 'Uncheck files you don\'t want in this batch' }
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
      const body = await makeInlineComment(f, line, feedback.trim());
      plans.push({ kind: 'inline', relPosix: rel, toLine: line, body });
    } else {
      const body = await makeGeneralComment(f, feedback.trim());
      plans.push({ kind: 'general', relPosix: rel, body });
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

  await withProgress(`Posting ${picked.length} comments...`, async (progress) => {
    let posted = 0;
    for (const i of picked) {
      const p = i.plan;
      if (p.kind === 'inline') {
        await postInlineIfNew(prId, p.relPosix, p.toLine, p.body, authHeader);
      } else {
        await postGeneralIfNew(prId, p.body, authHeader);
      }
      posted++;
      progress.report({ increment: (posted / picked.length) * 100, message: `Posted ${posted}/${picked.length}` });
    }
    vscode.window.showInformationMessage(`✅ Posted ${posted} comment(s) to PR #${prId}`);
  });
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
    { canPickMany: true, title: 'Clipboard → Batch: select open files to include', placeHolder: 'Uncheck files you don\'t want in this batch' }
  );
  if (!pickTargets || pickTargets.length === 0) return;
  const openFiles = pickTargets.map(i => i.label);

  const clip = await readClipboard();
  if (!clip) return vscode.window.showWarningMessage('Clipboard is empty.');
  const parsed = parseClipboardSuggestionsEnhanced(clip);

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
      const body = await makeInlineComment(rel, p.line, p.feedback);
      plans.push({ kind: 'inline', relPosix: rel, toLine: p.line, body });
    } else {
      const body = await makeGeneralComment(rel, p.feedback);
      plans.push({ kind: 'general', relPosix: rel, body });
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
      const body = await makeGeneralComment(f, clip);
      plans.push({ kind: 'general', relPosix: f, body });
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

  await withProgress(`Posting ${picked.length} clipboard comments...`, async (progress) => {
    let posted = 0;
    for (const i of picked) {
      const p = i.plan;
      if (p.kind === 'inline') {
        await postInlineIfNew(prId, p.relPosix, p.toLine, p.body, authHeader);
      } else {
        await postGeneralIfNew(prId, p.body, authHeader);
      }
      posted++;
      progress.report({ increment: (posted / picked.length) * 100, message: `Posted ${posted}/${picked.length}` });
    }
    vscode.window.showInformationMessage(`✅ Posted ${posted} clipboard comment(s) to PR #${prId}`);
  });
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

  // Register ALL debug commands
  context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.debugEnv', () => cmdDebugEnv()));
  context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.debugAuth', () => cmdDebugAuth(context)));
  context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.debugConfig', () => cmdDebugConfig()));
  context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.debugAPI', () => cmdDebugAPI(context)));
  context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.debugFull', () => cmdDebugFull(context)));
  context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.compareRequests', () => cmdCompareRequests(context)));
  context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.clearCommentCache', () => cmdClearCommentCache()));
  context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.validateConfig', () => cmdValidateConfig(context)));
  context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.setupWizard', () => setupConfigurationWizard(context)));
  context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.debugRemoteUrl', () => cmdDebugRemoteUrl()));
  context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.debugPRSearch', () => cmdDebugPRSearch(context)));

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

      // Register ALL core commands
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.testGit', () => cmdTestGit()));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postGeneralForCurrentFile', () => cmdPostGeneralForCurrentFile(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postInlineAtSelection', () => cmdPostInlineAtSelection(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postInlineAtLine', () => cmdPostInlineAtLine(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.postBatchForOpenFiles', () => cmdPostBatchForOpenFiles(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.batchPostFromClipboard', () => cmdBatchPostFromClipboard(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.quickPost', () => cmdQuickPost(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.clearApiToken', async () => clearSecretAuth(context)));
      context.subscriptions.push(vscode.commands.registerCommand('bitbucketPRCopilot.showEnvHelp', () => showEnvHelp()));

      log('All commands registered successfully.');
      
      // Validate configuration on startup
      setTimeout(async () => {
        const errors = await validateConfiguration(context);
        if (errors.length > 0) {
          log(`Configuration issues detected on startup: ${errors.join(', ')}`);
        }
      }, 2000);
      
    } catch (e) {
      vscode.window.showErrorMessage(`Activation failed: ${e.message}`);
      log(`Activation failed: ${e.stack || e.message}`);
    }
  })();
}

function deactivate() {}

module.exports = { activate, deactivate };