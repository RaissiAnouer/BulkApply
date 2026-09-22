"""Pydantic schemas for CV management and parsed resume data."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ContactInfoSchema(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None


class WorkExperienceSchema(BaseModel):
    company: str | None = None
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class EducationSchema(BaseModel):
    institution: str | None = None
    degree: str | None = None
    graduation_year: str | None = None


class ParsedDataSchema(BaseModel):
    contact_info: ContactInfoSchema = ContactInfoSchema()
    skills: list[str] = []
    work_experience: list[WorkExperienceSchema] = []
    education: list[EducationSchema] = []


class ParsedDataUpdateRequest(BaseModel):
    contact_info: ContactInfoSchema | None = None
    skills: list[str] | None = None
    work_experience: list[WorkExperienceSchema] | None = None
    education: list[EducationSchema] | None = None


class CVResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    file_name: str
    file_type: str
    file_size: int
    parsed_data: ParsedDataSchema | None = None
    created_at: datetime
    updated_at: datetime
