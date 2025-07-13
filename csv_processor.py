import pandas as pd
import logging
from typing import List, Dict, Optional, Tuple
from io import StringIO, BytesIO
from models import CompanyLookup, SimpleDomainResponse, CompanyAddress, CompanyRequest
from domain_enrichment import DomainEnrichmentService

logger = logging.getLogger(__name__)

class CSVProcessor:
    def __init__(self, domain_service: DomainEnrichmentService):
        self.domain_service = domain_service
    
    def detect_columns(self, df: pd.DataFrame) -> Dict[str, Optional[str]]:
        """
        Automatically detect which columns contain company names and locations
        Returns a dict with 'company_name' and 'location' keys
        """
        columns = df.columns.str.lower()
        
        # Company name column detection
        company_name_col = None
        company_name_patterns = [
            'company', 'company_name', 'name', 'business_name', 
            'organization', 'org', 'firm', 'entity'
        ]
        
        for pattern in company_name_patterns:
            matches = [col for col in df.columns if pattern in col.lower()]
            if matches:
                company_name_col = matches[0]
                break
        
        # If no pattern match, try first non-empty string column
        if not company_name_col:
            for col in df.columns:
                if df[col].dtype == 'object' and not df[col].isna().all():
                    company_name_col = col
                    break
        
        # Location column detection (optional)
        location_col = None
        location_patterns = [
            'location', 'address', 'city', 'state', 'country', 
            'headquarters', 'hq', 'region', 'place'
        ]
        
        for pattern in location_patterns:
            matches = [col for col in df.columns if pattern in col.lower()]
            if matches:
                location_col = matches[0]
                break
        
        # Alternative: combine city/state columns if available
        if not location_col:
            city_cols = [col for col in df.columns if 'city' in col.lower()]
            state_cols = [col for col in df.columns if any(s in col.lower() for s in ['state', 'province', 'region'])]
            
            if city_cols and state_cols:
                location_col = 'combined_location'  # Special flag to combine columns
        
        logger.info(f"Detected columns - Company: {company_name_col}, Location: {location_col}")
        
        return {
            'company_name': company_name_col,
            'location': location_col
        }
    
    def prepare_location_string(self, row: pd.Series, location_col: str, df: pd.DataFrame) -> Optional[str]:
        """
        Create a location string from the row data
        """
        if location_col == 'combined_location':
            # Combine city and state columns
            city_cols = [col for col in df.columns if 'city' in col.lower()]
            state_cols = [col for col in df.columns if any(s in col.lower() for s in ['state', 'province', 'region'])]
            
            parts = []
            if city_cols and not pd.isna(row[city_cols[0]]):
                parts.append(str(row[city_cols[0]]).strip())
            if state_cols and not pd.isna(row[state_cols[0]]):
                parts.append(str(row[state_cols[0]]).strip())
            
            return ', '.join(parts) if parts else None
        
        elif location_col and not pd.isna(row[location_col]):
            return str(row[location_col]).strip()
        
        return None
    
    def parse_location(self, location_str: Optional[str]) -> CompanyAddress:
        """
        Parse a free-form location string into CompanyAddress components
        """
        if not location_str:
            # Default address for companies without location
            return CompanyAddress(city="Unknown", state="Unknown")
        
        # Simple parsing logic - can be enhanced later
        parts = [part.strip() for part in location_str.split(',')]
        
        if len(parts) >= 2:
            city = parts[0]
            state = parts[1]
            country = parts[2] if len(parts) > 2 else "US"
        elif len(parts) == 1:
            # Assume it's a city or state
            city = parts[0]
            state = "Unknown"
            country = "US"
        else:
            city = "Unknown"
            state = "Unknown" 
            country = "US"
        
        return CompanyAddress(
            city=city,
            state=state,
            country=country
        )
    
    async def process_single_row(self, company_name: str, location: Optional[str]) -> SimpleDomainResponse:
        """
        Process a single company lookup and return simplified response
        """
        try:
            # Parse location into address components
            address = self.parse_location(location)
            
            # Create full request object
            request = CompanyRequest(
                company_name=company_name,
                address=address
            )
            
            # Process with domain enrichment service
            full_response = await self.domain_service.process_company_request(request)
            
            # Convert to simplified response
            return SimpleDomainResponse(
                primary_domain=full_response.primary_domain,
                confidence_score=full_response.confidence_score,
                verification_status=full_response.verification_status,
                processing_time_ms=full_response.processing_time_ms
            )
            
        except Exception as e:
            logger.error(f"Error processing company {company_name}: {str(e)}")
            return SimpleDomainResponse(
                primary_domain=None,
                confidence_score=0.0,
                verification_status="error",
                processing_time_ms=0
            )
    
    def validate_csv(self, file_content: bytes) -> Tuple[bool, str, Optional[pd.DataFrame]]:
        """
        Validate uploaded CSV file and return validation results
        """
        try:
            # Try reading as CSV
            df = pd.read_csv(BytesIO(file_content))
            
            if df.empty:
                return False, "CSV file is empty", None
            
            if len(df.columns) == 0:
                return False, "CSV file has no columns", None
            
            # Check if we can detect required columns
            detected_cols = self.detect_columns(df)
            
            if not detected_cols['company_name']:
                return False, "Could not detect company name column. Please ensure your CSV has a column with company names.", None
            
            # Check for actual data
            company_col = detected_cols['company_name']
            non_empty_companies = df[company_col].dropna()
            
            if len(non_empty_companies) == 0:
                return False, f"No valid company names found in column '{company_col}'", None
            
            logger.info(f"CSV validation passed: {len(df)} rows, company column: {company_col}")
            return True, f"Valid CSV with {len(df)} rows detected", df
            
        except pd.errors.EmptyDataError:
            return False, "CSV file is empty or invalid", None
        except pd.errors.ParserError as e:
            return False, f"Error parsing CSV file: {str(e)}", None
        except Exception as e:
            return False, f"Error reading CSV file: {str(e)}", None
    
    def prepare_output_csv(self, original_df: pd.DataFrame, results: List[SimpleDomainResponse]) -> str:
        """
        Combine original CSV with enrichment results and return as CSV string
        """
        # Create a copy of the original dataframe
        output_df = original_df.copy()
        
        # Add result columns
        output_df['primary_domain'] = [r.primary_domain for r in results]
        output_df['confidence_score'] = [r.confidence_score for r in results]
        output_df['verification_status'] = [r.verification_status for r in results]
        output_df['processing_time_ms'] = [r.processing_time_ms for r in results]
        
        # Convert to CSV string
        return output_df.to_csv(index=False)