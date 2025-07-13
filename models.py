from pydantic import BaseModel
from typing import List, Dict, Optional
from enum import Enum

class CompanyAddress(BaseModel):
    street: Optional[str] = None
    city: str
    state: str
    zip: Optional[str] = None
    country: Optional[str] = "US"

class CompanyRequest(BaseModel):
    company_name: str
    address: CompanyAddress

class DomainResponse(BaseModel):
    primary_domain: Optional[str]
    confidence_score: float
    search_queries_used: List[str]
    domains_considered: List[str]
    verification_status: str
    processing_time_ms: int
    metadata: Dict

# New simplified models for CSV processing and simple API

class CompanyLookup(BaseModel):
    company_name: str
    location: Optional[str] = None  # Free-form location string like "Zurich, Switzerland"

class SimpleDomainResponse(BaseModel):
    primary_domain: Optional[str]
    confidence_score: float
    verification_status: str
    processing_time_ms: int

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class CSVUploadResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    total_rows: Optional[int] = None

class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int  # Number of rows processed
    total: int     # Total number of rows
    completed_at: Optional[str] = None
    download_url: Optional[str] = None
    errors: List[str] = []