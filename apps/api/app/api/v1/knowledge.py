import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db_session
from app.models.agent import Document, KnowledgeBase
from app.schemas.knowledge import (
    AddDocumentRequest,
    CreateKbRequest,
    DocumentResponse,
    KnowledgeBaseResponse,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/{business_id}", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    business_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[KnowledgeBase]:
    stmt = (
        select(KnowledgeBase)
        .where(KnowledgeBase.business_id == business_id)
        .options(selectinload(KnowledgeBase.documents))
        .order_by(KnowledgeBase.created_at)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post("/{business_id}", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    business_id: uuid.UUID,
    payload: CreateKbRequest,
    session: AsyncSession = Depends(get_db_session),
) -> KnowledgeBase:
    kb = KnowledgeBase(business_id=business_id, name=payload.name, description=payload.description)
    session.add(kb)
    await session.flush()
    await session.refresh(kb, ["documents"])
    return kb


@router.get("/{business_id}/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    business_id: uuid.UUID,
    kb_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> KnowledgeBase:
    return await _get_kb_or_404(session, business_id, kb_id)


@router.post("/{business_id}/{kb_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def add_document(
    business_id: uuid.UUID,
    kb_id: uuid.UUID,
    payload: AddDocumentRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Document:
    await _get_kb_or_404(session, business_id, kb_id)

    doc = Document(
        knowledge_base_id=kb_id,
        business_id=business_id,
        title=payload.title,
        content=payload.content,
        source_type=payload.source_type,
        source_url=payload.source_url,
        status="pending",
    )
    session.add(doc)
    await session.flush()
    await session.refresh(doc)
    return doc


@router.delete("/{business_id}/{kb_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    business_id: uuid.UUID,
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    doc = await session.get(Document, doc_id)
    if doc is None or doc.knowledge_base_id != kb_id or doc.business_id != business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await session.delete(doc)


async def _get_kb_or_404(
    session: AsyncSession, business_id: uuid.UUID, kb_id: uuid.UUID
) -> KnowledgeBase:
    stmt = (
        select(KnowledgeBase)
        .where(KnowledgeBase.id == kb_id, KnowledgeBase.business_id == business_id)
        .options(selectinload(KnowledgeBase.documents))
    )
    kb = (await session.execute(stmt)).scalar_one_or_none()
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb
