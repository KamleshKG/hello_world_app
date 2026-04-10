# ===========================================================
# HORIZON — TO-BE  (Target State) — PROD Pipeline
# DevOps Platform  |  20k Developers  |  100k Repos
# ===========================================================

# -- People / Actors --------------------------------------
Actor: App Dev Teams (20k)
Actor: Platform Team
Actor: Release Manager
Actor: DBA Team

# -- Source Control ----------------------------------------
System: GitHub Enterprise Cloud [color: gray]

# -- CI Layer — GitHub Actions ----------------------------
System: GitHub Actions [color: blue]
System: Reusable Workflow — Java [color: blue]
System: Reusable Workflow — Python [color: blue]
System: Reusable Workflow — MsBuild [color: blue]
System: Reusable Workflow — OpenShift [color: blue]
System: Reusable Workflow — DB Datical [color: blue]
System: Self-Hosted Runner Pool [color: blue]

# -- Code Quality (RETAINED) -------------------------------
System: SonarQube [color: teal]

# -- Artefact Management (RETAINED) -----------------------
System: JFrog Artifactory [color: purple]

# -- CD / Release — Harness --------------------------------
System: Harness CD [color: green]
System: Harness Pipeline — PROD [color: green]
System: Harness Approval Gate [color: green]

# -- Config Management (RETAINED) -------------------------
System: Ansible Tower [color: yellow]

# -- IaC (RETAINED) ----------------------------------------
System: Terraform [color: gray]

# -- Test Management (RETAINED) ----------------------------
System: Octane ALM [color: gray]

# -- Chaos Engineering (RETAINED) -------------------------
System: Litmus Chaos [color: red]

# -- DB Migrations (RETAINED) ------------------------------
System: Datical DB [color: teal]

# -- Target Platform (RETAINED) ----------------------------
System: OpenShift PROD Cluster [color: green]
Database: PROD Databases [color: green]
System: OpenShift Registry [color: green]

# -- Observability (NEW) -----------------------------------
System: Harness Dashboards [color: green]

# ===========================================================
# FLOW — Code to Production (Target State)
# ===========================================================

App Dev Teams (20k) -> GitHub Enterprise Cloud [label: git push / PR]
Platform Team -> Reusable Workflow — Java [label: maintain workflow library]
Platform Team -> Reusable Workflow — Python [label: maintain workflow library]
Platform Team -> Reusable Workflow — MsBuild [label: maintain workflow library]

GitHub Enterprise Cloud -> GitHub Actions [label: on push / PR merge]
GitHub Actions -> Self-Hosted Runner Pool [label: dispatch job]

Self-Hosted Runner Pool -> Reusable Workflow — Java [label: java/maven/gradle]
Self-Hosted Runner Pool -> Reusable Workflow — Python [label: python/pip/poetry]
Self-Hosted Runner Pool -> Reusable Workflow — MsBuild [label: .net/nuget]
Self-Hosted Runner Pool -> Reusable Workflow — OpenShift [label: oc deploy]
Self-Hosted Runner Pool -> Reusable Workflow — DB Datical [label: db changeset]

Reusable Workflow — Java -> SonarQube [label: SAST quality gate]
Reusable Workflow — Python -> SonarQube [label: SAST quality gate]
Reusable Workflow — MsBuild -> SonarQube [label: SAST quality gate]
SonarQube --> GitHub Actions [label: gate pass/fail]

Reusable Workflow — Java -> JFrog Artifactory [label: publish JAR/Docker]
Reusable Workflow — Python -> JFrog Artifactory [label: publish wheel/Docker]
Reusable Workflow — MsBuild -> JFrog Artifactory [label: publish NuGet/Docker]

JFrog Artifactory -> Harness CD [label: artifact trigger]
Harness CD -> Harness Pipeline — PROD [label: execute]
Harness Pipeline — PROD -> Harness Approval Gate [label: request approval]
Release Manager -> Harness Approval Gate [label: approve PROD release]
Harness Approval Gate -> OpenShift PROD Cluster [label: rolling deploy]

JFrog Artifactory -> OpenShift Registry [label: image pull]
OpenShift Registry -> OpenShift PROD Cluster [label: serve images]

Ansible Tower -> OpenShift PROD Cluster [label: config & secrets]
Terraform -> OpenShift PROD Cluster [label: infra provisioning]

Reusable Workflow — DB Datical -> Datical DB [label: validate + forecast]
DBA Team -> Datical DB [label: review change sets]
Datical DB -> PROD Databases [label: apply migrations]

Octane ALM -> Harness Approval Gate [label: test sign-off]
Litmus Chaos -> OpenShift PROD Cluster [label: resilience tests]

Harness Dashboards -> Harness CD [label: pipeline metrics]
Harness Dashboards -> OpenShift PROD Cluster [label: deployment status]
