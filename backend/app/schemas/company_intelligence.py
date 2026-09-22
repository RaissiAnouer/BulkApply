"""Pydantic schemas for Company & Contact Intelligence."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CompanyContactData(BaseModel):
    full_name: str
    job_title: str
    category: str = "other"  # "hiring", "leadership", "other"
    department: str | None = None
    linkedin_url: str | None = None
    confidence: str = "MEDIUM"  # "HIGH", "MEDIUM", "LOW"
    evidence: str | None = None
    is_relevant: bool = True


class CompanyIntelligenceData(BaseModel):
    company_name: str
    website: str | None = None
    linkedin_url: str | None = None
    industry: str | None = None
    description: str | None = None
    headquarters: str | None = None
    company_size: str | None = None
    technologies: str | None = None
    confidence: str = "UNKNOWN"  # "HIGH", "MEDIUM", "LOW", "UNKNOWN"
    contacts: list[CompanyContactData] = []


class CompanyContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intelligence_id: int
    full_name: str
    job_title: str
    category: str  # "hiring", "leadership", "other"
    department: str | None = None
    linkedin_url: str | None = None
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    evidence: str | None = None
    is_relevant: bool
    created_at: datetime


class CompanyContactUpdate(BaseModel):
    is_relevant: bool


class CompanyIntelligenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    company_name: str
    website: str | None = None
    linkedin_url: str | None = None
    industry: str | None = None
    description: str | None = None
    headquarters: str | None = None
    company_size: str | None = None
    technologies: str | None = None
    confidence: str  # "HIGH", "MEDIUM", "LOW", "UNKNOWN"
    status: str  # "PENDING", "RESEARCHING", "COMPLETED", "FAILED"
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    contacts: list[CompanyContactResponse] = []
