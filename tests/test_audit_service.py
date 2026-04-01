"""
Tests for the audit service.
"""

from app.services.audit_service import get_audit_log, log_change


class TestLogChange:
    async def test_creates_entry(self, db):
        entry = await log_change(
            db,
            entity_type="tax_rate",
            entity_id=1,
            action="create",
            changed_by="test_user",
            change_source="api",
            new_values={"rate_value": 0.05},
        )
        assert entry.id is not None
        assert entry.entity_type == "tax_rate"
        assert entry.entity_id == 1
        assert entry.action == "create"
        assert entry.changed_by == "test_user"
        assert entry.change_source == "api"
        assert entry.new_values == {"rate_value": 0.05}

    async def test_with_old_values_and_reason(self, db):
        entry = await log_change(
            db,
            entity_type="tax_rate",
            entity_id=42,
            action="update",
            changed_by="admin",
            change_source="api",
            old_values={"status": "draft"},
            new_values={"status": "active"},
            change_reason="Approved after review",
        )
        assert entry.old_values == {"status": "draft"}
        assert entry.change_reason == "Approved after review"


class TestGetAuditLog:
    async def test_empty_log(self, db):
        entries = await get_audit_log(db)
        assert entries == []

    async def test_filter_by_entity_type(self, db):
        await log_change(
            db, entity_type="tax_rate", entity_id=1,
            action="create", changed_by="sys", change_source="api",
        )
        await log_change(
            db, entity_type="jurisdiction", entity_id=2,
            action="create", changed_by="sys", change_source="api",
        )
        await db.flush()

        entries = await get_audit_log(db, entity_type="tax_rate")
        assert len(entries) == 1
        assert entries[0].entity_type == "tax_rate"

    async def test_filter_by_entity_id(self, db):
        await log_change(
            db, entity_type="tax_rate", entity_id=10,
            action="create", changed_by="sys", change_source="api",
        )
        await log_change(
            db, entity_type="tax_rate", entity_id=20,
            action="create", changed_by="sys", change_source="api",
        )
        await db.flush()

        entries = await get_audit_log(db, entity_type="tax_rate", entity_id=10)
        assert len(entries) == 1
        assert entries[0].entity_id == 10

    async def test_pagination(self, db):
        for i in range(5):
            await log_change(
                db, entity_type="tax_rate", entity_id=i,
                action="create", changed_by="sys", change_source="api",
            )
        await db.flush()

        page1 = await get_audit_log(db, limit=2, offset=0)
        page2 = await get_audit_log(db, limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2

        all_entries = await get_audit_log(db, limit=10)
        assert len(all_entries) == 5
