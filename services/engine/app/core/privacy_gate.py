"""LLM Provider Mode, Data Classification, and Data Disclosure Gate.

Implements Section 6 of the AKSA Enterprise Readiness Master Specification:
- Explicit Provider Modes: local_only, cloud_by_choice, hybrid_with_consent, enterprise_managed
- Data Classification: PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED
- DataDisclosureGate: blocks unauthorized cloud data egress and prevents automatic document attachment
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ProviderMode(str, Enum):
    """Explicit LLM routing & privacy modes."""

    LOCAL_ONLY = "local_only"
    CLOUD_BY_CHOICE = "cloud_by_choice"
    HYBRID_WITH_CONSENT = "hybrid_with_consent"
    ENTERPRISE_MANAGED = "enterprise_managed"


class DataClassification(str, Enum):
    """Sensitivity classification for prompts, workspaces, and files."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


LOCAL_PROVIDERS = {"ollama", "lmstudio"}
CLOUD_PROVIDERS = {"gemini", "anthropic", "openai", "deepseek", "groq", "openrouter"}


class DataDisclosureSummary(BaseModel):
    """Structured summary displayed to the user before external cloud processing."""

    provider: str
    model_id: str
    provider_mode: ProviderMode
    data_classification: DataClassification
    data_types: list[str] = Field(default_factory=lambda: ["prompt"])
    attached_resources: list[str] = Field(default_factory=list)
    purpose: str = "Pemrosesan instruksi pengguna melalui model cloud eksternal"
    retention_notice: str = (
        "Data dikirim melalui koneksi HTTPS terenkripsi ke penyedia model cloud sesuai kebijakan privasi penyedia."
    )
    redaction_applied: bool = False
    requires_explicit_consent: bool = False
    allowed: bool = True
    denial_reason: str | None = None


class PrivacyPolicyGate:
    """Enforces provider mode constraints, data classification rules, and disclosure gates."""

    def __init__(self) -> None:
        self.provider_mode: ProviderMode = ProviderMode.CLOUD_BY_CHOICE
        self.default_classification: DataClassification = DataClassification.INTERNAL
        self.allowed_enterprise_providers: set[str] = set(LOCAL_PROVIDERS | CLOUD_PROVIDERS)
        self.telemetry_opt_in: bool = False

    def configure(
        self,
        provider_mode: str | ProviderMode | None = None,
        default_classification: str | DataClassification | None = None,
        allowed_providers: list[str] | None = None,
        telemetry_opt_in: bool | None = None,
    ) -> dict[str, Any]:
        if provider_mode is not None:
            self.provider_mode = ProviderMode(provider_mode)
        if default_classification is not None:
            self.default_classification = DataClassification(default_classification)
        if allowed_providers is not None:
            self.allowed_enterprise_providers = set(allowed_providers)
        if telemetry_opt_in is not None:
            self.telemetry_opt_in = bool(telemetry_opt_in)
        return self.get_status()

    def get_status(self) -> dict[str, Any]:
        return {
            "provider_mode": self.provider_mode.value,
            "default_classification": self.default_classification.value,
            "allowed_enterprise_providers": sorted(self.allowed_enterprise_providers),
            "telemetry_opt_in": self.telemetry_opt_in,
        }

    def is_local_provider(self, provider: str) -> bool:
        return provider.lower().strip() in LOCAL_PROVIDERS

    def classify_request_data(
        self,
        messages: list[dict[str, str]],
        explicit_classification: str | DataClassification | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> DataClassification:
        """Determine data classification using deterministic rules and explicit labels."""
        if explicit_classification is not None:
            return DataClassification(explicit_classification)

        combined_text = " ".join(m.get("content", "") for m in messages).lower()
        if any(
            marker in combined_text
            for marker in ("rahasia negara", "sangat rahasia", "top secret", "[restricted]", "password", "private key")
        ):
            return DataClassification.RESTRICTED

        if attachments or any(
            marker in combined_text
            for marker in ("rahasia perusahaan", "[confidential]", "nik:", "npwp:", "rekening koran")
        ):
            return DataClassification.CONFIDENTIAL

        return self.default_classification

    def evaluate_disclosure(
        self,
        provider: str,
        model_id: str,
        messages: list[dict[str, str]],
        attachments: list[dict[str, Any]] | None = None,
        explicit_classification: str | DataClassification | None = None,
        user_consent_granted: bool = False,
    ) -> DataDisclosureSummary:
        """Evaluate whether a request is allowed to proceed to the target LLM provider."""
        prov = provider.lower().strip()
        is_local = self.is_local_provider(prov)
        classification = self.classify_request_data(
            messages=messages,
            explicit_classification=explicit_classification,
            attachments=attachments,
        )

        data_types = ["prompt"]
        attached_names: list[str] = []
        if attachments:
            data_types.append("document_attachment")
            attached_names = [str(a.get("name", "dokumen")) for a in attachments]

        summary = DataDisclosureSummary(
            provider=prov,
            model_id=model_id,
            provider_mode=self.provider_mode,
            data_classification=classification,
            data_types=data_types,
            attached_resources=attached_names,
        )

        # Rule 1: Local providers never send data externally
        if is_local:
            summary.purpose = "Pemrosesan lokal 100% di dalam perangkat (tanpa pengiriman keluar)"
            summary.retention_notice = "Data tetap berada di memori lokal perangkat Anda."
            summary.allowed = True
            return summary

        # Rule 2: LOCAL_ONLY mode strictly blocks all cloud providers
        if self.provider_mode == ProviderMode.LOCAL_ONLY:
            summary.allowed = False
            summary.denial_reason = (
                f"Mode Privasi 'Local-Only' sedang aktif. Pengiriman data ke penyedia cloud '{prov}' "
                "diblokir sepenuhnya (tidak ada fallback ke cloud)."
            )
            return summary

        # Rule 3: Enterprise Managed provider allowlist
        if self.provider_mode == ProviderMode.ENTERPRISE_MANAGED and prov not in self.allowed_enterprise_providers:
            summary.allowed = False
            summary.denial_reason = (
                f"Penyedia '{prov}' tidak termasuk dalam daftar izin kebijakan Enterprise Managed."
            )
            return summary

        # Rule 4: RESTRICTED data is blocked from cloud providers
        if classification == DataClassification.RESTRICTED:
            summary.allowed = False
            summary.denial_reason = (
                "Data berklasifikasi RESTRICTED tidak diizinkan dikirim ke penyedia cloud eksternal."
            )
            return summary

        # Rule 5: CONFIDENTIAL data or document attachments require explicit consent in HYBRID_WITH_CONSENT mode
        if (
            classification == DataClassification.CONFIDENTIAL
            and self.provider_mode == ProviderMode.HYBRID_WITH_CONSENT
            and not user_consent_granted
        ):
            summary.requires_explicit_consent = True
            summary.allowed = False
            summary.denial_reason = (
                "Data berklasifikasi CONFIDENTIAL atau lampiran dokumen memerlukan persetujuan eksplisit "
                "(Data Disclosure Gate) sebelum dikirim ke penyedia cloud."
            )
            return summary

        # Rule 6: Any external document attachment requires explicit user consent
        if attachments and not user_consent_granted:
            summary.requires_explicit_consent = True
            summary.allowed = False
            summary.denial_reason = (
                "Pengiriman lampiran dokumen ke penyedia cloud memerlukan persetujuan eksplisit pengguna."
            )
            return summary

        summary.allowed = True
        return summary


privacy_policy_gate = PrivacyPolicyGate()
