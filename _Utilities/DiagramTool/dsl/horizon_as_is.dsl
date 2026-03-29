# ===========================================================
# HORIZON — AS-IS  (Current State) — PROD Pipeline
# DevOps Platform  |  20k Developers  |  100k Repos
# ===========================================================

# -- People / Actors --------------------------------------
Actor: App Dev Teams (20k)
Actor: Platform Team
Actor: Release Manager
Actor: DBA Team

# -- Source Control ----------------------------------------
System: Bitbucket Server [color: blue]

# -- CI Layer — Jenkins Shared Library --------------------
System: Jenkins Master [color: orange]
System: Jenkins Agent Pool [color: orange]
System: Shared Library [color: orange]
System: Pipeline — Java Build [color: orange]
System: Pipeline — Python Build [color: orange]
System: Pipeline — MsBuild (.NET) [color: orange]
System: Pipeline — OpenShift Deploy [color: orange]
System: Pipeline — DB Datical [color: orange]

# -- Code Quality ------------------------------------------
System: SonarQube [color: teal]

# -- Artefact Management -----------------------------------
System: JFrog Artifactory [color: purple]

# -- CD / Release Orchestration ----------------------------
System: XLRelease [color: red]
System: XL Deploy [color: red]

# -- Config Management -------------------------------------
System: Ansible Tower [color: yellow]

# -- IaC ---------------------------------------------------
System: Terraform [color: gray]

# -- Test Management ---------------------------------------
System: Octane ALM [color: gray]

# -- Chaos Engineering -------------------------------------
System: Litmus Chaos [color: red]

# -- DB Migrations -----------------------------------------
System: Datical DB [color: teal]

# -- Target Platform ---------------------------------------
System: OpenShift PROD Cluster [color: green]
Database: PROD Databases [color: green]
System: OpenShift Registry [color: green]

# ===========================================================
# FLOW — Code to Production
# ===========================================================

App Dev Teams (20k) -> Bitbucket Server [label: git push / PR]
Platform Team -> Shared Library [label: maintain 15 pipeline types]
Shared Library -> Jenkins Master [label: loaded at runtime]

Bitbucket Server -> Jenkins Master [label: webhook trigger]
Jenkins Master -> Jenkins Agent Pool [label: dispatch build]

Jenkins Agent Pool -> Pipeline — Java Build [label: Java/Maven/Gradle]
Jenkins Agent Pool -> Pipeline — Python Build [label: Python/pip]
Jenkins Agent Pool -> Pipeline — MsBuild (.NET) [label: .NET/NuGet]
Jenkins Agent Pool -> Pipeline — OpenShift Deploy [label: OC deploy]
Jenkins Agent Pool -> Pipeline — DB Datical [label: DB change set]

Pipeline — Java Build -> SonarQube [label: SAST / quality gate]
Pipeline — Python Build -> SonarQube [label: SAST / quality gate]
Pipeline — MsBuild (.NET) -> SonarQube [label: SAST / quality gate]

SonarQube --> Jenkins Master [label: gate pass/fail]

Pipeline — Java Build -> JFrog Artifactory [label: publish JAR/Docker]
Pipeline — Python Build -> JFrog Artifactory [label: publish wheel/Docker]
Pipeline — MsBuild (.NET) -> JFrog Artifactory [label: publish NuGet/Docker]

JFrog Artifactory -> XLRelease [label: trigger release pipeline]
Release Manager -> XLRelease [label: approve PROD gate]
XLRelease -> XL Deploy [label: orchestrate deployment]

XL Deploy -> OpenShift PROD Cluster [label: rolling deploy]
JFrog Artifactory -> OpenShift Registry [label: image pull]
OpenShift Registry -> OpenShift PROD Cluster [label: serve images]

Ansible Tower -> OpenShift PROD Cluster [label: config & secrets]
Terraform -> OpenShift PROD Cluster [label: infra provisioning]

Pipeline — DB Datical -> Datical DB [label: validate + forecast]
DBA Team -> Datical DB [label: review change sets]
Datical DB -> PROD Databases [label: apply migrations]

Octane ALM -> XLRelease [label: test sign-off gate]
Litmus Chaos -> OpenShift PROD Cluster [label: resilience tests]

Platform Team -> Jenkins Master [label: ops & maintenance]
