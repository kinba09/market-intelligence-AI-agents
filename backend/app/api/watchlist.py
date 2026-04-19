from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import Company, User, WatchlistCompany
from app.schemas.api import CompanyUpsertRequest, WatchlistResponse


router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.post("/companies", response_model=WatchlistResponse)
def upsert_watchlist_company(
    req: CompanyUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistResponse:
    company = None
    if req.domain:
        company = db.execute(
            select(Company).where(Company.domain == req.domain, Company.user_id == current_user.id)
        ).scalar_one_or_none()

    if not company:
        company = db.execute(
            select(Company).where(Company.name == req.name, Company.user_id == current_user.id)
        ).scalar_one_or_none()

    if not company:
        company = Company(
            user_id=current_user.id,
            name=req.name,
            domain=req.domain,
            industry=req.industry,
            headquarters=req.headquarters,
            watchlist_tier=req.watchlist_tier,
        )
        db.add(company)
        db.flush()
    else:
        company.watchlist_tier = req.watchlist_tier
        if req.industry:
            company.industry = req.industry
        if req.headquarters:
            company.headquarters = req.headquarters
        if req.domain and not company.domain:
            company.domain = req.domain

    wl = db.execute(
        select(WatchlistCompany).where(
            WatchlistCompany.company_id == company.id,
            WatchlistCompany.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if not wl:
        wl = WatchlistCompany(user_id=current_user.id, company_id=company.id)
        db.add(wl)

    db.commit()

    return WatchlistResponse(company_id=company.id, name=company.name, watchlist_tier=company.watchlist_tier)


@router.get("/companies", response_model=list[WatchlistResponse])
def list_watchlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WatchlistResponse]:
    rows = (
        db.execute(
            select(Company)
            .join(WatchlistCompany, WatchlistCompany.company_id == Company.id)
            .where(WatchlistCompany.user_id == current_user.id)
            .order_by(Company.watchlist_tier.desc(), Company.name.asc())
        )
        .scalars()
        .all()
    )
    return [WatchlistResponse(company_id=r.id, name=r.name, watchlist_tier=r.watchlist_tier) for r in rows]


@router.delete("/companies/{company_id}")
def remove_watchlist_company(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    wl = db.execute(
        select(WatchlistCompany).where(
            WatchlistCompany.company_id == company_id,
            WatchlistCompany.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if not wl:
        raise HTTPException(status_code=404, detail="Company not in watchlist")
    db.delete(wl)
    db.commit()
    return {"status": "removed", "company_id": company_id}
