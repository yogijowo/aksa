"""Tests for Phase 1 SQLite database initialization, Indonesian team seeding, and REST endpoints."""

from __future__ import annotations

from pathlib import Path
import pytest
from app.db.models import DatabaseManager
from app.db.seed import seed_default_indonesian_team


@pytest.mark.asyncio
async def test_database_and_default_indonesian_seed(tmp_path: Path) -> None:
    db_file = tmp_path / "test_aksa.db"
    db = DatabaseManager(db_path=db_file)
    await db.initialize()
    await seed_default_indonesian_team(db)

    teams = await db.list_teams_with_agents()
    assert len(teams) == 1
    default_team = teams[0]
    assert default_team["name"] == "Tim Produktivitas Kantor Indonesia"
    assert len(default_team["agents"]) == 4

    supervisor = next(a for a in default_team["agents"] if a["tier_level"] == 0)
    assert supervisor["name"] == "Manajer Eksekutif"
    assert supervisor["parent_id"] is None

    sub_agents = [a for a in default_team["agents"] if a["tier_level"] == 1]
    assert len(sub_agents) == 3
    for sub in sub_agents:
        assert sub["parent_id"] == supervisor["id"]

