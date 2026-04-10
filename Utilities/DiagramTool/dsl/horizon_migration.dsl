# ===========================================================
# HORIZON — MIGRATION STRATEGY
# Bitbucket+Jenkins+XLRelease → GitHub+GHActions+Harness
# 20k Developers  |  100k Repos  |  3 Phases
# ===========================================================
# Color coding:
#   red    = DECOMMISSION (being replaced)
#   green  = NEW (being introduced)
#   teal   = RETAINED (stays, may be re-pointed)
#   orange = TRANSITION (runs in parallel during migration)
#   blue   = ACTOR / team
#   gray   = UNCHANGED infra
# ===========================================================

# -- Migration Actors --------------------------------------
Actor: Platform Engineering Team
Actor: App Dev Teams (20k)
Actor: Migration Tiger Team
Actor: Change Approval Board

# -- PHASE 1 — SCM Migration (Repos) ----------------------
System: Bitbucket Server [color: red]
System: GitHub Enterprise Cloud [color: green]
System: Repo Migration Tool [color: orange]
System: Branch Policy Migration [color: orange]
System: PR Webhook Re-routing [color: orange]

# -- PHASE 2 — CI Migration (Pipelines) -------------------
System: Jenkins Shared Library (15 types) [color: red]
System: GitHub Actions [color: green]
System: Reusable Workflows Library [color: green]
System: Parallel Run — Jenkins [color: orange]
System: Parallel Run — GH Actions [color: orange]
System: Pipeline Parity Validator [color: orange]

# -- PHASE 3 — CD Migration (Release) ---------------------
System: XLRelease [color: red]
System: XL Deploy [color: red]
System: Harness CD [color: green]
System: Harness Approval Gates [color: green]
System: Release Bridge (dual-run) [color: orange]

# -- RETAINED TOOLS (no change) ---------------------------
System: JFrog Artifactory [color: teal]
System: SonarQube [color: teal]
System: Ansible Tower [color: teal]
System: Terraform [color: teal]
System: Datical DB [color: teal]
System: Octane ALM [color: teal]
System: Litmus Chaos [color: teal]
System: OpenShift PROD Cluster [color: teal]

# -- Governance --------------------------------------------
System: Migration Tracker Dashboard [color: purple]
System: Rollback Runbook [color: gray]

# ===========================================================
# PHASE 1  —  SCM MIGRATION
# ===========================================================

Migration Tiger Team -> Repo Migration Tool [label: Phase 1: migrate 100k repos]
Repo Migration Tool -> Bitbucket Server [label: export repos + history]
Repo Migration Tool -> GitHub Enterprise Cloud [label: import + LFS + tags]
Branch Policy Migration -> Bitbucket Server [label: export branch rules]
Branch Policy Migration -> GitHub Enterprise Cloud [label: import rulesets]
PR Webhook Re-routing -> Bitbucket Server [label: disable old webhooks]
PR Webhook Re-routing -> GitHub Enterprise Cloud [label: register new webhooks]
App Dev Teams (20k) --> GitHub Enterprise Cloud [label: switch remote origin]
Change Approval Board -> Repo Migration Tool [label: CAB sign-off per wave]

# ===========================================================
# PHASE 2  —  CI MIGRATION
# ===========================================================

Platform Engineering Team -> Reusable Workflows Library [label: Phase 2: build 15 workflow types]
Reusable Workflows Library -> GitHub Actions [label: Java, Python, MsBuild, OCP, DB...]
GitHub Actions -> JFrog Artifactory [label: publish artefacts (same target)]
GitHub Actions -> SonarQube [label: quality gate (same target)]

Parallel Run — Jenkins -> Jenkins Shared Library (15 types) [label: existing pipelines run]
Parallel Run — GH Actions -> Reusable Workflows Library [label: new pipelines shadow-run]
Pipeline Parity Validator -> Parallel Run — Jenkins [label: compare outputs]
Pipeline Parity Validator -> Parallel Run — GH Actions [label: compare outputs]
Pipeline Parity Validator --> Migration Tracker Dashboard [label: parity report]

Migration Tiger Team -> Pipeline Parity Validator [label: sign off pipeline type]

# ===========================================================
# PHASE 3  —  CD MIGRATION
# ===========================================================

Platform Engineering Team -> Harness CD [label: Phase 3: model release pipelines]
Harness CD -> Harness Approval Gates [label: configure PROD gates]
Release Bridge (dual-run) -> XLRelease [label: existing releases continue]
Release Bridge (dual-run) -> Harness CD [label: new releases shadow-run]
Change Approval Board -> Harness Approval Gates [label: validate approval workflow]

Harness CD -> OpenShift PROD Cluster [label: deploy (same target)]
Ansible Tower -> OpenShift PROD Cluster [label: config (unchanged)]
Terraform -> OpenShift PROD Cluster [label: IaC (unchanged)]
Datical DB -> OpenShift PROD Cluster [label: DB migrations (unchanged)]

# ===========================================================
# GOVERNANCE
# ===========================================================

Migration Tracker Dashboard -> Migration Tiger Team [label: wave progress]
Migration Tracker Dashboard -> Change Approval Board [label: exec reporting]
Rollback Runbook -> Bitbucket Server [label: revert if needed Phase1]
Rollback Runbook -> Jenkins Shared Library (15 types) [label: revert if needed Phase2]
Rollback Runbook -> XLRelease [label: revert if needed Phase3]
