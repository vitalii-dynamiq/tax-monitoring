"""Tests for app.services.jurisdiction_service."""

from app.schemas.jurisdiction import JurisdictionCreate, JurisdictionStatus, JurisdictionType
from app.services import jurisdiction_service as svc
from tests.factories import create_jurisdiction, seed_nyc_hierarchy

# ─── get_all_jurisdictions ───────────────────────────────────────────


async def test_get_all_no_filters(db):
    await seed_nyc_hierarchy(db)
    result = await svc.get_all_jurisdictions(db)
    assert len(result) == 3
    # Ordered by path: US, US.NY, US.NY.NYC
    assert [j.code for j in result] == ["US", "US-NY", "US-NY-NYC"]


async def test_get_all_filter_by_country_code(db):
    await seed_nyc_hierarchy(db)
    await create_jurisdiction(
        db, code="GB", name="United Kingdom", jurisdiction_type="country",
        path="GB", country_code="GB", currency_code="GBP",
    )
    result = await svc.get_all_jurisdictions(db, country_code="GB")
    assert len(result) == 1
    assert result[0].code == "GB"


async def test_get_all_filter_by_type(db):
    await seed_nyc_hierarchy(db)
    result = await svc.get_all_jurisdictions(db, jurisdiction_type="state")
    assert len(result) == 1
    assert result[0].code == "US-NY"


async def test_get_all_filter_by_status(db):
    await seed_nyc_hierarchy(db)
    await create_jurisdiction(
        db, code="DE", name="Germany", jurisdiction_type="country",
        path="DE", country_code="DE", currency_code="EUR", status="inactive",
    )
    result = await svc.get_all_jurisdictions(db, status="inactive")
    assert len(result) == 1
    assert result[0].code == "DE"


async def test_get_all_filter_by_parent_code(db):
    await seed_nyc_hierarchy(db)
    result = await svc.get_all_jurisdictions(db, parent_code="US-NY")
    assert len(result) == 1
    assert result[0].code == "US-NY-NYC"


async def test_get_all_filter_by_parent_code_nonexistent(db):
    await seed_nyc_hierarchy(db)
    # Nonexistent parent_code -- parent lookup returns None so no parent_id filter applied
    result = await svc.get_all_jurisdictions(db, parent_code="NOPE")
    # When parent is not found, the parent_id filter is never added, so all rows return
    assert len(result) == 3


async def test_get_all_search(db):
    await seed_nyc_hierarchy(db)
    result = await svc.get_all_jurisdictions(db, search="york")
    assert len(result) == 2
    codes = {j.code for j in result}
    assert codes == {"US-NY", "US-NY-NYC"}


async def test_get_all_search_case_insensitive(db):
    await seed_nyc_hierarchy(db)
    result = await svc.get_all_jurisdictions(db, search="YORK")
    assert len(result) == 2


async def test_get_all_limit(db):
    await seed_nyc_hierarchy(db)
    result = await svc.get_all_jurisdictions(db, limit=2)
    assert len(result) == 2
    assert result[0].code == "US"
    assert result[1].code == "US-NY"


async def test_get_all_offset(db):
    await seed_nyc_hierarchy(db)
    result = await svc.get_all_jurisdictions(db, limit=100, offset=1)
    assert len(result) == 2
    assert result[0].code == "US-NY"
    assert result[1].code == "US-NY-NYC"


async def test_get_all_limit_and_offset(db):
    await seed_nyc_hierarchy(db)
    result = await svc.get_all_jurisdictions(db, limit=1, offset=1)
    assert len(result) == 1
    assert result[0].code == "US-NY"


# ─── get_jurisdiction_by_code ────────────────────────────────────────


async def test_get_by_code_found(db):
    data = await seed_nyc_hierarchy(db)
    j = await svc.get_jurisdiction_by_code(db, "US-NY")
    assert j is not None
    assert j.name == "New York"
    assert j.id == data["ny"].id


async def test_get_by_code_not_found(db):
    result = await svc.get_jurisdiction_by_code(db, "NOPE")
    assert result is None


# ─── get_jurisdiction_children ───────────────────────────────────────


async def test_get_children_with_children(db):
    await seed_nyc_hierarchy(db)
    children = await svc.get_jurisdiction_children(db, "US")
    assert len(children) == 1
    assert children[0].code == "US-NY"


async def test_get_children_multiple(db):
    us = await create_jurisdiction(
        db, code="US", name="United States", jurisdiction_type="country",
        path="US", country_code="US", currency_code="USD",
    )
    await create_jurisdiction(
        db, code="US-NY", name="New York", jurisdiction_type="state",
        path="US.NY", country_code="US", currency_code="USD", parent_id=us.id,
    )
    await create_jurisdiction(
        db, code="US-CA", name="California", jurisdiction_type="state",
        path="US.CA", country_code="US", currency_code="USD", parent_id=us.id,
    )
    await db.flush()
    children = await svc.get_jurisdiction_children(db, "US")
    assert len(children) == 2
    # Ordered by name
    assert [c.name for c in children] == ["California", "New York"]


async def test_get_children_no_children(db):
    await seed_nyc_hierarchy(db)
    children = await svc.get_jurisdiction_children(db, "US-NY-NYC")
    assert children == []


async def test_get_children_nonexistent_parent(db):
    children = await svc.get_jurisdiction_children(db, "NOPE")
    assert children == []


# ─── get_jurisdiction_ancestors ──────────────────────────────────────


async def test_get_ancestors_multi_level(db):
    await seed_nyc_hierarchy(db)
    ancestors = await svc.get_jurisdiction_ancestors(db, "US-NY-NYC")
    assert len(ancestors) == 2
    assert ancestors[0].code == "US"      # root first
    assert ancestors[1].code == "US-NY"   # direct parent second


async def test_get_ancestors_one_level(db):
    await seed_nyc_hierarchy(db)
    ancestors = await svc.get_jurisdiction_ancestors(db, "US-NY")
    assert len(ancestors) == 1
    assert ancestors[0].code == "US"


async def test_get_ancestors_root_no_ancestors(db):
    await seed_nyc_hierarchy(db)
    ancestors = await svc.get_jurisdiction_ancestors(db, "US")
    assert ancestors == []


async def test_get_ancestors_nonexistent_code(db):
    ancestors = await svc.get_jurisdiction_ancestors(db, "NOPE")
    assert ancestors == []


# ─── get_jurisdiction_with_ancestors ─────────────────────────────────


async def test_with_ancestors_full_chain(db):
    await seed_nyc_hierarchy(db)
    chain = await svc.get_jurisdiction_with_ancestors(db, "US-NY-NYC")
    assert len(chain) == 3
    assert chain[0].code == "US"
    assert chain[1].code == "US-NY"
    assert chain[2].code == "US-NY-NYC"


async def test_with_ancestors_root_only(db):
    await seed_nyc_hierarchy(db)
    chain = await svc.get_jurisdiction_with_ancestors(db, "US")
    assert len(chain) == 1
    assert chain[0].code == "US"


async def test_with_ancestors_nonexistent(db):
    chain = await svc.get_jurisdiction_with_ancestors(db, "NOPE")
    assert chain == []


# ─── create_jurisdiction ─────────────────────────────────────────────


async def test_create_simple(db):
    data = JurisdictionCreate(
        code="FR",
        name="France",
        jurisdiction_type=JurisdictionType.country,
        country_code="FR",
        currency_code="EUR",
    )
    j = await svc.create_jurisdiction(db, data)
    assert j.code == "FR"
    assert j.name == "France"
    assert j.path == "FR"
    assert j.parent_id is None
    assert j.status == "active"
    assert j.id is not None


async def test_create_with_parent_builds_path(db):
    us = await create_jurisdiction(
        db, code="US", name="United States", jurisdiction_type="country",
        path="US", country_code="US", currency_code="USD",
    )
    data = JurisdictionCreate(
        code="US-NY",
        name="New York",
        jurisdiction_type=JurisdictionType.state,
        parent_code="US",
        country_code="US",
        currency_code="USD",
    )
    ny = await svc.create_jurisdiction(db, data)
    assert ny.parent_id == us.id
    assert ny.path == "US.NY"


async def test_create_nested_path(db):
    await create_jurisdiction(
        db, code="US", name="United States", jurisdiction_type="country",
        path="US", country_code="US", currency_code="USD",
    )
    ny_data = JurisdictionCreate(
        code="US-NY",
        name="New York",
        jurisdiction_type=JurisdictionType.state,
        parent_code="US",
        country_code="US",
        currency_code="USD",
    )
    ny = await svc.create_jurisdiction(db, ny_data)

    nyc_data = JurisdictionCreate(
        code="US-NY-NYC",
        name="New York City",
        jurisdiction_type=JurisdictionType.city,
        parent_code="US-NY",
        country_code="US",
        currency_code="USD",
    )
    nyc = await svc.create_jurisdiction(db, nyc_data)
    assert nyc.path == "US.NY.NYC"
    assert nyc.parent_id == ny.id


async def test_create_with_optional_fields(db):
    data = JurisdictionCreate(
        code="JP",
        name="Japan",
        local_name="日本",
        jurisdiction_type=JurisdictionType.country,
        country_code="JP",
        currency_code="JPY",
        timezone="Asia/Tokyo",
        subdivision_code="JP-13",
        status=JurisdictionStatus.pending,
        metadata={"population": 125_000_000},
    )
    j = await svc.create_jurisdiction(db, data)
    assert j.local_name == "日本"
    assert j.timezone == "Asia/Tokyo"
    assert j.subdivision_code == "JP-13"
    assert j.status == "pending"
    assert j.metadata_ == {"population": 125_000_000}


# ─── create_jurisdictions_bulk ───────────────────────────────────────


async def test_create_bulk(db):
    us = await create_jurisdiction(
        db, code="US", name="United States", jurisdiction_type="country",
        path="US", country_code="US", currency_code="USD",
    )
    children = [
        JurisdictionCreate(
            code="US-NY",
            name="New York",
            jurisdiction_type=JurisdictionType.state,
            country_code="US",
            currency_code="USD",
        ),
        JurisdictionCreate(
            code="US-CA",
            name="California",
            jurisdiction_type=JurisdictionType.state,
            country_code="US",
            currency_code="USD",
        ),
    ]
    results = await svc.create_jurisdictions_bulk(db, "US", children)
    assert len(results) == 2
    assert results[0].code == "US-NY"
    assert results[0].parent_id == us.id
    assert results[0].path == "US.NY"
    assert results[1].code == "US-CA"
    assert results[1].parent_id == us.id
    assert results[1].path == "US.CA"


# ─── Search with LIKE wildcards escaped ──────────────────────────────


async def test_search_percent_in_name(db):
    """Ensure literal '%' in search term does not act as SQL wildcard."""
    await create_jurisdiction(
        db, code="X1", name="Tax 5% Rate", jurisdiction_type="country",
        path="X1", country_code="XX", currency_code="XXX",
    )
    await create_jurisdiction(
        db, code="X2", name="Tax 50 Rate", jurisdiction_type="country",
        path="X2", country_code="XX", currency_code="XXX",
    )
    result = await svc.get_all_jurisdictions(db, search="5%")
    assert len(result) == 1
    assert result[0].code == "X1"


async def test_search_underscore_in_name(db):
    """Ensure literal '_' in search term does not act as single-char wildcard."""
    await create_jurisdiction(
        db, code="A1", name="Tax_rate_special", jurisdiction_type="country",
        path="A1", country_code="AA", currency_code="AAA",
    )
    await create_jurisdiction(
        db, code="A2", name="Tax rate special", jurisdiction_type="country",
        path="A2", country_code="AA", currency_code="AAA",
    )
    # Searching for literal underscore should only match the one with underscores
    result = await svc.get_all_jurisdictions(db, search="x_r")
    assert len(result) == 1
    assert result[0].code == "A1"


async def test_search_no_match(db):
    await seed_nyc_hierarchy(db)
    result = await svc.get_all_jurisdictions(db, search="zzzzzzz")
    assert result == []


# ─── Combined filters ───────────────────────────────────────────────


async def test_combined_country_and_type(db):
    await seed_nyc_hierarchy(db)
    await create_jurisdiction(
        db, code="GB", name="United Kingdom", jurisdiction_type="country",
        path="GB", country_code="GB", currency_code="GBP",
    )
    result = await svc.get_all_jurisdictions(
        db, country_code="US", jurisdiction_type="city",
    )
    assert len(result) == 1
    assert result[0].code == "US-NY-NYC"


async def test_combined_search_and_country(db):
    await seed_nyc_hierarchy(db)
    await create_jurisdiction(
        db, code="GB", name="New Glasgow", jurisdiction_type="country",
        path="GB", country_code="GB", currency_code="GBP",
    )
    # "New" matches NY, NYC, and GB's New Glasgow -- but country_code=US filters GB out
    result = await svc.get_all_jurisdictions(db, search="New", country_code="US")
    assert len(result) == 2
    codes = {j.code for j in result}
    assert codes == {"US-NY", "US-NY-NYC"}
