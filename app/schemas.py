from typing import Literal

from pydantic import BaseModel, Field

EntryType = Literal["manual", "credential"]


class PasswordIn(BaseModel):
    password: str = Field(min_length=1)


class AuthStatus(BaseModel):
    initialized: bool
    authenticated: bool


class EntryIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = ""
    type: EntryType
    tags: list[str] = []


class LinkedEntryOut(BaseModel):
    id: int
    title: str
    type: EntryType


class EntryOut(BaseModel):
    id: int
    title: str
    body: str
    type: EntryType
    created_at: str
    updated_at: str
    tags: list[str]
    linked_entries: list[LinkedEntryOut]


class EntryListItem(BaseModel):
    id: int
    title: str
    type: EntryType
    created_at: str
    updated_at: str
    tags: list[str]
    snippet: str | None = None


class TagOut(BaseModel):
    id: int
    name: str
    count: int


class LinkIn(BaseModel):
    target_id: int


class SuggestionRequest(BaseModel):
    title: str = ""
    body: str = ""
    tags: list[str] = []
    exclude_id: int | None = None


class SuggestionItem(BaseModel):
    id: int
    title: str
    type: EntryType
    matched_tags: list[str]
    matched_keywords: list[str]
    score: float


class BulkEntryItem(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = ""
    tags: list[str] = []


class BulkImportRequest(BaseModel):
    type: EntryType
    items: list[BulkEntryItem] = Field(min_length=1, max_length=200)


class BulkImportResult(BaseModel):
    created_count: int
    ids: list[int]
