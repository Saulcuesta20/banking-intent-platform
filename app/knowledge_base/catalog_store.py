from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.events import emit_asset_status_change
from app.knowledge_base.models import EnterpriseAsset
from app.knowledge_base.registry import EnterpriseAssetRegistry


@dataclass(frozen=True)
class AssetCatalogStore:
    """SQLite-backed asset catalog with global ids, locations, and relations."""

    path: Path

    def initialize(self, *, clear: bool = False) -> None:
        """Create catalog tables and optionally remove previous catalog data."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id TEXT PRIMARY KEY,
                    asset_type TEXT NOT NULL,
                    name TEXT,
                    version TEXT,
                    status TEXT,
                    primary_kb TEXT,
                    stores_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS relationships (
                    source_asset_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    target_asset_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (source_asset_id, relation_type, target_asset_id)
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_assets_primary_kb ON assets(primary_kb)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_relationship_target ON relationships(target_asset_id)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_versions (
                    asset_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    name TEXT,
                    status TEXT NOT NULL,
                    domain_id TEXT,
                    module_id TEXT,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    stores_json TEXT NOT NULL DEFAULT '[]',
                    payload_json TEXT NOT NULL,
                    checksum TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (asset_id, version)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_sets (
                    asset_set_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    domain_id TEXT,
                    module_id TEXT,
                    asset_type TEXT,
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_set_versions (
                    asset_set_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    git_commit TEXT,
                    checksum TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (asset_set_id, version)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_set_members (
                    asset_set_id TEXT NOT NULL,
                    asset_set_version TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    asset_version TEXT NOT NULL,
                    PRIMARY KEY (asset_set_id, asset_set_version, asset_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    asset_set_id TEXT NOT NULL,
                    asset_set_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reviewer TEXT,
                    comment TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS deployments (
                    deployment_id TEXT PRIMARY KEY,
                    asset_set_id TEXT NOT NULL,
                    asset_set_version TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    status TEXT NOT NULL,
                    previous_version TEXT,
                    deployed_by TEXT NOT NULL,
                    projection_results_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_asset_sets (
                    environment TEXT NOT NULL,
                    asset_set_id TEXT NOT NULL,
                    asset_set_version TEXT NOT NULL,
                    deployment_id TEXT NOT NULL,
                    activated_at TEXT NOT NULL,
                    PRIMARY KEY (environment, asset_set_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS lifecycle_events (
                    event_id TEXT PRIMARY KEY,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    subject_version TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    comment TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_asset_versions_type ON asset_versions(asset_type)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_asset_versions_status ON asset_versions(status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_asset_versions_domain ON asset_versions(domain_id, module_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_asset_set_members_asset ON asset_set_members(asset_id, asset_version)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_deployments_set ON deployments(asset_set_id, environment)")
            self._ensure_column(connection, "assets", "canonical_name", "TEXT")
            self._ensure_column(connection, "assets", "normalized_name", "TEXT")
            self._ensure_column(connection, "assets", "aliases_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(connection, "assets", "structural_layer", "TEXT")
            self._ensure_column(connection, "assets", "business_layer", "TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_assets_structural_layer ON assets(structural_layer)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_assets_business_layer ON assets(business_layer)")
            if clear:
                connection.execute("DELETE FROM lifecycle_events")
                connection.execute("DELETE FROM active_asset_sets")
                connection.execute("DELETE FROM deployments")
                connection.execute("DELETE FROM reviews")
                connection.execute("DELETE FROM asset_set_members")
                connection.execute("DELETE FROM asset_set_versions")
                connection.execute("DELETE FROM asset_sets")
                connection.execute("DELETE FROM asset_versions")
                connection.execute("DELETE FROM relationships")
                connection.execute("DELETE FROM assets")

    def upsert_asset(self, asset: EnterpriseAsset, registry: EnterpriseAssetRegistry) -> None:
        """Store one asset plus its outbound relationships."""
        stores = registry.stores_for(asset.asset_type)
        primary_kb = asset.owner or registry.owner_kb_for(asset.asset_type) or self._primary_kb_for(stores)
        canonical_name = self._canonical_name_for(asset)
        normalized_name = self._normalized_name(canonical_name or asset.asset_id)
        aliases = self._aliases_for(asset)
        payload = asset.payload or {}
        structural_layer = (
            getattr(asset, "structural_layer", None)
            or (payload.get("structural_layer") if isinstance(payload, dict) else None)
            or getattr(asset, "business_layer", None)
            or (payload.get("business_layer") if isinstance(payload, dict) else None)
        )
        business_layer = getattr(asset, "business_layer", None) or structural_layer
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO assets (
                    asset_id, asset_type, name, version, status, primary_kb, stores_json, payload_json,
                    canonical_name, normalized_name, aliases_json, structural_layer, business_layer, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(asset_id) DO UPDATE SET
                    asset_type = excluded.asset_type,
                    name = excluded.name,
                    version = excluded.version,
                    status = excluded.status,
                    primary_kb = excluded.primary_kb,
                    stores_json = excluded.stores_json,
                    payload_json = excluded.payload_json,
                    canonical_name = excluded.canonical_name,
                    normalized_name = excluded.normalized_name,
                    aliases_json = excluded.aliases_json,
                    structural_layer = excluded.structural_layer,
                    business_layer = excluded.business_layer,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    asset.asset_id,
                    asset.asset_type,
                    asset.name,
                    asset.version,
                    asset.status,
                    primary_kb,
                    json.dumps(stores, ensure_ascii=False),
                    json.dumps(asset.model_dump(mode="json"), ensure_ascii=False),
                    canonical_name,
                    normalized_name,
                    json.dumps(aliases, ensure_ascii=False),
                    structural_layer,
                    business_layer,
                ),
            )
            connection.execute("DELETE FROM relationships WHERE source_asset_id = ?", (asset.asset_id,))
            for relation in asset.relations:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO relationships (
                        source_asset_id, relation_type, target_asset_id, metadata_json
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        asset.asset_id,
                        relation.type,
                        relation.target_asset_id,
                        json.dumps(relation.metadata, ensure_ascii=False),
                    ),
                )
            self._upsert_asset_version(connection, asset, stores)

    def upsert_asset_set(
        self,
        *,
        asset_set_id: str,
        name: str,
        version: str,
        status: str,
        checksum: str,
        domain_id: str | None,
        module_id: str | None,
        asset_type: str | None,
        description: str,
        git_commit: str | None,
        metadata: dict[str, Any],
        members: list[tuple[str, str]],
    ) -> None:
        """Store one immutable AssetSet version and its exact asset members."""
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO asset_sets (
                    asset_set_id, name, domain_id, module_id, asset_type, description, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_set_id) DO UPDATE SET
                    name = excluded.name,
                    domain_id = excluded.domain_id,
                    module_id = excluded.module_id,
                    asset_type = excluded.asset_type,
                    description = excluded.description,
                    updated_at = excluded.updated_at
                """,
                (asset_set_id, name, domain_id, module_id, asset_type, description, now),
            )
            connection.execute(
                """
                INSERT INTO asset_set_versions (
                    asset_set_id, version, status, git_commit, checksum, metadata_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_set_id, version) DO UPDATE SET
                    status = excluded.status,
                    git_commit = excluded.git_commit,
                    checksum = excluded.checksum,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (asset_set_id, version, status, git_commit, checksum, json.dumps(metadata), now),
            )
            connection.execute(
                "DELETE FROM asset_set_members WHERE asset_set_id = ? AND asset_set_version = ?",
                (asset_set_id, version),
            )
            connection.executemany(
                """
                INSERT INTO asset_set_members (
                    asset_set_id, asset_set_version, asset_id, asset_version
                ) VALUES (?, ?, ?, ?)
                """,
                [(asset_set_id, version, asset_id, asset_version) for asset_id, asset_version in members],
            )

    def transition_asset_set(
        self,
        *,
        asset_set_id: str,
        version: str,
        to_status: str,
        actor: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Apply a guarded lifecycle transition to an AssetSet and its members."""
        allowed = {
            "draft": {"ready_for_review"},
            "ready_for_review": {"in_review"},
            "in_review": {"validated", "rejected", "draft"},
            "rejected": {"draft"},
            "validated": {"active", "draft"},
            "active": {"deprecated"},
            "deprecated": {"retired", "active"},
            "retired": set(),
        }
        now = self._now()
        member_asset_ids: list[str] = []
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM asset_set_versions WHERE asset_set_id = ? AND version = ?",
                (asset_set_id, version),
            ).fetchone()
            if row is None:
                raise KeyError(f"AssetSet version not found: {asset_set_id}@{version}")
            from_status = str(row["status"])
            if to_status not in allowed.get(from_status, set()):
                raise ValueError(f"Invalid AssetSet transition: {from_status} -> {to_status}")
            connection.execute(
                """
                UPDATE asset_set_versions SET status = ?, updated_at = ?
                WHERE asset_set_id = ? AND version = ?
                """,
                (to_status, now, asset_set_id, version),
            )
            connection.execute(
                """
                UPDATE asset_versions SET status = ?, updated_at = ?
                WHERE (asset_id, version) IN (
                    SELECT asset_id, asset_version FROM asset_set_members
                    WHERE asset_set_id = ? AND asset_set_version = ?
                )
                """,
                (to_status, now, asset_set_id, version),
            )
            member_rows = connection.execute(
                "SELECT asset_id FROM asset_set_members WHERE asset_set_id = ? AND asset_set_version = ?",
                (asset_set_id, version),
            ).fetchall()
            member_asset_ids = [str(r["asset_id"]) for r in member_rows]
            connection.execute(
                """
                INSERT INTO lifecycle_events (
                    event_id, subject_type, subject_id, subject_version,
                    from_status, to_status, actor, comment, created_at
                ) VALUES (?, 'asset_set', ?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), asset_set_id, version, from_status, to_status, actor, comment, now),
            )
            if to_status in {"in_review", "validated", "rejected", "draft"}:
                connection.execute(
                    """
                    INSERT INTO reviews (
                        review_id, asset_set_id, asset_set_version, status,
                        reviewer, comment, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), asset_set_id, version, to_status, actor, comment, now, now),
                )
        emit_asset_status_change(
            asset_set_id, "asset_set", from_status, to_status,
            version=version, actor=actor,
        )
        for asset_id in member_asset_ids:
            emit_asset_status_change(
                asset_id, "asset", from_status, to_status,
                version=version, asset_set_id=asset_set_id,
            )
        return self.get_asset_set(asset_set_id, version) or {}

    def deploy_asset_set(
        self,
        *,
        asset_set_id: str,
        version: str,
        environment: str,
        actor: str,
        projection_results: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Atomically activate a validated AssetSet version for one environment."""
        now = self._now()
        deployment_id = str(uuid.uuid4())
        deprecated_asset_ids: list[str] = []
        activated_asset_ids: list[str] = []
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM asset_set_versions WHERE asset_set_id = ? AND version = ?",
                (asset_set_id, version),
            ).fetchone()
            if row is None:
                raise KeyError(f"AssetSet version not found: {asset_set_id}@{version}")
            if row["status"] not in {"validated", "active"}:
                raise ValueError("Only a validated AssetSet version can be deployed")
            previous = connection.execute(
                "SELECT asset_set_version FROM active_asset_sets WHERE environment = ? AND asset_set_id = ?",
                (environment, asset_set_id),
            ).fetchone()
            previous_version = str(previous["asset_set_version"]) if previous else None
            projection_results = projection_results or self._projection_results(
                connection, asset_set_id, version
            )
            if previous_version and previous_version != version:
                connection.execute(
                    """
                    UPDATE asset_set_versions SET status = 'deprecated', updated_at = ?
                    WHERE asset_set_id = ? AND version = ?
                    """,
                    (now, asset_set_id, previous_version),
                )
                connection.execute(
                    """
                    UPDATE asset_versions SET status = 'deprecated', updated_at = ?
                    WHERE (asset_id, version) IN (
                        SELECT asset_id, asset_version FROM asset_set_members
                        WHERE asset_set_id = ? AND asset_set_version = ?
                    )
                    """,
                    (now, asset_set_id, previous_version),
                )
                deprecated_rows = connection.execute(
                    "SELECT asset_id FROM asset_set_members WHERE asset_set_id = ? AND asset_set_version = ?",
                    (asset_set_id, previous_version),
                ).fetchall()
                deprecated_asset_ids = [str(r["asset_id"]) for r in deprecated_rows]
            connection.execute(
                """
                UPDATE asset_set_versions SET status = 'active', updated_at = ?
                WHERE asset_set_id = ? AND version = ?
                """,
                (now, asset_set_id, version),
            )
            connection.execute(
                """
                UPDATE asset_versions SET status = 'active', updated_at = ?
                WHERE (asset_id, version) IN (
                    SELECT asset_id, asset_version FROM asset_set_members
                    WHERE asset_set_id = ? AND asset_set_version = ?
                )
                """,
                (now, asset_set_id, version),
            )
            activated_rows = connection.execute(
                "SELECT asset_id FROM asset_set_members WHERE asset_set_id = ? AND asset_set_version = ?",
                (asset_set_id, version),
            ).fetchall()
            activated_asset_ids = [str(r["asset_id"]) for r in activated_rows]
            connection.execute(
                """
                INSERT INTO active_asset_sets (
                    environment, asset_set_id, asset_set_version, deployment_id, activated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(environment, asset_set_id) DO UPDATE SET
                    asset_set_version = excluded.asset_set_version,
                    deployment_id = excluded.deployment_id,
                    activated_at = excluded.activated_at
                """,
                (environment, asset_set_id, version, deployment_id, now),
            )
            connection.execute(
                """
                INSERT INTO deployments (
                    deployment_id, asset_set_id, asset_set_version, environment,
                    status, previous_version, deployed_by, projection_results_json, created_at
                ) VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?)
                """,
                (
                    deployment_id,
                    asset_set_id,
                    version,
                    environment,
                    previous_version,
                    actor,
                    json.dumps(projection_results),
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO lifecycle_events (
                    event_id, subject_type, subject_id, subject_version,
                    from_status, to_status, actor, comment, created_at
                ) VALUES (?, 'asset_set', ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    asset_set_id,
                    version,
                    row["status"],
                    actor,
                    f"Deployed to {environment}",
                    now,
                ),
            )
        emit_asset_status_change(
            asset_set_id, "asset_set", row["status"], "active",
            version=version, environment=environment, actor=actor,
        )
        for aid in deprecated_asset_ids:
            emit_asset_status_change(
                aid, "asset", "active", "deprecated",
                version=previous_version, asset_set_id=asset_set_id,
            )
        for aid in activated_asset_ids:
            emit_asset_status_change(
                aid, "asset", "active", "active",
                version=version, asset_set_id=asset_set_id, environment=environment,
            )
        return self.get_deployment(deployment_id) or {}

    def rollback_asset_set(self, *, asset_set_id: str, environment: str, actor: str) -> dict[str, Any]:
        """Reactivate the previous deployed version of an AssetSet."""
        with self._connect() as connection:
            current = connection.execute(
                "SELECT asset_set_version FROM active_asset_sets WHERE environment = ? AND asset_set_id = ?",
                (environment, asset_set_id),
            ).fetchone()
            if current is None:
                raise KeyError(f"No active deployment for {asset_set_id} in {environment}")
            previous = connection.execute(
                """
                SELECT previous_version FROM deployments
                WHERE asset_set_id = ? AND environment = ? AND asset_set_version = ?
                  AND previous_version IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
                """,
                (asset_set_id, environment, current["asset_set_version"]),
            ).fetchone()
            if previous is None:
                raise ValueError("No previous AssetSet version is available for rollback")
            connection.execute(
                """
                UPDATE asset_set_versions SET status = 'validated'
                WHERE asset_set_id = ? AND version = ?
                """,
                (asset_set_id, previous["previous_version"]),
            )
        return self.deploy_asset_set(
            asset_set_id=asset_set_id,
            version=str(previous["previous_version"]),
            environment=environment,
            actor=actor,
        )

    def list_asset_sets(
        self,
        *,
        environment: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List AssetSet versions with membership and active deployment metadata."""
        where = []
        params: list[Any] = []
        if status and status != "all":
            where.append("v.status = ?")
            params.append(status)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT s.*, v.version, v.status, v.git_commit, v.checksum,
                       v.metadata_json, v.created_at AS version_created_at,
                       a.environment AS active_environment
                FROM asset_sets s
                JOIN asset_set_versions v ON v.asset_set_id = s.asset_set_id
                LEFT JOIN active_asset_sets a
                  ON a.asset_set_id = v.asset_set_id
                 AND a.asset_set_version = v.version
                 AND (? IS NULL OR a.environment = ?)
                {clause}
                ORDER BY s.domain_id, s.module_id, s.asset_set_id, v.version DESC
                """,
                [environment, environment, *params],
            ).fetchall()
        return [self._asset_set_row(row) for row in rows]

    def get_asset_set(self, asset_set_id: str, version: str) -> dict[str, Any] | None:
        """Return one AssetSet version with members, reviews, deployments, and history."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT s.*, v.version, v.status, v.git_commit, v.checksum,
                       v.metadata_json, v.created_at AS version_created_at,
                       NULL AS active_environment
                FROM asset_sets s
                JOIN asset_set_versions v ON v.asset_set_id = s.asset_set_id
                WHERE s.asset_set_id = ? AND v.version = ?
                """,
                (asset_set_id, version),
            ).fetchone()
            if row is None:
                return None
            members = connection.execute(
                """
                SELECT m.asset_id, m.asset_version, v.asset_type, v.name, v.status,
                       v.domain_id, v.module_id, v.tags_json, v.stores_json, v.payload_json
                FROM asset_set_members m
                JOIN asset_versions v ON v.asset_id = m.asset_id AND v.version = m.asset_version
                WHERE m.asset_set_id = ? AND m.asset_set_version = ?
                ORDER BY v.asset_type, m.asset_id
                """,
                (asset_set_id, version),
            ).fetchall()
            reviews = connection.execute(
                """
                SELECT * FROM reviews WHERE asset_set_id = ? AND asset_set_version = ?
                ORDER BY created_at DESC
                """,
                (asset_set_id, version),
            ).fetchall()
            deployments = connection.execute(
                """
                SELECT * FROM deployments WHERE asset_set_id = ? AND asset_set_version = ?
                ORDER BY created_at DESC
                """,
                (asset_set_id, version),
            ).fetchall()
            events = connection.execute(
                """
                SELECT * FROM lifecycle_events
                WHERE subject_type = 'asset_set' AND subject_id = ? AND subject_version = ?
                ORDER BY created_at DESC
                """,
                (asset_set_id, version),
            ).fetchall()
        result = self._asset_set_row(row)
        result["members"] = [
            {
                "asset_id": item["asset_id"],
                "version": item["asset_version"],
                "asset_type": item["asset_type"],
                "name": item["name"],
                "status": item["status"],
                "domain_id": item["domain_id"],
                "module_id": item["module_id"],
                "tags": json.loads(item["tags_json"] or "[]"),
                "stores": json.loads(item["stores_json"] or "[]"),
                "payload": json.loads(item["payload_json"]),
            }
            for item in members
        ]
        result["reviews"] = [dict(item) for item in reviews]
        result["deployments"] = [
            {**dict(item), "projection_results": json.loads(item["projection_results_json"] or "{}")}
            for item in deployments
        ]
        result["lifecycle_events"] = [dict(item) for item in events]
        return result

    def list_catalog_assets(
        self,
        *,
        environment: str = "dev",
        query: str | None = None,
        asset_type: str | None = None,
        knowledge_base: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        active_only: bool = False,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Return versioned catalog assets decorated with AssetSet and deployment data."""
        where = []
        params: list[Any] = []
        if query:
            where.append("(v.asset_id LIKE ? OR v.name LIKE ? OR v.payload_json LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like, like])
        if asset_type:
            where.append("v.asset_type = ?")
            params.append(asset_type)
        if knowledge_base:
            where.append("v.stores_json LIKE ?")
            params.append(f'%"{knowledge_base}"%')
        if status and status != "all":
            where.append("v.status = ?")
            params.append(status)
        if tag:
            where.append("v.tags_json LIKE ?")
            params.append(f'%"{tag}"%')
        if active_only:
            where.append("active.asset_set_id IS NOT NULL")
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT v.*, m.asset_set_id, m.asset_set_version,
                       active.environment AS active_environment
                FROM asset_versions v
                LEFT JOIN asset_set_members m
                  ON m.asset_id = v.asset_id AND m.asset_version = v.version
                LEFT JOIN active_asset_sets active
                  ON active.asset_set_id = m.asset_set_id
                 AND active.asset_set_version = m.asset_set_version
                 AND active.environment = ?
                {clause}
                ORDER BY v.asset_type, v.name, v.asset_id
                LIMIT ?
                """,
                [environment, *params, limit],
            ).fetchall()
        return [
            {
                "asset_id": row["asset_id"],
                "version": row["version"],
                "asset_type": row["asset_type"],
                "name": row["name"],
                "status": row["status"],
                "domain_id": row["domain_id"],
                "module_id": row["module_id"],
                "tags": json.loads(row["tags_json"] or "[]"),
                "stores": json.loads(row["stores_json"] or "[]"),
                "payload": json.loads(row["payload_json"]),
                "asset_set_id": row["asset_set_id"],
                "asset_set_version": row["asset_set_version"],
                "active": row["active_environment"] is not None,
                "active_environment": row["active_environment"],
            }
            for row in rows
        ]

    def get_catalog_asset(self, asset_id: str, version: str | None = None) -> dict[str, Any] | None:
        """Return one catalog asset version with relationships and AssetSet context."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT v.*, m.asset_set_id, m.asset_set_version, active.environment AS active_environment
                FROM asset_versions v
                LEFT JOIN asset_set_members m
                  ON m.asset_id = v.asset_id AND m.asset_version = v.version
                LEFT JOIN active_asset_sets active
                  ON active.asset_set_id = m.asset_set_id AND active.asset_set_version = m.asset_set_version
                WHERE v.asset_id = ? AND (? IS NULL OR v.version = ?)
                ORDER BY
                  CASE WHEN active.environment IS NOT NULL THEN 0 ELSE 1 END,
                  v.updated_at DESC
                LIMIT 1
                """,
                (asset_id, version, version),
            ).fetchone()
            if row is None:
                return None
            relations = connection.execute(
                """
                SELECT relation_type, target_asset_id, metadata_json
                FROM relationships WHERE source_asset_id = ?
                ORDER BY relation_type, target_asset_id
                """,
                (asset_id,),
            ).fetchall()
        return {
            "asset_id": row["asset_id"],
            "version": row["version"],
            "asset_type": row["asset_type"],
            "name": row["name"],
            "status": row["status"],
            "domain_id": row["domain_id"],
            "module_id": row["module_id"],
            "tags": json.loads(row["tags_json"] or "[]"),
            "stores": json.loads(row["stores_json"] or "[]"),
            "payload": json.loads(row["payload_json"]),
            "checksum": row["checksum"],
            "asset_set_id": row["asset_set_id"],
            "asset_set_version": row["asset_set_version"],
            "relationships": [
                {
                    "type": item["relation_type"],
                    "target_asset_id": item["target_asset_id"],
                    "metadata": json.loads(item["metadata_json"] or "{}"),
                }
                for item in relations
            ],
        }

    def get_deployment(self, deployment_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM deployments WHERE deployment_id = ?",
                (deployment_id,),
            ).fetchone()
        if row is None:
            return None
        return {**dict(row), "projection_results": json.loads(row["projection_results_json"] or "{}")}

    def list_active_assets(self, *, environment: str = "dev", asset_type: str | None = None) -> list[dict[str, Any]]:
        """Return exact asset versions belonging to active AssetSets."""
        return self.list_catalog_assets(
            environment=environment,
            asset_type=asset_type,
            active_only=True,
            status="all",
            limit=10_000,
        )

    def list_assets(
        self,
        *,
        asset_type: str | None = None,
        knowledge_base: str | None = None,
        owner_kb: str | None = None,
        query: str | None = None,
        relation_type: str | None = None,
        structural_layer: str | None = None,
        business_layer: str | None = None,
        status: str = "approved",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List catalog assets with optional KB, type, status, and text filtering."""
        where = []
        params: list[Any] = []
        join = ""
        if asset_type:
            where.append("asset_type = ?")
            params.append(asset_type)
        if knowledge_base:
            where.append("(primary_kb = ? OR stores_json LIKE ?)")
            params.extend([knowledge_base, f"%\"{knowledge_base}\"%"])
        if owner_kb:
            where.append("primary_kb = ?")
            params.append(owner_kb)
        if relation_type:
            join = "JOIN relationships r ON r.source_asset_id = assets.asset_id"
            where.append("r.relation_type = ?")
            params.append(relation_type)
        layer_filter = structural_layer or business_layer
        if layer_filter:
            where.append("(structural_layer = ? OR business_layer = ?)")
            params.extend([layer_filter, layer_filter])
        if status != "all":
            where.append("status = ?")
            params.append(status)
        if query:
            where.append(
                "(asset_id LIKE ? OR name LIKE ? OR payload_json LIKE ? OR canonical_name LIKE ? OR aliases_json LIKE ?)"
            )
            like = f"%{query}%"
            params.extend([like, like, like, like, like])
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT
                    assets.asset_id, assets.asset_type, assets.name, assets.version, assets.status,
                    assets.primary_kb, assets.stores_json, assets.payload_json, assets.updated_at,
                    assets.canonical_name, assets.normalized_name, assets.aliases_json,
                    assets.structural_layer, assets.business_layer
                FROM assets
                {join}
                {clause}
                ORDER BY assets.asset_type, assets.asset_id
                LIMIT ?
                """,
                [*params, limit],
            ).fetchall()
        return [self._row_to_asset(row) for row in rows]

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        """Return one catalog asset by global id."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT asset_id, asset_type, name, version, status, primary_kb, stores_json, payload_json,
                       updated_at, canonical_name, normalized_name, aliases_json
                FROM assets
                WHERE asset_id = ?
                """,
                (asset_id,),
            ).fetchone()
        return self._row_to_asset(row) if row else None

    def children(self, asset_id: str) -> list[dict[str, Any]]:
        """Return outbound relationships with target asset summaries when present."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT r.relation_type, r.target_asset_id, r.metadata_json,
                       a.asset_type, a.name, a.status, a.primary_kb, a.stores_json
                FROM relationships r
                LEFT JOIN assets a ON a.asset_id = r.target_asset_id
                WHERE r.source_asset_id = ?
                ORDER BY r.relation_type, r.target_asset_id
                """,
                (asset_id,),
            ).fetchall()
        return [
            {
                "relation_type": row["relation_type"],
                "target_asset_id": row["target_asset_id"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "target": self._resolve_relationship_target(
                    row["target_asset_id"],
                    asset_type=row["asset_type"] or self._asset_type_from_asset_id(row["target_asset_id"]),
                    name=row["name"],
                    status=row["status"],
                    primary_kb=row["primary_kb"],
                    stores_json=row["stores_json"],
                ),
            }
            for row in rows
        ]

    def find_referencers(
        self,
        target_asset_id: str,
        relation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find all assets that reference the given target asset (inbound relationships).

        Returns a list of dicts with keys: source_asset_id, relation_type, target_asset_id, metadata_json
        """
        with self._connect() as connection:
            if relation_type is not None:
                rows = connection.execute(
                    """
                    SELECT source_asset_id, relation_type, target_asset_id, metadata_json
                    FROM relationships
                    WHERE target_asset_id = ? AND relation_type = ?
                    ORDER BY source_asset_id, relation_type
                    """,
                    (target_asset_id, relation_type),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT source_asset_id, relation_type, target_asset_id, metadata_json
                    FROM relationships
                    WHERE target_asset_id = ?
                    ORDER BY source_asset_id, relation_type
                    """,
                    (target_asset_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def _resolve_relationship_target(
        self,
        target_asset_id: str,
        *,
        asset_type: str | None,
        name: str | None,
        status: str | None,
        primary_kb: str | None,
        stores_json: str | None,
    ) -> dict[str, Any]:
        """Resolve a relationship target using exact ids first, then catalog aliases and payload hints."""
        target = self.resolve_asset_reference(target_asset_id, asset_type=asset_type)
        if target:
            return {
                "asset_id": target.get("asset_id"),
                "asset_type": target.get("asset_type"),
                "name": target.get("name"),
                "status": target.get("status"),
                "primary_kb": target.get("primary_kb"),
                "stores": target.get("stores") or [],
            }
        return {
            "asset_id": target_asset_id,
            "asset_type": asset_type,
            "name": name,
            "status": status,
            "primary_kb": primary_kb,
            "stores": json.loads(stores_json) if stores_json else [],
        }

    def resolve_asset_reference(self, reference: str, *, asset_type: str | None = None) -> dict[str, Any] | None:
        """Return the best matching asset for a reference id, alias, or payload hint."""
        candidate = str(reference or "").strip()
        if not candidate:
            return None
        exact = self.get_asset(candidate)
        if exact:
            return exact
        suffix = candidate.split(".", 1)[1] if "." in candidate else candidate
        normalized_suffix = self._normalized_name(suffix)
        normalized_exact = self._normalized_name(candidate)
        terms = [term for term in [candidate, suffix, normalized_suffix, normalized_exact] if term]
        if not terms:
            return None
        like_clauses = []
        params: list[Any] = []
        for term in terms:
            like_clauses.append(
                "(asset_id = ? OR asset_id LIKE ? OR name = ? OR canonical_name = ? OR normalized_name = ? OR aliases_json LIKE ? OR payload_json LIKE ?)"
            )
            params.extend([term, f"%{term}%", term, term, term, f"%{term}%", f"%{term}%"])
        clause = " OR ".join(like_clauses)
        type_clause = "asset_type = ?" if asset_type else "1=1"
        if asset_type:
            params = [asset_type, *params]
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT asset_id, asset_type, name, version, status, primary_kb, stores_json, payload_json,
                       updated_at, canonical_name, normalized_name, aliases_json
                FROM assets
                WHERE {type_clause} AND ({clause})
                """,
                params,
            ).fetchall()
        if not rows:
            return None

        def score(row: sqlite3.Row) -> tuple[int, str]:
            asset_id = str(row["asset_id"] or "")
            canonical_name = str(row["canonical_name"] or "")
            normalized_name = str(row["normalized_name"] or "")
            name = str(row["name"] or "")
            payload_json = str(row["payload_json"] or "")
            score = 0
            if asset_id == candidate:
                score = 100
            elif asset_id == suffix or asset_id.endswith(f".{suffix}"):
                score = 95
            elif canonical_name == candidate or canonical_name == suffix:
                score = 90
            elif normalized_name == normalized_suffix:
                score = 85
            elif name.casefold() == suffix.casefold() or name.casefold() == candidate.casefold():
                score = 80
            elif suffix in payload_json or normalized_suffix in payload_json:
                score = 70
            return score, asset_id

        row = sorted(rows, key=score, reverse=True)[0]
        return self._row_to_asset(row)

    def totals(self) -> dict[str, int]:
        """Return asset counts by type from the catalog database."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT asset_type, COUNT(*) AS count FROM assets GROUP BY asset_type ORDER BY asset_type"
            ).fetchall()
        return {row["asset_type"]: row["count"] for row in rows}

    def clear_unmanaged_assets(self) -> None:
        """Remove ingestion-managed assets while preserving versioned AssetSet deployments."""
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM relationships
                WHERE source_asset_id NOT IN (SELECT DISTINCT asset_id FROM asset_set_members)
                """
            )
            connection.execute(
                """
                DELETE FROM assets
                WHERE asset_id NOT IN (SELECT DISTINCT asset_id FROM asset_set_members)
                """
            )
            connection.execute(
                """
                DELETE FROM asset_versions
                WHERE (asset_id, version) NOT IN (
                    SELECT asset_id, asset_version FROM asset_set_members
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _asset_set_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "asset_set_id": row["asset_set_id"],
            "name": row["name"],
            "version": row["version"],
            "status": row["status"],
            "domain_id": row["domain_id"],
            "module_id": row["module_id"],
            "asset_type": row["asset_type"],
            "description": row["description"],
            "git_commit": row["git_commit"],
            "checksum": row["checksum"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "created_at": row["version_created_at"],
            "active_environment": row["active_environment"],
        }

    @staticmethod
    def _projection_results(
        connection: sqlite3.Connection,
        asset_set_id: str,
        version: str,
    ) -> dict[str, Any]:
        rows = connection.execute(
            """
            SELECT v.stores_json
            FROM asset_set_members m
            JOIN asset_versions v ON v.asset_id = m.asset_id AND v.version = m.asset_version
            WHERE m.asset_set_id = ? AND m.asset_set_version = ?
            """,
            (asset_set_id, version),
        ).fetchall()
        stores = sorted({store for row in rows for store in json.loads(row["stores_json"] or "[]")})
        prev_deploy = connection.execute(
            """
            SELECT projection_results_json FROM deployments
            WHERE asset_set_id = ? AND asset_set_version = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (asset_set_id, version),
        ).fetchone()
        prev_results = json.loads(prev_deploy["projection_results_json"] or "{}") if prev_deploy else {}
        results: dict[str, Any] = {}
        for store in stores:
            prev = prev_results.get(store, {})
            status = prev.get("status", "scheduled")
            count = prev.get("asset_count", len(rows))
            results[store] = {"status": status, "asset_count": count}
        return results

    @staticmethod
    def _upsert_asset_version(
        connection: sqlite3.Connection,
        asset: EnterpriseAsset,
        stores: list[str],
    ) -> None:
        payload = asset.model_dump(mode="json")
        domain_id = str(asset.payload.get("domain_id") or asset.payload.get("domainId") or "") or None
        module_id = str(asset.payload.get("module_id") or asset.payload.get("moduleId") or "") or None
        checksum = str(asset.payload.get("checksum") or "") or None
        connection.execute(
            """
            INSERT INTO asset_versions (
                asset_id, version, asset_type, name, status, domain_id, module_id,
                tags_json, stores_json, payload_json, checksum, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(asset_id, version) DO UPDATE SET
                asset_type = excluded.asset_type,
                name = excluded.name,
                status = excluded.status,
                domain_id = excluded.domain_id,
                module_id = excluded.module_id,
                tags_json = excluded.tags_json,
                stores_json = excluded.stores_json,
                payload_json = excluded.payload_json,
                checksum = excluded.checksum,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                asset.asset_id,
                asset.version,
                asset.asset_type,
                asset.name,
                asset.status,
                domain_id,
                module_id,
                json.dumps(asset.tags),
                json.dumps(stores),
                json.dumps(payload),
                checksum,
            ),
        )

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
        columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    @staticmethod
    def _primary_kb_for(stores: list[str]) -> str | None:
        for name in ["graph", "document", "vector", "repository", "relational"]:
            if name in stores:
                return name
        return stores[0] if stores else None

    @staticmethod
    def _row_to_asset(row: sqlite3.Row) -> dict[str, Any]:
        payload = json.loads(row["payload_json"])
        return {
            "asset_id": row["asset_id"],
            "asset_type": row["asset_type"],
            "name": row["name"],
            "version": row["version"],
            "status": row["status"],
            "primary_kb": row["primary_kb"],
            "stores": json.loads(row["stores_json"]),
            "updated_at": row["updated_at"],
            "canonical_name": row["canonical_name"] if "canonical_name" in row.keys() else None,
            "normalized_name": row["normalized_name"] if "normalized_name" in row.keys() else None,
            "aliases": json.loads(row["aliases_json"]) if "aliases_json" in row.keys() and row["aliases_json"] else [],
            "structural_layer": (
                row["structural_layer"]
                if "structural_layer" in row.keys() and row["structural_layer"]
                else (row["business_layer"] if "business_layer" in row.keys() else None)
            ),
            "business_layer": row["business_layer"] if "business_layer" in row.keys() else None,
            "payload": payload,
        }

    @staticmethod
    def _canonical_name_for(asset: EnterpriseAsset) -> str:
        payload = asset.payload if isinstance(asset.payload, dict) else {}
        return str(payload.get("canonical_name") or asset.name or asset.asset_id)

    @staticmethod
    def _aliases_for(asset: EnterpriseAsset) -> list[str]:
        payload = asset.payload if isinstance(asset.payload, dict) else {}
        raw_aliases = payload.get("aliases") or payload.get("concept_aliases") or payload.get("synonyms") or []
        if isinstance(raw_aliases, dict):
            flattened = []
            for values in raw_aliases.values():
                if isinstance(values, list):
                    flattened.extend(value for value in values if isinstance(value, str) and value.strip())
            raw_aliases = flattened
        values = []
        for value in raw_aliases:
            if not isinstance(value, str):
                continue
            text = " ".join(value.strip().split())
            if not text:
                continue
            normalized = text.casefold()
            if normalized in {"true", "false", "none", "null", "yes", "no", "n/a"}:
                continue
            if not any(char.isalpha() for char in text):
                continue
            values.append(text)
        seen: set[str] = set()
        deduped: list[str] = []
        for value in values:
            normalized = value.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(value)
        return deduped

    @staticmethod
    def _normalized_name(value: str) -> str:
        return " ".join(str(value).lower().replace("_", " ").split())

    @staticmethod
    def _asset_type_from_asset_id(asset_id: str) -> str | None:
        value = str(asset_id or "")
        if "." not in value:
            return None
        asset_type, _ = value.split(".", 1)
        return asset_type or None
