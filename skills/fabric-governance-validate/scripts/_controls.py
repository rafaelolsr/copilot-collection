"""Shared governance control rubric for the fabric-governance-validate skill.

Purpose:
    Single source of truth for the controls scored by ``validate_governance.py``.
    Mirrors ``references/governance-controls.md`` — keep the two in sync.

Usage:
    from _controls import CONTROLS  # list[Control]

Each control declares an evidence key (a dotted path into the evidence JSON),
the requirement, a severity, and the Microsoft Learn search terms used to ground
the requirement with a citation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["high", "medium", "low"]
Scope = Literal["workspace", "tenant"]
CheckKind = Literal[
    "int_between",
    "int_min",
    "int_max",
    "all_items_truthy",
    "present",
    "is_true",
    "none_failed",
    "all_recent_days",
]


@dataclass(slots=True, frozen=True)
class Control:
    """One governance control and how to evaluate it against evidence."""

    id: str
    severity: Severity
    requirement: str
    evidence_key: str
    learn_terms: str
    check: CheckKind
    scope: Scope = "workspace"
    bounds: tuple[int | None, int | None] = (None, None)


CONTROLS: list[Control] = [
    Control(
        id="workspace-admin-count",
        severity="high",
        requirement="Between 2 and 5 workspace Admins (avoid single-owner and over-grant).",
        evidence_key="roles.admin_count",
        learn_terms="Microsoft Fabric workspace roles least privilege admin",
        check="int_between",
        bounds=(2, 5),
    ),
    Control(
        id="no-guest-access",
        severity="high",
        requirement="No external/guest (B2B) users hold workspace roles unless approved.",
        evidence_key="roles.guest_count",
        learn_terms="Microsoft Fabric external guest user access governance",
        check="int_max",
        scope="tenant",
        bounds=(None, 0),
    ),
    Control(
        id="service-principal-control",
        severity="medium",
        requirement="Service principals with workspace access are inventoried and scoped.",
        evidence_key="roles.service_principal_count",
        learn_terms="Microsoft Fabric service principal workspace access",
        check="present",
    ),
    Control(
        id="sensitivity-labels",
        severity="high",
        requirement="Every item carries a Microsoft Purview sensitivity label.",
        evidence_key="items[].sensitivityLabel",
        learn_terms="Microsoft Fabric sensitivity labels Purview information protection",
        check="all_items_truthy",
    ),
    Control(
        id="object-ownership",
        severity="high",
        requirement="Every item has an identifiable owner (no orphaned objects).",
        evidence_key="items[].owner",
        learn_terms="Microsoft Fabric item ownership take over orphaned dataset owner",
        check="all_items_truthy",
        scope="tenant",
    ),
    Control(
        id="dlp-coverage",
        severity="medium",
        requirement="Data loss prevention policies apply to the workspace.",
        evidence_key="workspace.dlpEnabled",
        learn_terms="Microsoft Fabric data loss prevention policy Power BI",
        check="is_true",
        scope="tenant",
    ),
    Control(
        id="domain-assignment",
        severity="medium",
        requirement="The workspace is assigned to a Fabric domain (data mesh).",
        evidence_key="workspace.domainId",
        learn_terms="Microsoft Fabric domains data mesh assign workspace",
        check="present",
        scope="tenant",
    ),
    Control(
        id="endorsement",
        severity="medium",
        requirement="Production items are Promoted or Certified.",
        evidence_key="items[].endorsement",
        learn_terms="Microsoft Fabric endorsement certified promoted content",
        check="all_items_truthy",
        scope="tenant",
    ),
    Control(
        id="workspace-metadata",
        severity="low",
        requirement="Workspace has a description.",
        evidence_key="workspace.description",
        learn_terms="Microsoft Fabric workspace settings description contact",
        check="present",
    ),
    Control(
        id="deployment-pipeline",
        severity="high",
        requirement="The workspace participates in a deployment pipeline.",
        evidence_key="workspace.deploymentPipelineId",
        learn_terms="Microsoft Fabric deployment pipelines lifecycle management",
        check="present",
    ),
    Control(
        id="git-integration",
        severity="medium",
        requirement="The workspace is connected to Git source control.",
        evidence_key="workspace.gitConnected",
        learn_terms="Microsoft Fabric Git integration source control workspace",
        check="is_true",
    ),
    Control(
        id="capacity-assignment",
        severity="high",
        requirement="The workspace is on a dedicated Fabric capacity.",
        evidence_key="workspace.capacityId",
        learn_terms="Microsoft Fabric capacity assign workspace governance",
        check="present",
    ),
    Control(
        id="refresh-health",
        severity="high",
        requirement="No semantic model's last refresh failed.",
        evidence_key="semantic_models[].lastRefresh.status",
        learn_terms="Power BI semantic model refresh failure troubleshoot",
        check="none_failed",
    ),
    Control(
        id="refresh-recency",
        severity="medium",
        requirement="Every refreshable semantic model refreshed within the recency window.",
        evidence_key="semantic_models[].lastRefresh.endTime",
        learn_terms="Power BI dataset scheduled refresh data freshness",
        check="all_recent_days",
        bounds=(1, None),
    ),
]

SEVERITY_ORDER: dict[Severity, int] = {"high": 0, "medium": 1, "low": 2}
