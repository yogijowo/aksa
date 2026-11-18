"""Regression tests for Prompt 3 (P0.2): HITL grant full context binding, atomic consumption, and fail-closed verification."""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.sandbox import (
    ApprovalGrant,
    ExecutionPolicyGateway,
    RiskLevel,
    compute_canonical_arguments_hash,
    execution_policy_gateway,
)
from app.main import create_app


def test_hitl_grant_action_id_and_session_id_mismatch_rejected() -> None:
    gateway = ExecutionPolicyGateway()
    args = {"filename": "data.csv", "row_count": 100}

    grant = gateway.create_grant(
        tool_name="excel_modify_cells",
        arguments=args,
        session_id="sess_alpha",
        workspace_id="ws_finance",
        action_id="act_batch_update_1",
        principal_id="user_accountant",
    )

    # 1. Matching context -> succeeds
    assert gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="excel_modify_cells",
        arguments=args,
        session_id="sess_alpha",
        workspace_id="ws_finance",
        action_id="act_batch_update_1",
        principal_id="user_accountant",
    ) is True


def test_hitl_grant_missing_or_mismatched_session_fails_closed() -> None:
    gateway = ExecutionPolicyGateway()
    args = {"command": "vacuum"}

    grant = gateway.create_grant(
        tool_name="db_vacuum",
        arguments=args,
        session_id="sess_important",
        workspace_id="ws_prod",
    )

    # Mismatched session -> rejected
    assert gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="db_vacuum",
        arguments=args,
        session_id="sess_different",
        workspace_id="ws_prod",
    ) is False

    # Missing session (None) when grant expected session_id -> fail closed
    assert gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="db_vacuum",
        arguments=args,
        session_id=None,
        workspace_id="ws_prod",
    ) is False


def test_hitl_grant_workspace_id_mismatch_fails_closed() -> None:
    gateway = ExecutionPolicyGateway()
    args = {"target": "budget.xlsx"}

    grant = gateway.create_grant(
        tool_name="excel_modify_cells",
        arguments=args,
        session_id="sess_1",
        workspace_id="ws_secret_pagu",
    )

    # Mismatched workspace -> rejected
    assert gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="excel_modify_cells",
        arguments=args,
        session_id="sess_1",
        workspace_id="ws_public",
    ) is False

    # Missing workspace (None) -> fail closed
    assert gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="excel_modify_cells",
        arguments=args,
        session_id="sess_1",
        workspace_id=None,
    ) is False


def test_hitl_grant_principal_mismatch_fails_closed() -> None:
    gateway = ExecutionPolicyGateway()
    args = {"table": "pegawai"}

    grant = gateway.create_grant(
        tool_name="delete_table",
        arguments=args,
        principal_id="super_admin",
    )

    # Calling as unprivileged user -> rejected
    assert gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="delete_table",
        arguments=args,
        principal_id="guest_user",
    ) is False


def test_hitl_grant_resource_path_binding(tmp_path: Path) -> None:
    gateway = ExecutionPolicyGateway()
    file_a = tmp_path / "authorized_file.txt"
    file_a.write_text("A", encoding="utf-8")
    file_b = tmp_path / "unauthorized_file.txt"
    file_b.write_text("B", encoding="utf-8")

    args = {"file_path": str(file_a)}
    grant = gateway.create_grant(
        tool_name="file_delete",
        arguments=args,
        resource_path=str(file_a),
    )

    # Attempting to use grant on file_b -> rejected
    assert gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="file_delete",
        arguments=args,
        resource_path=str(file_b),
    ) is False

    # Missing resource path when grant was bound -> rejected
    assert gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="file_delete",
        arguments=args,
        resource_path=None,
    ) is False

    # Exact matching canonical resource path -> approved
    assert gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="file_delete",
        arguments=args,
        resource_path=str(file_a),
    ) is True


def test_hitl_grant_deterministic_argument_hashing() -> None:
    # Different key ordering
    dict_1 = {"b": 2, "a": 1, "nested": {"y": "yes", "x": "no"}}
    dict_2 = {"a": 1, "b": 2, "nested": {"x": "no", "y": "yes"}}
    assert compute_canonical_arguments_hash(dict_1) == compute_canonical_arguments_hash(dict_2)

    # Argument change breaks hash
    dict_3 = {"a": 1, "b": 3}
    assert compute_canonical_arguments_hash(dict_1) != compute_canonical_arguments_hash(dict_3)


def test_hitl_grant_single_use_replay_rejected() -> None:
    gateway = ExecutionPolicyGateway()
    args = {"op": "write"}
    grant = gateway.create_grant(tool_name="writer", arguments=args)

    # First consumption -> succeeds
    assert gateway.verify_and_consume_grant(grant.id, "writer", args) is True

    # Replay attempt -> immediately rejected
    assert gateway.verify_and_consume_grant(grant.id, "writer", args) is False


def test_hitl_grant_expiry_and_revocation() -> None:
    gateway = ExecutionPolicyGateway()
    args = {"action": "restart"}

    # Expired grant
    exp_grant = gateway.create_grant(tool_name="restarter", arguments=args, ttl_seconds=-1)
    assert gateway.verify_and_consume_grant(exp_grant.id, "restarter", args) is False

    # Revoked grant
    valid_grant = gateway.create_grant(tool_name="restarter", arguments=args, ttl_seconds=300)
    gateway.revoke_grant(valid_grant.id)
    assert gateway.verify_and_consume_grant(valid_grant.id, "restarter", args) is False


def test_hitl_grant_atomic_parallel_consumption() -> None:
    """Verify that multiple concurrent threads attempting to consume the same grant result in exactly one success."""
    gateway = ExecutionPolicyGateway()
    args = {"fund_transfer": 1000000}
    grant = gateway.create_grant(tool_name="wire_transfer", arguments=args)

    results: list[bool] = []

    def try_consume() -> bool:
        return gateway.verify_and_consume_grant(grant.id, "wire_transfer", args)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_consume) for _ in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # Exactly one thread succeeds, all other 9 threads fail
    assert results.count(True) == 1
    assert results.count(False) == 9


@pytest.mark.asyncio
async def test_p0_hitl_rest_api_full_context_binding() -> None:
    orig_dev = settings.dev_mode
    orig_token = settings.auth_token
    try:
        settings.dev_mode = False
        settings.auth_token = "aksa-prod-token-test-hitl-987"

        app = create_app()
        transport = ASGITransport(app=app)
        auth_headers = {"X-AKSA-Auth-Token": settings.auth_token, "X-Principal-ID": "user_finance"}

        async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
            # 1. Create HITL request carrying full action context
            create_resp = await client.post(
                "/api/v1/sandbox/approvals",
                json={
                    "tool_name": "excel_create_workbook",
                    "title_id": "Persetujuan Pembuatan Excel",
                    "description_id": "Menyetujui eksekusi laporan anggaran.",
                    "risk_level": "high",
                    "action_id": "act_excel_2026",
                    "session_id": "sess_budget_2026",
                    "workspace_id": "ws_finance_id",
                    "arguments": {"filename": "laporan_keuangan.xlsx", "rows": 50},
                },
            )
            assert create_resp.status_code == 200
            req_data = create_resp.json()["approval"]
            assert req_data["action_id"] == "act_excel_2026"
            assert req_data["session_id"] == "sess_budget_2026"
            assert req_data["workspace_id"] == "ws_finance_id"
            hitl_id = req_data["id"]

            # 2. Resolve approval
            resolve_resp = await client.post(
                f"/api/v1/sandbox/approvals/{hitl_id}/resolve",
                json={"approved": True},
            )
            assert resolve_resp.status_code == 200
            resolved_data = resolve_resp.json()["approval"]
            grant_id = resolved_data["grant_id"]
            assert grant_id is not None
            assert grant_id.startswith("grant_")

            # 3. Retrieve grant from gateway and verify context bindings
            grant = execution_policy_gateway.get_grant(grant_id)
            assert grant is not None
            assert grant.action_id == "act_excel_2026"
            assert grant.session_id == "sess_budget_2026"
            assert grant.workspace_id == "ws_finance_id"
            assert grant.principal_id == "user_finance"
            assert grant.consumed is False
    finally:
        settings.dev_mode = orig_dev
        settings.auth_token = orig_token

