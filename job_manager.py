import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional
from models import JobStatus, JobStatusResponse, SimpleDomainResponse
from csv_processor import CSVProcessor
import pandas as pd

logger = logging.getLogger(__name__)

class JobManager:
    def __init__(self, csv_processor: CSVProcessor):
        self.csv_processor = csv_processor
        self.jobs: Dict[str, Dict] = {}
        self.results_cache: Dict[str, str] = {}  # job_id -> CSV content
        
    def create_job(self, df: pd.DataFrame, detected_columns: Dict[str, Optional[str]]) -> str:
        """Create a new processing job and return job ID"""
        job_id = str(uuid.uuid4())
        
        self.jobs[job_id] = {
            'id': job_id,
            'status': JobStatus.PENDING,
            'progress': 0,
            'total': len(df),
            'created_at': datetime.now(),
            'completed_at': None,
            'dataframe': df,
            'detected_columns': detected_columns,
            'results': [],
            'errors': []
        }
        
        logger.info(f"Created job {job_id} with {len(df)} rows to process")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[JobStatusResponse]:
        """Get current status of a job"""
        if job_id not in self.jobs:
            return None
        
        job = self.jobs[job_id]
        
        return JobStatusResponse(
            job_id=job_id,
            status=job['status'],
            progress=job['progress'],
            total=job['total'],
            completed_at=job['completed_at'].isoformat() if job['completed_at'] else None,
            download_url=f"/download/{job_id}" if job['status'] == JobStatus.COMPLETED else None,
            errors=job['errors']
        )
    
    async def process_job(self, job_id: str):
        """Process a job in the background"""
        if job_id not in self.jobs:
            logger.error(f"Job {job_id} not found")
            return
        
        job = self.jobs[job_id]
        
        try:
            job['status'] = JobStatus.PROCESSING
            logger.info(f"Starting processing job {job_id}")
            
            df = job['dataframe']
            detected_cols = job['detected_columns']
            company_col = detected_cols['company_name']
            location_col = detected_cols['location']
            
            results = []
            
            for index, row in df.iterrows():
                try:
                    # Extract company name
                    company_name = str(row[company_col]).strip()
                    if pd.isna(row[company_col]) or not company_name:
                        # Skip empty company names
                        results.append(SimpleDomainResponse(
                            primary_domain=None,
                            confidence_score=0.0,
                            verification_status="empty_input",
                            processing_time_ms=0
                        ))
                        job['progress'] += 1
                        continue
                    
                    # Extract location
                    location = self.csv_processor.prepare_location_string(row, location_col, df) if location_col else None
                    
                    logger.debug(f"Processing row {index + 1}: {company_name}, {location}")
                    
                    # Process the company
                    result = await self.csv_processor.process_single_row(company_name, location)
                    results.append(result)
                    
                    job['progress'] += 1
                    job['results'] = results
                    
                    logger.info(f"Job {job_id}: Processed {job['progress']}/{job['total']} - {company_name} -> {result.primary_domain}")
                    
                except Exception as e:
                    error_msg = f"Error processing row {index + 1}: {str(e)}"
                    logger.error(error_msg)
                    job['errors'].append(error_msg)
                    
                    # Add error result
                    results.append(SimpleDomainResponse(
                        primary_domain=None,
                        confidence_score=0.0,
                        verification_status="processing_error",
                        processing_time_ms=0
                    ))
                    
                    job['progress'] += 1
                    job['results'] = results
            
            # Generate output CSV
            output_csv = self.csv_processor.prepare_output_csv(df, results)
            self.results_cache[job_id] = output_csv
            
            # Mark as completed
            job['status'] = JobStatus.COMPLETED
            job['completed_at'] = datetime.now()
            
            logger.info(f"Job {job_id} completed successfully. Processed {len(results)} rows.")
            
        except Exception as e:
            error_msg = f"Job {job_id} failed: {str(e)}"
            logger.error(error_msg)
            job['status'] = JobStatus.FAILED
            job['errors'].append(error_msg)
    
    def get_result_csv(self, job_id: str) -> Optional[str]:
        """Get the result CSV content for a completed job"""
        if job_id not in self.jobs:
            return None
        
        job = self.jobs[job_id]
        if job['status'] != JobStatus.COMPLETED:
            return None
        
        return self.results_cache.get(job_id)
    
    def start_job_processing(self, job_id: str):
        """Start processing a job in the background"""
        # Create background task
        asyncio.create_task(self.process_job(job_id))
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Clean up old jobs and their cached results"""
        current_time = datetime.now()
        to_remove = []
        
        for job_id, job in self.jobs.items():
            age_hours = (current_time - job['created_at']).total_seconds() / 3600
            if age_hours > max_age_hours:
                to_remove.append(job_id)
        
        for job_id in to_remove:
            del self.jobs[job_id]
            if job_id in self.results_cache:
                del self.results_cache[job_id]
            logger.info(f"Cleaned up old job {job_id}")
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old jobs")