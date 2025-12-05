# Bitbucket PR Copilot (PoC)

VS Code extension that lets you:

- Send a Bitbucket PR diff to **GitHub Copilot Chat** for AI-powered review  
- Paste Copilot’s review back into the PR as **inline** or **general** comments  
- Run **Jira story–based** PR reviews against acceptance criteria  
- Batch post review comments for multiple open files  

---

## 1. Installation (Local Dev)

1. Clone / open this repo in VS Code.  
2. Install dependencies:

```bash
npm install
```

3. Run the extension in a dev host:

- Press `F5` in VS Code (Launch Extension)
- A new VS Code window will open with the extension loaded.

4. (Optional) Package as a VSIX:

```bash
npm run package
```

Then install:

```bash
code --install-extension bitbucket-pr-copilot-x.y.z.vsix
```

---

## 2. Configuration

Settings → search **“Bitbucket PR Copilot”**.

- `bitbucketPRCopilot.workspace` – Bitbucket project key  
- `bitbucketPRCopilot.repo` – repository slug  
- `bitbucketPRCopilot.baseBranch` – PR target branch  
- `bitbucketPRCopilot.mergeBranch` – PR source branch (optional)

Commands:

- Configure Settings  
- Show Current Configuration  
- Reset to Defaults  

On first run, you will be prompted for Bitbucket credentials (stored securely).

---

## 3. Basic PR Workflow

The extension will:

- Detect your current Git branch  
- Locate an existing open PR  
- Or create one if none exists  

Triggered automatically by any PR-related command.

---

## 4. Copilot Review Flow

### 4.1 Send PR Diff to Copilot Chat

Command:

```
Bitbucket PR Copilot: Send PR Diff to Copilot Chat
```

or shortcut:

```
Ctrl+Alt+D  (Cmd+Alt+D on macOS)
```

The extension:

1. Fetches PR diff  
2. Parses and formats it  
3. Auto-pastes a structured prompt into Copilot Chat  

Then Copilot generates a review.

---

### 4.2 Post Copilot Review Back to Bitbucket

After Copilot responds:

1. Copy the response to clipboard  
2. Run:

```
Bitbucket PR Copilot: Post Copilot Response to Bitbucket
```

Choose between:

- **Parse structured comments** → inline or file-level  
- **Post entire response** → general PR comment  

The extension deduplicates comments automatically.

---

## 5. Quick / Batch Commenting (Manual Copilot Use)

### Quick Post (Active File)

Command:

```
Bitbucket PR Copilot: Quick Post (Active File)
```

Shortcut:

```
Ctrl+Alt+P / Cmd+Alt+P
```

Supports:

- Inline comment at selection  
- Inline at specific line  
- General file comment  

---

### Batch Post (All Open Files)

Command:

```
Bitbucket PR Copilot: Batch Post (All Open Files)
```

Shortcut:

```
Ctrl+Alt+B / Cmd+Alt+B
```

Choose: Inline / General / Skip per file → preview → post.

---

## 6. Jira Story–Driven Review

Command:

```
Bitbucket PR Copilot: Review Against Jira Story
```

You provide:

- Jira Story ID  
- Acceptance Criteria  
- Optional Business Requirements  

The extension:

- Fetches PR diff  
- Builds a criteria-focused Copilot prompt  
- Auto-pastes into chat  

Then you can post Copilot’s review back to the PR.

---

## 7. Debugging & Logs

Useful commands:

- **Show Log**
- **Debug PR**
- **Debug PR Diff**
- **Super Debug**
- **Test Git**
- **Clear API Token**

Check output channel:

```
BB PR Copilot
```

---

## 8. Keyboard Shortcuts

| Action | Windows/Linux | macOS |
|--------|----------------|--------|
| Quick Post | Ctrl+Alt+P | Cmd+Alt+P |
| Batch Post | Ctrl+Alt+B | Cmd+Alt+B |
| Send Diff to Copilot | Ctrl+Alt+D | Cmd+Alt+D |
| Post Copilot Response | Ctrl+Alt+R | Cmd+Alt+R |

---

## 9. Requirements

- Git repo must be open in VS Code  
- Bitbucket server must be reachable  
- GitHub Copilot Chat installed  
- Node & VS Code extension runtime compatible  

---

## 10. License

Internal PoC — not intended for public distribution.
