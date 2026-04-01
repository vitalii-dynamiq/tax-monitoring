from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import require_admin
from app.db.session import get_db
from app.models.jurisdiction import Jurisdiction
from app.models.tax_rule import TaxRule
from app.schemas.tax_rule import TaxRuleCreate, TaxRuleResponse
from app.services.jurisdiction_service import get_jurisdiction_by_code

router = APIRouter(prefix="/v1/rules", tags=["Tax Rules"])


def _rule_to_response(rule: TaxRule) -> TaxRuleResponse:
    resp = TaxRuleResponse.model_validate(rule)
    if rule.jurisdiction:
        resp.jurisdiction_code = rule.jurisdiction.code
    return resp


@router.get("", response_model=list[TaxRuleResponse])
async def list_rules(
    jurisdiction_code: str | None = None,
    rule_type: str | None = None,
    status: str | None = None,
    tax_rate_id: int | None = None,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(TaxRule).options(selectinload(TaxRule.jurisdiction))

    if jurisdiction_code:
        query = query.join(TaxRule.jurisdiction).where(Jurisdiction.code == jurisdiction_code)
    if rule_type:
        query = query.where(TaxRule.rule_type == rule_type)
    if status:
        query = query.where(TaxRule.status == status)
    if tax_rate_id:
        query = query.where(TaxRule.tax_rate_id == tax_rate_id)

    query = query.order_by(TaxRule.priority.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    rules = list(result.unique().scalars().all())
    return [_rule_to_response(r) for r in rules]


@router.get("/{rule_id}", response_model=TaxRuleResponse)
async def get_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TaxRule).options(selectinload(TaxRule.jurisdiction)).where(TaxRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")
    return _rule_to_response(rule)


@router.post("", response_model=TaxRuleResponse, status_code=201)
async def create_rule(data: TaxRuleCreate, _admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    jurisdiction = await get_jurisdiction_by_code(db, data.jurisdiction_code)
    if not jurisdiction:
        raise HTTPException(404, f"Jurisdiction not found: {data.jurisdiction_code}")

    rule = TaxRule(
        tax_rate_id=data.tax_rate_id,
        jurisdiction_id=jurisdiction.id,
        rule_type=data.rule_type,
        priority=data.priority,
        name=data.name,
        description=data.description,
        conditions=data.conditions,
        action=data.action,
        effective_start=data.effective_start,
        effective_end=data.effective_end,
        enacted_date=data.enacted_date,
        legal_reference=data.legal_reference,
        legal_uri=data.legal_uri,
        authority_name=data.authority_name,
        status=data.status,
        created_by=data.created_by,
    )
    db.add(rule)
    await db.flush()
    return _rule_to_response(rule)
