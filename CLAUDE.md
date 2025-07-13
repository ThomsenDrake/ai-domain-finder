# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a company domain enrichment API service that takes company names and addresses as input and returns primary website domains. The service uses SearXNG for web search and OpenRouter.ai for AI-powered analysis of search results.

### Core Architecture
- **FastAPI**: Main application framework
- **SearXNG**: Self-hosted metasearch engine (Docker) or public instances for development
- **OpenRouter.ai**: AI models for analyzing search results (free tier: 1000 requests/day)
- **httpx**: Async HTTP client for external API calls

### Workflow
1. Normalize company name and generate search query variations
2. Search via SearXNG with multiple query formats
3. AI analysis of search results to identify primary domain
4. Domain verification and confidence scoring
5. Return structured response with metadata

## Development Commands

### Local Development
```bash
# Install dependencies
pip install fastapi==0.104.1 uvicorn==0.24.0 httpx==0.25.2 pydantic==2.5.0 python-dotenv==1.0.0

# Run development server with auto-reload
python run_local.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

# CLI testing
python cli.py "Apple Inc" "Cupertino, CA"
python cli.py "Tesla" "Austin, TX"

# Simple testing script
python main.py  # Runs predefined test cases
```

### Docker Commands (Production)
```bash
# Copy environment file and configure
cp .env.docker .env
# Edit .env and add your OpenRouter API key

# Build and run full stack
docker-compose up --build

# Or run in background
docker-compose up --build -d

# Check SearXNG API
curl "http://localhost:8080/search?q=test&format=json"

# Check API health
curl "http://localhost:8000/health"
```

See [DOCKER.md](DOCKER.md) for complete deployment guide.

## Environment Configuration

### Required Environment Variables
```bash
OPENROUTER_API_KEY=your_openrouter_api_key_here
SEARXNG_BASE_URL=https://searx.be  # Public instance for local dev
# or 
SEARXNG_URL=http://searxng:8080    # Docker container

# AI Model Configuration (optional)
AI_MODEL=moonshotai/kimi-k2        # Default: moonshotai/kimi-k2
```

### AI Model Options
- **moonshotai/kimi-k2** (default) - Best for reasoning, 66K context, superior disambiguation
- **openai/gpt-3.5-turbo** - Fast and cost-effective
- **openai/gpt-4** - Higher accuracy, slower and more expensive
- **anthropic/claude-3-haiku** - Fast Claude model
- **anthropic/claude-3-sonnet** - Balanced Claude model

See [OpenRouter.ai](https://openrouter.ai/models) for full model list and pricing.

### Development vs Production
- **Local Development**: Uses public SearXNG instances (searx.be, searx.org)
- **Production**: Self-hosted SearXNG via Docker Compose

## Key Implementation Details

### Search Query Generation
The service generates multiple search query variations:
- `"{normalized_name}" official website`
- `"{normalized_name}" {city} {state} website`
- `"{normalized_name}" headquarters website`
- Company name normalization removes common suffixes (Inc, Corp, LLC, etc.)

### AI Analysis Pipeline
- Formats search results for AI consumption (processes up to 25 results with detailed content)
- Uses OpenRouter.ai with moonshotai/kimi-k2 for superior reasoning and larger context
- Returns structured JSON with domain, confidence score, and reasoning
- Conservative approach: returns null if uncertain

### Domain Verification
- Tests both HTTPS and HTTP accessibility
- Returns verification status: "verified", "http_only", "inaccessible", "unreachable"

## Development Strategy

**CRITICAL**: Build locally first, then dockerize. The project emphasizes local development and testing before container deployment.

### Phase 1: Local Development
1. Test with public SearXNG instances
2. Validate core search → AI analysis → verification flow
3. Use simple CLI and web interface for manual testing
4. Achieve 90%+ accuracy on test cases

### Phase 2: Docker Production
1. Set up self-hosted SearXNG
2. Add production monitoring and rate limiting
3. Deploy full stack via Docker Compose

## Testing Approach

### Test Case Categories
- **Well-known companies**: Apple, Microsoft, Tesla (should work reliably)
- **Ambiguous names**: ABB, Ford, Delta (test AI disambiguation)
- **Edge cases**: Fake companies, empty inputs (should return null)

### Success Metrics
- Accuracy: >85% correct domain identification
- Coverage: >75% of queries return a domain
- Performance: <5 seconds average response time
- Stay within OpenRouter free tier limits

## File Structure Notes

Currently contains only `prompt.md` which serves as the comprehensive project specification. The actual implementation files should be created following the patterns and structure outlined in the prompt document.

## API Endpoints

### 1. Simple Lookup: POST /lookup
**Purpose**: Quick domain lookup with minimal input requirements
**Input Format:**
```json
{
  "company_name": "Apple Inc",
  "location": "Cupertino, CA"  // optional
}
```

**Output Format (4 key metrics):**
```json
{
  "primary_domain": "apple.com",
  "confidence_score": 0.95,
  "verification_status": "verified",
  "processing_time_ms": 23056
}
```

### 2. CSV Batch Processing: POST /upload-csv
**Purpose**: Process multiple companies from uploaded CSV file
**Input**: Multipart form with CSV file
**Process**: 
1. Upload CSV file
2. Get job ID and monitor with GET /status/{job_id}
3. Download results with GET /download/{job_id}

**CSV Format**: Auto-detects company name and location columns
```csv
company_name,location
Apple Inc,Cupertino CA
Microsoft Corporation,Redmond WA
```

### 3. Detailed Analysis: POST /enrich
**Purpose**: Full detailed analysis with complete metadata
**Input Format:**
```json
{
  "company_name": "Advanced Micro Devices Inc",
  "address": {
    "street": "2485 Augustine Drive",
    "city": "Santa Clara", 
    "state": "CA",
    "zip": "95054",
    "country": "US"
  }
}
```

**Output Format:**
```json
{
  "primary_domain": "amd.com",
  "confidence_score": 0.92,
  "search_queries_used": ["..."],
  "domains_considered": ["amd.com", "amd.net"],
  "verification_status": "verified",
  "processing_time_ms": 1800,
  "metadata": {...}
}
```

### 4. Job Management
- **GET /status/{job_id}**: Check CSV processing progress
- **GET /download/{job_id}**: Download enriched CSV results

## Web Interfaces

### 1. Simple Lookup (/static/lookup.html)
- Single company domain lookup
- Returns 4 key metrics in clean format
- Optional location field
- Example companies for testing

### 2. CSV Batch Processing (/static/upload.html)
- Drag-and-drop CSV file upload
- Auto-detects company and location columns
- Real-time progress monitoring
- Download enriched results
- Supports flexible CSV formats

### 3. Advanced Analysis (/test)
- Detailed domain analysis
- Full search query information
- AI reasoning and alternative domains
- Complete metadata and timing

## Error Handling Patterns

- SearXNG failures: Fallback to alternative public instances
- OpenRouter API issues: Exponential backoff retry logic
- Domain verification failures: Mark as "unverified" but still return domain
- JSON parsing failures: Extract domains from raw text response