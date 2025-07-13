#!/usr/bin/env python3
"""
CLI tool for testing the domain enrichment service
Usage: python cli.py "Company Name" "City, State"
"""

import asyncio
import sys
import os
import logging
from dotenv import load_dotenv
from models import CompanyRequest, CompanyAddress
from domain_enrichment import DomainEnrichmentService

# Load environment variables
load_dotenv()

def setup_logging(debug=False):
    """Configure logging for CLI"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

async def test_company(company_name: str, city: str, state: str, debug: bool = False):
    """Test a single company"""
    
    # Get configuration
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    searxng_url = os.getenv("SEARXNG_BASE_URL", "https://searx.be")
    
    if not openrouter_api_key:
        print("❌ Error: OPENROUTER_API_KEY not found in environment")
        print("Please copy .env.example to .env and add your API key")
        return
    
    # Initialize service
    service = DomainEnrichmentService(searxng_url, openrouter_api_key)
    
    try:
        # Create request
        request = CompanyRequest(
            company_name=company_name,
            address=CompanyAddress(
                city=city,
                state=state
            )
        )
        
        print(f"🔍 Searching for domain of: {company_name} in {city}, {state}")
        print("─" * 60)
        
        # Process request
        result = await service.process_company_request(request)
        
        # Display results
        print(f"🌐 Primary Domain: {result.primary_domain or 'Not found'}")
        print(f"📊 Confidence Score: {result.confidence_score:.2f}")
        print(f"✅ Verification Status: {result.verification_status}")
        print(f"⏱️  Processing Time: {result.processing_time_ms}ms")
        
        if debug:
            print(f"\n🔍 Search Queries Used:")
            for i, query in enumerate(result.search_queries_used, 1):
                print(f"  {i}. {query}")
            
            if result.domains_considered:
                print(f"\n🌐 Alternative Domains Considered:")
                for domain in result.domains_considered:
                    print(f"  • {domain}")
            
            if result.metadata.get('reasoning'):
                print(f"\n💭 AI Reasoning: {result.metadata['reasoning']}")
            
            print(f"\n📈 Metadata:")
            print(f"  • Normalized Name: {result.metadata['company_name_normalized']}")
            print(f"  • Search Results: {result.metadata['search_results_count']}")
            print(f"  • AI Model: {result.metadata['ai_model_used']}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        if debug:
            import traceback
            traceback.print_exc()
    
    finally:
        await service.close()

def print_usage():
    """Print usage instructions"""
    print("Domain Enrichment CLI Tool")
    print("=" * 50)
    print("Usage:")
    print('  python cli.py "Company Name" "City, State"')
    print('  python cli.py "Company Name" "City, State" --debug')
    print("")
    print("Examples:")
    print('  python cli.py "Apple Inc" "Cupertino, CA"')
    print('  python cli.py "Tesla" "Austin, TX"')
    print('  python cli.py "Microsoft Corporation" "Redmond, WA" --debug')
    print("")
    print("Options:")
    print("  --debug    Enable verbose debugging output")

async def run_test_suite():
    """Run a suite of test cases"""
    test_cases = [
        ("Apple Inc", "Cupertino", "CA"),
        ("Microsoft Corporation", "Redmond", "WA"),
        ("Tesla Inc", "Austin", "TX"),
        ("Fake Company LLC", "Nowhere", "XX"),  # Should return null
    ]
    
    print("🧪 Running test suite...")
    print("=" * 60)
    
    for i, (company, city, state) in enumerate(test_cases, 1):
        print(f"\nTest {i}/{ len(test_cases)}:")
        await test_company(company, city, state)
        
        if i < len(test_cases):
            print("\n" + "─" * 60)

async def main():
    """Main CLI entry point"""
    args = sys.argv[1:]
    debug = False
    
    # Check for debug flag
    if "--debug" in args:
        debug = True
        args.remove("--debug")
    
    if "--help" in args or "-h" in args:
        print_usage()
        return
    
    # Setup logging
    setup_logging(debug)
    
    if len(args) == 0:
        # Run test suite if no arguments
        await run_test_suite()
        return
    
    if len(args) < 2:
        print("❌ Error: Missing required arguments")
        print_usage()
        return
    
    company_name = args[0]
    location_parts = args[1].split(", ")
    
    if len(location_parts) < 2:
        print("❌ Error: Location must be in format 'City, State'")
        print('Example: "Cupertino, CA"')
        return
    
    city = location_parts[0].strip()
    state = location_parts[1].strip()
    
    await test_company(company_name, city, state, debug)

if __name__ == "__main__":
    asyncio.run(main())