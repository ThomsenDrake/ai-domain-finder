# AI Pair Programming Prompt: Company Domain Enrichment with SearXNG

## Problem Statement
Build a robust API service that takes a company name and address as input and returns the company's primary website/domain. This tool enriches IRS data by finding missing website URLs using a self-hosted search engine and AI analysis.

## Architecture Overview

### Core Components
- **SearXNG**: Self-hosted metasearch engine (Docker container)
- **OpenRouter.ai**: Free tier AI models (1000 requests/day)
- **FastAPI**: Main application API
- **Docker Compose**: Orchestrates all services

### Workflow Strategy
1. **Normalize company name** and prepare search queries
2. **Search via SearXNG** with multiple query variations
3. **AI analysis** of search results to identify primary domain
4. **Domain verification** and confidence scoring
5. **Structured response** with metadata

## Technical Requirements

### Input Format
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

### Expected Output Format
```json
{
  "primary_domain": "amd.com",
  "confidence_score": 0.92,
  "search_queries_used": [
    "Advanced Micro Devices Santa Clara official website",
    "AMD headquarters website",
    "Advanced Micro Devices Inc"
  ],
  "domains_considered": ["amd.com", "amd.net", "advancedmicrodevices.com"],
  "verification_status": "verified",
  "processing_time_ms": 1800,
  "metadata": {
    "company_name_normalized": "Advanced Micro Devices",
    "ai_model_used": "openai/gpt-3.5-turbo",
    "search_results_count": 15,
    "domain_status": "active"
  }
}
```

## Local Development Setup

### Environment Requirements
```bash
# requirements.txt for local development
fastapi==0.104.1
uvicorn==0.24.0
httpx==0.25.2
pydantic==2.5.0
python-dotenv==1.0.0
```

### Environment Variables
```bash
# .env file for local development
OPENROUTER_API_KEY=your_openrouter_api_key_here
SEARXNG_BASE_URL=https://searx.be  # Public instance for testing
```

### Local FastAPI Development Server
```python
# run_local.py - Start development server
import uvicorn
from main import app

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,  # Auto-reload on code changes
        log_level="debug"
    )

# Run with: python run_local.py
```

### Simple Testing Web Interface
```html
<!-- static/test.html - Simple form for manual testing -->
<!DOCTYPE html>
<html>
<head>
    <title>Domain Enrichment Tester</title>
</head>
<body>
    <h1>Company Domain Finder</h1>
    <form id="searchForm">
        <label>Company Name:</label><br>
        <input type="text" id="company" placeholder="Apple Inc" required><br><br>
        
        <label>City:</label><br>
        <input type="text" id="city" placeholder="Cupertino" required><br><br>
        
        <label>State:</label><br>
        <input type="text" id="state" placeholder="CA" required><br><br>
        
        <button type="submit">Find Domain</button>
    </form>
    
    <div id="results"></div>
    
    <script>
        document.getElementById('searchForm').onsubmit = async (e) => {
            e.preventDefault();
            const results = document.getElementById('results');
            results.innerHTML = 'Searching...';
            
            const response = await fetch('/enrich', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    company_name: document.getElementById('company').value,
                    address: {
                        city: document.getElementById('city').value,
                        state: document.getElementById('state').value
                    }
                })
            });
            
            const data = await response.json();
            results.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
        };
    </script>
</body>
</html>
```

## Docker Compose Setup (Phase 3 - After Local Testing Works)

### Full Stack Configuration
```yaml
version: '3.8'

services:
  # SearXNG Search Engine
  searxng:
    image: searxng/searxng:latest
    container_name: searxng
    ports:
      - "8080:8080"
    environment:
      - SEARXNG_BASE_URL=http://localhost:8080
    volumes:
      - ./searxng/settings.yml:/etc/searxng/settings.yml:ro
      - ./searxng/uwsgi.ini:/etc/searxng/uwsgi.ini:ro
    restart: unless-stopped

  # Redis for SearXNG caching (optional but recommended)
  redis:
    image: redis:alpine
    container_name: searxng-redis
    restart: unless-stopped

  # Main Application
  domain-enrichment-api:
    build: .
    container_name: domain-enrichment
    ports:
      - "8000:8000"
    environment:
      - SEARXNG_URL=http://searxng:8080
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    depends_on:
      - searxng
    restart: unless-stopped

networks:
  default:
    name: domain-enrichment-network
```

### SearXNG Configuration
```yaml
# searxng/settings.yml
use_default_settings: true

server:
  port: 8080
  bind_address: "0.0.0.0"
  secret_key: "your-secret-key-here"

search:
  safe_search: 0
  autocomplete: ""
  default_lang: "en"
  formats:
    - html
    - json

engines:
  - name: google
    engine: google
    use_mobile_ui: false
    
  - name: bing
    engine: bing
    
  - name: duckduckgo
    engine: duckduckgo
    
  - name: startpage
    engine: startpage

outgoing:
  request_timeout: 10.0
  max_request_timeout: 20.0
```

## Core Implementation

### Main Application Structure
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import asyncio
from typing import List, Dict, Optional
import json
import time

class CompanyRequest(BaseModel):
    company_name: str
    address: Dict[str, str]

class DomainResponse(BaseModel):
    primary_domain: Optional[str]
    confidence_score: float
    search_queries_used: List[str]
    domains_considered: List[str]
    verification_status: str
    processing_time_ms: int
    metadata: Dict

class DomainEnrichmentService:
    def __init__(self, searxng_url: str, openrouter_api_key: str):
        self.searxng_url = searxng_url
        self.openrouter_api_key = openrouter_api_key
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def process_company_request(self, request: CompanyRequest) -> DomainResponse:
        start_time = time.time()
        
        # Step 1: Generate search queries
        search_queries = self.generate_search_queries(request.company_name, request.address)
        
        # Step 2: Search via SearXNG
        all_search_results = []
        for query in search_queries:
            results = await self.search_with_searxng(query)
            all_search_results.extend(results)
        
        # Step 3: AI analysis of results
        domain_analysis = await self.analyze_results_with_ai(
            request.company_name, 
            request.address, 
            all_search_results
        )
        
        # Step 4: Verify domain if found
        if domain_analysis.get('primary_domain'):
            verification = await self.verify_domain(domain_analysis['primary_domain'])
        else:
            verification = "no_domain_found"
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return DomainResponse(
            primary_domain=domain_analysis.get('primary_domain'),
            confidence_score=domain_analysis.get('confidence_score', 0.0),
            search_queries_used=search_queries,
            domains_considered=domain_analysis.get('alternative_domains', []),
            verification_status=verification,
            processing_time_ms=processing_time,
            metadata={
                "company_name_normalized": self.normalize_company_name(request.company_name),
                "ai_model_used": "openai/gpt-3.5-turbo",
                "search_results_count": len(all_search_results),
                "domain_status": verification
            }
        )
```

### SearXNG Integration (Local Development)
```python
# For local development, use public SearXNG instances
# Popular public instances: searx.be, searx.org, searx.space

class SearXNGClient:
    def __init__(self, base_url: str = "https://searx.be"):
        self.base_url = base_url
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def search_with_searxng(self, query: str, limit: int = 10) -> List[Dict]:
        """Search using public SearXNG instance for local development"""
        try:
            params = {
                'q': query,
                'format': 'json',
                'engines': 'google,bing,duckduckgo',
                'language': 'en',
                'time_range': '',
                'safesearch': '0',
                'pageno': '1'
            }
            
            response = await self.http_client.get(
                f"{self.base_url}/search",
                params=params,
                headers={'User-Agent': 'Domain-Enrichment-Tool/1.0'}  # Be respectful
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('results', [])[:limit]
            else:
                print(f"SearXNG returned status {response.status_code}")
                return []
                
        except Exception as e:
            print(f"SearXNG search error: {e}")
            # Fallback to different public instance
            if "searx.be" in self.base_url:
                print("Trying fallback instance...")
                self.base_url = "https://searx.org"
                return await self.search_with_searxng(query, limit)
            return []
```

### Local Testing Setup
```python
# main.py - Simple script for local testing
import asyncio
from domain_enrichment import DomainEnrichmentService

async def test_company(company_name: str, city: str, state: str):
    """Quick test function for local development"""
    service = DomainEnrichmentService(
        searxng_url="https://searx.be",
        openrouter_api_key="your-api-key-here"
    )
    
    request = {
        "company_name": company_name,
        "address": {"city": city, "state": state}
    }
    
    result = await service.process_company_request(request)
    print(f"\nCompany: {company_name}")
    print(f"Domain: {result.primary_domain}")
    print(f"Confidence: {result.confidence_score}")
    print(f"Queries used: {result.search_queries_used}")
    
if __name__ == "__main__":
    # Test with real companies
    test_companies = [
        ("Apple Inc", "Cupertino", "CA"),
        ("Microsoft Corporation", "Redmond", "WA"),
        ("Tesla Inc", "Austin", "TX"),
        ("Small Local Business", "Denver", "CO")  # Should return null
    ]
    
    for company, city, state in test_companies:
        asyncio.run(test_company(company, city, state))
```

### Quick CLI for Manual Testing
```python
# cli.py - Interactive testing tool
import asyncio
import sys
from domain_enrichment import DomainEnrichmentService

async def main():
    if len(sys.argv) < 3:
        print("Usage: python cli.py 'Company Name' 'City, State'")
        sys.exit(1)
    
    company_name = sys.argv[1]
    location = sys.argv[2].split(", ")
    city = location[0] if len(location) > 0 else ""
    state = location[1] if len(location) > 1 else ""
    
    service = DomainEnrichmentService(
        searxng_url="https://searx.be",
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY")
    )
    
    print(f"Searching for domain of: {company_name} in {city}, {state}")
    print("-" * 50)
    
    result = await service.process_company_request({
        "company_name": company_name,
        "address": {"city": city, "state": state}
    })
    
    print(f"Primary Domain: {result.primary_domain}")
    print(f"Confidence: {result.confidence_score}")
    print(f"Processing Time: {result.processing_time_ms}ms")
    print(f"Verification: {result.verification_status}")
    
if __name__ == "__main__":
    asyncio.run(main())

# Usage examples:
# python cli.py "Apple Inc" "Cupertino, CA"
# python cli.py "Tesla" "Austin, TX"
```

def generate_search_queries(self, company_name: str, address: Dict) -> List[str]:
    """Generate multiple search query variations"""
    normalized_name = self.normalize_company_name(company_name)
    city = address.get('city', '')
    state = address.get('state', '')
    
    queries = [
        f'"{normalized_name}" official website',
        f'"{normalized_name}" {city} {state} website',
        f'"{normalized_name}" headquarters website',
        f'"{normalized_name}" corporate site',
        f'{normalized_name} {city} company website',
        f'"{company_name}" official domain'
    ]
    
    return list(set(queries))  # Remove duplicates

def normalize_company_name(self, name: str) -> str:
    """Clean up company name for better search results"""
    # Remove common suffixes
    suffixes = ['Inc', 'Corp', 'Corporation', 'LLC', 'Ltd', 'Limited', 'Co', 'Company']
    normalized = name
    
    for suffix in suffixes:
        if normalized.endswith(f' {suffix}'):
            normalized = normalized[:-len(suffix)-1]
            
    return normalized.strip()
```

### OpenRouter AI Integration
```python
async def analyze_results_with_ai(self, company_name: str, address: Dict, search_results: List[Dict]) -> Dict:
    """Use OpenRouter AI to analyze search results and identify primary domain"""
    
    # Prepare search results for AI analysis
    formatted_results = []
    for result in search_results[:15]:  # Limit to avoid token limits
        formatted_results.append({
            "title": result.get('title', ''),
            "url": result.get('url', ''),
            "content": result.get('content', '')[:200]  # Truncate content
        })
    
    prompt = f"""
Analyze these search results to find the PRIMARY business website domain for:

Company: {company_name}
Address: {address.get('city', '')}, {address.get('state', '')} {address.get('zip', '')}

Search Results:
{json.dumps(formatted_results, indent=2)}

Instructions:
1. Identify the most likely PRIMARY business domain (not social media, news articles, or subsidiaries)
2. Look for official corporate websites that match the company name and location
3. Avoid regional subsidiaries unless they're clearly the primary entity
4. Consider domain authority and relevance

Return ONLY a JSON object with this exact format:
{{
  "primary_domain": "example.com" or null,
  "confidence_score": 0.0-1.0,
  "reasoning": "Brief explanation of choice",
  "alternative_domains": ["other.com", "another.com"],
  "red_flags": ["any concerns about the selection"]
}}

Be conservative - if uncertain, return null for primary_domain.
"""

    try:
        response = await self.http_client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-3.5-turbo",  # Free tier model
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500
            }
        )
        
        if response.status_code == 200:
            ai_response = response.json()
            content = ai_response['choices'][0]['message']['content']
            
            # Parse JSON response
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # If AI didn't return valid JSON, extract what we can
                return {"primary_domain": None, "confidence_score": 0.0, "reasoning": "Failed to parse AI response"}
                
        else:
            return {"primary_domain": None, "confidence_score": 0.0, "reasoning": "AI API error"}
            
    except Exception as e:
        print(f"AI analysis error: {e}")
        return {"primary_domain": None, "confidence_score": 0.0, "reasoning": f"Error: {str(e)}"}
```

### Domain Verification
```python
async def verify_domain(self, domain: str) -> str:
    """Verify that domain is accessible and appears legitimate"""
    try:
        # Check if domain resolves and is accessible
        response = await self.http_client.head(f"https://{domain}", timeout=10.0)
        
        if response.status_code < 400:
            return "verified"
        else:
            return "inaccessible"
            
    except:
        try:
            # Try HTTP if HTTPS fails
            response = await self.http_client.head(f"http://{domain}", timeout=10.0)
            if response.status_code < 400:
                return "http_only"
            else:
                return "inaccessible"
        except:
            return "unreachable"
```

## Development Strategy: Local First, Then Docker

**IMPORTANT**: Build this for local testing FIRST before dockerizing anything. We want to iterate and test the core functionality without rebuilding containers every time.

### Phase 1: Local Development Setup
- [ ] Create a simple Python script that can run locally
- [ ] Use a public SearXNG instance for testing (searx.be or searx.org)
- [ ] Build FastAPI application that runs with `uvicorn main:app --reload`
- [ ] Integrate OpenRouter.ai API client with local testing
- [ ] Test the full search → AI analysis → domain verification flow
- [ ] Create a simple CLI or web interface for manual testing
- [ ] Validate with 5-10 real company examples

### Phase 2: Local Optimization
- [ ] Fine-tune search query generation with test companies
- [ ] Optimize AI prompts by testing different prompt variations
- [ ] Add comprehensive error handling and logging
- [ ] Implement confidence scoring based on test results
- [ ] Add simple file-based caching for development

### Phase 3: Docker Production Setup (Only After Local Works)
- [ ] Create Dockerfile for the FastAPI app
- [ ] Set up Docker Compose with self-hosted SearXNG
- [ ] Migrate from public SearXNG to private instance
- [ ] Add production monitoring and logging
- [ ] Implement rate limiting and queue management

## Error Handling

### SearXNG Failures
- Container not running: Return error with restart instructions
- No search results: Try alternative query formats
- Search timeout: Reduce query complexity and retry

### OpenRouter API Issues
- Rate limit exceeded: Queue requests and implement backoff
- API errors: Retry with exponential backoff
- JSON parsing failures: Extract domains from raw text response

### Domain Verification Failures
- Network timeout: Mark as "unverified" but still return domain
- DNS resolution issues: Check with multiple resolvers

## Success Metrics
- **Accuracy**: >85% correct primary domain identification
- **Coverage**: >75% of queries return a domain result
- **Performance**: <5 seconds average response time
- **Cost**: Stay within free tier limits (1000 OpenRouter requests/day)

## Testing Strategy (Local Development Focus)

### Manual Testing Checklist
Before dockerizing, validate these scenarios locally:

#### 1. Well-Known Companies (Should work reliably)
```python
test_cases_reliable = [
    ("Apple Inc", "Cupertino", "CA", "apple.com"),
    ("Microsoft Corporation", "Redmond", "WA", "microsoft.com"),
    ("Tesla Inc", "Austin", "TX", "tesla.com"),
    ("Amazon.com Inc", "Seattle", "WA", "amazon.com"),
    ("Google LLC", "Mountain View", "CA", "google.com")
]
```

#### 2. Ambiguous Company Names (Test AI disambiguation)
```python
test_cases_ambiguous = [
    ("ABB Ltd", "Zurich", "Switzerland", "abb.com"),  # Not random bank
    ("Ford Motor Company", "Dearborn", "MI", "ford.com"),  # Not Ford Foundation
    ("Delta", "Atlanta", "GA", "delta.com"),  # Airline not other Deltas
]
```

#### 3. Edge Cases
```python
test_cases_edge = [
    ("Fake Company LLC", "Nowhere", "XX", None),  # Should return null
    ("", "", "", None),  # Empty input handling
    ("A", "B", "C", None),  # Very short names
]
```

### Local Development Validation Steps

1. **Test SearXNG Connection**
   ```bash
   curl "https://searx.be/search?q=test&format=json"
   # Should return JSON results
   ```

2. **Test OpenRouter API**
   ```python
   # Simple API test
   import httpx
   response = httpx.post("https://openrouter.ai/api/v1/chat/completions", ...)
   print(response.status_code)  # Should be 200
   ```

3. **Run Progressive Tests**
   ```bash
   # Start simple
   python cli.py "Apple Inc" "Cupertino, CA"
   
   # Test edge cases  
   python cli.py "Fake Company" "Nowhere, XX"
   
   # Test ambiguous names
   python cli.py "ABB" "Zurich, Switzerland"
   ```

4. **Performance Testing**
   - Time each request (should be < 10 seconds locally)
   - Monitor OpenRouter usage (stay under daily limit)
   - Test error handling (disconnect internet, wrong API key, etc.)

### Debug Information to Include

Add extensive logging for local development:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

class DomainEnrichmentService:
    async def process_company_request(self, request):
        logging.info(f"Processing: {request.company_name}")
        
        # Log each step
        logging.debug(f"Generated queries: {search_queries}")
        logging.debug(f"SearXNG results count: {len(search_results)}")
        logging.debug(f"AI analysis result: {ai_analysis}")
        
        return result
```

### When to Move to Docker
Only dockerize when you can demonstrate:
- ✅ 90%+ accuracy on test cases
- ✅ Reliable SearXNG search results
- ✅ Proper AI analysis and domain extraction  
- ✅ Graceful error handling
- ✅ Reasonable performance (< 10 seconds per request)
- ✅ Staying within OpenRouter daily limits

Start by setting up the Docker Compose stack with SearXNG, then build the FastAPI application with OpenRouter integration for AI-powered domain analysis.