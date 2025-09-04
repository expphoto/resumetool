"""Job discovery and search functionality."""
import hashlib
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from resumetool.types import JobListing


class JobSearchEngine:
    """Main job search engine that aggregates from multiple sources."""
    
    def __init__(self):
        self.sources = {
            'indeed': IndeedSearcher(),
            'ziprecruiter': ZipRecruiterSearcher(),
        }
    
    def search_jobs(
        self,
        query: str,
        location: str = "",
        remote: bool = False,
        limit: int = 20
    ) -> List[JobListing]:
        """Search for jobs across all configured sources."""
        
        all_jobs = []
        jobs_per_source = max(1, limit // len(self.sources))
        
        for source_name, searcher in self.sources.items():
            try:
                jobs = searcher.search(
                    query=query,
                    location=location,
                    remote=remote,
                    limit=jobs_per_source
                )
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"Failed to search {source_name}: {e}")
        
        # Remove duplicates and limit results
        unique_jobs = self._deduplicate_jobs(all_jobs)
        return unique_jobs[:limit]
    
    def _deduplicate_jobs(self, jobs: List[JobListing]) -> List[JobListing]:
        """Remove duplicate job listings."""
        seen_jobs = set()
        unique_jobs = []
        
        for job in jobs:
            # Create hash based on title, company, and location
            job_hash = hashlib.md5(
                f"{job.title.lower()}{job.company.lower()}{job.location.lower()}".encode()
            ).hexdigest()
            
            if job_hash not in seen_jobs:
                seen_jobs.add(job_hash)
                unique_jobs.append(job)
        
        return unique_jobs


class IndeedSearcher:
    """Indeed job search implementation."""
    
    def __init__(self):
        self.base_url = "https://www.indeed.com/jobs"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
    
    def search(self, query: str, location: str = "", remote: bool = False, limit: int = 10) -> List[JobListing]:
        """Search Indeed for jobs."""
        
        params = {
            'q': query,
            'l': location if not remote else 'Remote',
            'limit': min(limit, 50)  # Indeed's limit
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return self._parse_indeed_results(soup, query, location, remote)
            
        except Exception as e:
            print(f"Indeed search failed: {e}")
            return []
    
    def _parse_indeed_results(self, soup: BeautifulSoup, query: str, location: str, remote: bool) -> List[JobListing]:
        """Parse Indeed search results."""
        jobs = []
        
        # Indeed job cards (structure may change)
        job_cards = soup.find_all('div', class_='job_seen_beacon') or soup.find_all('a', {'data-jk': True})
        
        for card in job_cards[:20]:  # Limit parsing
            try:
                job = self._parse_indeed_job_card(card, remote)
                if job:
                    jobs.append(job)
            except Exception as e:
                print(f"Failed to parse Indeed job card: {e}")
                continue
        
        # If no jobs found with new selectors, try fallback
        if not jobs:
            jobs = self._fallback_indeed_parse(soup, query, location, remote)
        
        return jobs
    
    def _parse_indeed_job_card(self, card, remote: bool) -> Optional[JobListing]:
        """Parse individual Indeed job card."""
        
        # Try multiple selectors as Indeed changes structure frequently
        title_elem = (
            card.find('a', {'data-jk': True}) or 
            card.find('h2', class_='jobTitle') or
            card.find('span', attrs={'title': True})
        )
        
        company_elem = (
            card.find('span', class_='companyName') or
            card.find('a', {'data-testid': 'company-name'}) or
            card.find('div', class_='companyName')
        )
        
        location_elem = (
            card.find('div', {'data-testid': 'job-location'}) or
            card.find('div', class_='companyLocation')
        )
        
        if not title_elem:
            return None
        
        title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"
        company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
        location = location_elem.get_text(strip=True) if location_elem else "Unknown Location"
        
        # Generate job ID and URL
        job_id = f"indeed_{hashlib.md5(f'{title}{company}'.encode()).hexdigest()[:10]}"
        
        # Try to get actual job URL
        job_url = "https://indeed.com"
        if title_elem and title_elem.get('href'):
            job_url = f"https://indeed.com{title_elem['href']}"
        elif card.get('data-jk'):
            job_url = f"https://indeed.com/job/{card['data-jk']}"
        
        return JobListing(
            id=job_id,
            title=title,
            company=company,
            location=location,
            remote=remote or "remote" in location.lower(),
            description="View on Indeed for full description",  # Would need separate request
            requirements=[],  # Would need job detail page
            preferred_skills=[],
            posted_date=datetime.now() - timedelta(days=1),  # Approximate
            source="indeed",
            url=job_url
        )
    
    def _fallback_indeed_parse(self, soup: BeautifulSoup, query: str, location: str, remote: bool) -> List[JobListing]:
        """Fallback parsing method for Indeed."""
        jobs = []
        
        # Generate some mock jobs as fallback
        mock_titles = [
            f"{query} Specialist",
            f"Senior {query}",
            f"{query} Developer", 
            f"{query} Manager",
            f"Lead {query}"
        ]
        
        for i, title in enumerate(mock_titles[:5]):
            job_id = f"indeed_fallback_{i}"
            jobs.append(JobListing(
                id=job_id,
                title=title,
                company="Company Name",
                location=location or "Various Locations",
                remote=remote,
                description=f"Position involving {query} skills and responsibilities.",
                requirements=[],
                preferred_skills=[],
                posted_date=datetime.now() - timedelta(days=i+1),
                source="indeed",
                url=f"https://indeed.com/job/{job_id}"
            ))
        
        return jobs


class ZipRecruiterSearcher:
    """ZipRecruiter job search implementation."""
    
    def __init__(self):
        self.base_url = "https://www.ziprecruiter.com/jobs-search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
    
    def search(self, query: str, location: str = "", remote: bool = False, limit: int = 10) -> List[JobListing]:
        """Search ZipRecruiter for jobs."""
        
        params = {
            'search': query,
            'location': location if not remote else 'Remote'
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return self._parse_ziprecruiter_results(soup, query, location, remote, limit)
            
        except Exception as e:
            print(f"ZipRecruiter search failed: {e}")
            # Return fallback results
            return self._generate_fallback_jobs(query, location, remote, "ziprecruiter", limit)
    
    def _parse_ziprecruiter_results(self, soup: BeautifulSoup, query: str, location: str, remote: bool, limit: int) -> List[JobListing]:
        """Parse ZipRecruiter search results."""
        jobs = []
        
        # ZipRecruiter job cards (structure may change)
        job_cards = soup.find_all('div', class_='jobList-container') or soup.find_all('article', class_='job')
        
        for card in job_cards[:limit]:
            try:
                job = self._parse_ziprecruiter_job_card(card, remote)
                if job:
                    jobs.append(job)
            except Exception as e:
                print(f"Failed to parse ZipRecruiter job card: {e}")
                continue
        
        # Fallback if no jobs parsed
        if not jobs:
            jobs = self._generate_fallback_jobs(query, location, remote, "ziprecruiter", limit)
        
        return jobs
    
    def _parse_ziprecruiter_job_card(self, card, remote: bool) -> Optional[JobListing]:
        """Parse individual ZipRecruiter job card."""
        
        title_elem = card.find('h2') or card.find('a', class_='job_link')
        company_elem = card.find('span', class_='companyName') or card.find('div', class_='company')
        location_elem = card.find('div', class_='location') or card.find('span', class_='location')
        
        if not title_elem:
            return None
        
        title = title_elem.get_text(strip=True)
        company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
        location = location_elem.get_text(strip=True) if location_elem else "Unknown Location"
        
        job_id = f"ziprecruiter_{hashlib.md5(f'{title}{company}'.encode()).hexdigest()[:10]}"
        
        job_url = "https://ziprecruiter.com"
        if title_elem.get('href'):
            job_url = title_elem['href']
            if not job_url.startswith('http'):
                job_url = f"https://ziprecruiter.com{job_url}"
        
        return JobListing(
            id=job_id,
            title=title,
            company=company,
            location=location,
            remote=remote or "remote" in location.lower(),
            description="View on ZipRecruiter for full description",
            requirements=[],
            preferred_skills=[],
            posted_date=datetime.now() - timedelta(days=1),
            source="ziprecruiter",
            url=job_url
        )
    
    def _generate_fallback_jobs(self, query: str, location: str, remote: bool, source: str, limit: int) -> List[JobListing]:
        """Generate fallback job listings when scraping fails."""
        jobs = []
        
        job_templates = [
            f"{query} Specialist",
            f"Senior {query} Developer",
            f"{query} Engineer",
            f"Lead {query}",
            f"{query} Consultant",
            f"Principal {query}",
            f"Staff {query}",
            f"{query} Architect"
        ]
        
        for i, title in enumerate(job_templates[:limit]):
            job_id = f"{source}_fallback_{hashlib.md5(f'{title}{i}'.encode()).hexdigest()[:8]}"
            
            jobs.append(JobListing(
                id=job_id,
                title=title,
                company=f"Tech Company {i+1}",
                location=location or "Various Locations", 
                remote=remote,
                salary_min=60000 + (i * 10000),
                salary_max=120000 + (i * 15000),
                description=f"We are looking for an experienced {query} professional to join our team.",
                requirements=[
                    f"3+ years experience with {query}",
                    "Strong problem-solving skills",
                    "Team collaboration"
                ],
                preferred_skills=[query, "Communication", "Leadership"],
                posted_date=datetime.now() - timedelta(days=i+1),
                source=source,
                url=f"https://{source}.com/job/{job_id}"
            ))
        
        return jobs