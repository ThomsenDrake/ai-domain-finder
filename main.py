import os
import logging
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from dotenv import load_dotenv
from models import (
    CompanyRequest, DomainResponse, CompanyLookup, SimpleDomainResponse,
    CSVUploadResponse, JobStatusResponse, JobStatus
)
from domain_enrichment import DomainEnrichmentService
from csv_processor import CSVProcessor
from job_manager import JobManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Domain Enrichment API",
    description="Find company primary domains using search and AI analysis",
    version="1.0.0"
)

# Initialize service
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
searxng_url = os.getenv("SEARXNG_BASE_URL", "https://searx.be")
ai_model = os.getenv("AI_MODEL", "moonshotai/kimi-k2")

if not openrouter_api_key:
    logger.warning("OPENROUTER_API_KEY not found in environment variables")

service = DomainEnrichmentService(searxng_url, openrouter_api_key, ai_model)
csv_processor = CSVProcessor(service)
job_manager = JobManager(csv_processor)

@app.on_event("startup")
async def startup_event():
    logger.info("Domain Enrichment API starting up")
    logger.info(f"Using SearXNG URL: {searxng_url}")
    logger.info(f"Using AI Model: {ai_model}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Domain Enrichment API")
    await service.close()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Domain Enrichment API is running",
        "version": "1.0.0",
        "endpoints": {
            "enrich": "POST /enrich - Detailed company domain analysis",
            "lookup": "POST /lookup - Simple company domain lookup",
            "upload-csv": "POST /upload-csv - Batch process CSV file",
            "test": "GET /test - Web interface"
        }
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "searxng_url": searxng_url,
        "openrouter_configured": bool(openrouter_api_key)
    }

@app.post("/enrich", response_model=DomainResponse)
async def enrich_company_domain(request: CompanyRequest):
    """
    Find the primary domain for a company based on name and address
    """
    try:
        logger.info(f"Received request for company: {request.company_name}")
        
        if not openrouter_api_key:
            raise HTTPException(
                status_code=500, 
                detail="OpenRouter API key not configured"
            )
        
        result = await service.process_company_request(request)
        
        logger.info(f"Completed request for {request.company_name}: {result.primary_domain}")
        return result
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/lookup", response_model=SimpleDomainResponse)
async def lookup_company_domain(request: CompanyLookup):
    """
    Simple company domain lookup with just company name and optional location
    Returns the 4 key metrics: domain, confidence, verification, processing time
    """
    try:
        logger.info(f"Lookup request for: {request.company_name}")
        
        if not openrouter_api_key:
            raise HTTPException(
                status_code=500, 
                detail="OpenRouter API key not configured"
            )
        
        # Process with CSV processor (handles location parsing)
        result = await csv_processor.process_single_row(
            request.company_name, 
            request.location
        )
        
        logger.info(f"Lookup completed for {request.company_name}: {result.primary_domain}")
        return result
        
    except Exception as e:
        logger.error(f"Error in lookup request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-csv", response_model=CSVUploadResponse)
async def upload_csv_file(file: UploadFile = File(...)):
    """
    Upload a CSV file for batch domain enrichment processing
    """
    try:
        logger.info(f"CSV upload: {file.filename}")
        
        if not openrouter_api_key:
            raise HTTPException(
                status_code=500, 
                detail="OpenRouter API key not configured"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Validate CSV
        is_valid, message, df = csv_processor.validate_csv(file_content)
        
        if not is_valid:
            return CSVUploadResponse(
                job_id="",
                status=JobStatus.FAILED,
                message=message
            )
        
        # Detect columns
        detected_columns = csv_processor.detect_columns(df)
        
        # Create job
        job_id = job_manager.create_job(df, detected_columns)
        
        # Start processing in background
        job_manager.start_job_processing(job_id)
        
        return CSVUploadResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            message=f"CSV uploaded successfully. Processing {len(df)} companies.",
            total_rows=len(df)
        )
        
    except Exception as e:
        logger.error(f"Error uploading CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a CSV processing job
    """
    try:
        status = job_manager.get_job_status(job_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{job_id}")
async def download_csv_results(job_id: str):
    """
    Download the processed CSV file with enrichment results
    """
    try:
        # Check job status
        status = job_manager.get_job_status(job_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if status.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=400, 
                detail=f"Job is not completed. Current status: {status.status}"
            )
        
        # Get CSV content
        csv_content = job_manager.get_result_csv(job_id)
        
        if not csv_content:
            raise HTTPException(status_code=404, detail="Results not found")
        
        # Return CSV file
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=enriched_companies_{job_id}.csv"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test")
async def get_test_page():
    """Serve the test HTML page"""
    return FileResponse("static/test.html")

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    logger.warning("Static directory not found, test interface may not work")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)