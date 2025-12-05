Bitbucket PR Copilot (PoC)

VS Code extension to post GitHub Copilot or AI review suggestions as comments on Bitbucket Pull Requests.

✨ Features

Detect changed files via Git (using simple-git)

Check or create PR on Bitbucket automatically

Post comments as:

🔹 General PR comment (whole review)

🔹 Inline per changed hunk

🔹 Hybrid (general + top 3 hunks inline)

🔹 Selection (highlighted text in editor)

File filtering (skips .vscode/, binaries, lockfiles, etc.)

Secure Bitbucket credentials storage in VS Code SecretStorage

🚀 Getting Started
1. Install dependencies
npm install

2. Debug in VS Code

Open this repo in VS Code

Press F5 → launches “Extension Development Host”

Open your project folder in that window

3. First run

Run any Bitbucket PR Copilot command from Command Palette (Ctrl+Shift+P)

You will be prompted for:

Bitbucket email

Bitbucket App Password / API Token
→ stored securely for reuse

🛠️ Commands
Command	Description
Bitbucket PR Copilot: Test Git	Show current Git branch
Bitbucket PR Copilot: Post Suggestions	Post placeholder suggestions for all changed files
Bitbucket PR Copilot: Post Selection	Post currently highlighted text as inline PR comment
Bitbucket PR Copilot: Post Copilot Review	Paste Copilot’s review → choose strategy to post
Bitbucket PR Copilot: Clear Bitbucket API Token	Clear stored credentials
💡 Usage Flow

Work on a feature branch in VS Code

Run Post Copilot Review

Paste Copilot’s review output (or use placeholder)

Choose strategy:

General → PR-level comment

Hunks → Inline comments for each diff hunk

Hybrid → Both overview + inline

Selection → Inline comment on highlighted code

Reviewers see Copilot feedback alongside code in Bitbucket PR