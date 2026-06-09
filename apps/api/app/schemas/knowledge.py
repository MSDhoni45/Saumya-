import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    title: str
    source_type: str
    source_url: str | None
    content: str
    status: str
    created_at: datetime


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    name: str
    description: str | None
    documents: list[DocumentResponse] = []
    created_at: datetime
    updated_at: datetime


class CreateKbRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class AddDocumentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    source_type: str = "text"
    source_url: str | None = None
