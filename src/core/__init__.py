"""
Core/Business Layer - Business logic and domain models
No dependencies on GUI or database implementations
"""

from src.core.communication_config import (
	CommunicationConfigManager,
	CommunicationConfigLoader,
	CommunicationOptionMutationResult,
	CommunicationOptionDefinition,
	CommunicationQualifierDefinition,
	CommunicationSystemDefinition,
	SystemConfig,
)
from src.core.communication_portability import (
	build_communication_portability_bundle,
	COMMUNICATION_PORTABILITY_BUNDLE_KIND,
	COMMUNICATION_PORTABILITY_BUNDLE_VERSION,
	EXCLUDED_COMMUNICATION_PORTABILITY_DOMAINS,
	PORTABLE_COMMUNICATION_DOMAINS,
	CommunicationPortabilityBundle,
	CommunicationPortabilityContractError,
	CommunicationPortabilityImportResult,
	CommunicationPortabilityImportTarget,
	export_communication_portability_payload,
	import_communication_portability_payload,
	parse_communication_portability_payload,
	PortableCommunicationOption,
	PortableCommunicationQualifier,
	PortableCommunicationSystem,
	validate_communication_portability_payload,
)
from src.core.entries import CommunicationEntry, EventEntry, PersonnelEntry
from src.core.reset_report import (
	ResetAttemptFacts,
	ResetFollowUpFacts,
	ResetFollowUpIssue,
	ResetReport,
	assemble_reset_report,
	assemble_reset_report_from_facts,
	normalize_reset_follow_up_issues,
)

__all__ = [
	"CommunicationConfigManager",
	"CommunicationConfigLoader",
	"CommunicationEntry",
	"CommunicationOptionDefinition",
	"CommunicationOptionMutationResult",
	"COMMUNICATION_PORTABILITY_BUNDLE_KIND",
	"COMMUNICATION_PORTABILITY_BUNDLE_VERSION",
	"CommunicationQualifierDefinition",
	"CommunicationPortabilityBundle",
	"CommunicationPortabilityContractError",
	"CommunicationPortabilityImportResult",
	"CommunicationPortabilityImportTarget",
	"CommunicationSystemDefinition",
	"EXCLUDED_COMMUNICATION_PORTABILITY_DOMAINS",
	"EventEntry",
	"PORTABLE_COMMUNICATION_DOMAINS",
	"PersonnelEntry",
	"PortableCommunicationOption",
	"PortableCommunicationQualifier",
	"PortableCommunicationSystem",
	"ResetAttemptFacts",
	"ResetFollowUpFacts",
	"ResetFollowUpIssue",
	"ResetReport",
	"SystemConfig",
	"assemble_reset_report",
	"assemble_reset_report_from_facts",
	"build_communication_portability_bundle",
	"export_communication_portability_payload",
	"import_communication_portability_payload",
	"normalize_reset_follow_up_issues",
	"parse_communication_portability_payload",
	"validate_communication_portability_payload",
]

