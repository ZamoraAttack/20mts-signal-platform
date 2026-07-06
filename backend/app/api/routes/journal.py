from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import select

from ...database import AsyncSessionLocal
from ...models import JournalEntry
from ..schemas import JournalEntryCreate, JournalEntryRead

router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.get("", response_model=list[JournalEntryRead])
async def list_journal_entries(session_id: str | None = None, signal_id: str | None = None):
    async with AsyncSessionLocal() as db:
        stmt = select(JournalEntry).order_by(JournalEntry.entry_time.desc())
        if session_id:
            stmt = stmt.where(JournalEntry.session_id == session_id)
        if signal_id:
            stmt = stmt.where(JournalEntry.signal_id == signal_id)
        result = await db.execute(stmt)
        return result.scalars().all()


@router.post("", response_model=JournalEntryRead, status_code=201)
async def create_journal_entry(payload: JournalEntryCreate):
    entry = JournalEntry(
        session_id=payload.session_id,
        signal_id=payload.signal_id,
        entry_type=payload.entry_type,
        body=payload.body,
        entry_time=datetime.now(timezone.utc),
    )
    async with AsyncSessionLocal() as db:
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
    return entry
