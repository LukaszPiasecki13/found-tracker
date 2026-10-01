"""Pydantic schemas for asset classes."""

from pydantic import BaseModel, ConfigDict, Field


class AssetClassCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=20)


class AssetClassUpdateRequest(BaseModel):
    """Same body for PUT and PATCH: the name is the only field."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=20)


class AssetClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
