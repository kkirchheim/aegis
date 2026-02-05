#!/usr/bin/env python3
"""
Paper Reproducibility Checker CLI Tool

Uploads PDF papers to the Paper Reproducibility Checker API and polls for results.

Usage Examples:
    # Basic upload
    python repro-cli.py -u http://localhost:5000 -k prc_sk_abc123 -p paper.pdf
    
    # With custom output file
    python repro-cli.py -u http://localhost:5000 -k prc_sk_abc123 -p paper.pdf -o result.json
    
    # Using long-form arguments
    python repro-cli.py --url http://localhost:5000 --key prc_sk_abc123 --pdf paper.pdf --output my_result.json
"""

import argparse
import json
import os
import sys
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urljoin


class ReproCliError(Exception):
    """Base exception for CLI errors."""
    pass


class APIClient:
    """Client for interacting with the Paper Reproducibility Checker API."""
    
    UPLOAD_ENDPOINT = "/api/job/upload"
    STATUS_ENDPOINT = "/api/job/{job_id}/full"
    
    def __init__(self, base_url: str, api_key: str):
        """Initialize the API client."""
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}'
        })
    
    def upload_pdf(self, pdf_path: str) -> str:
        """
        Upload a PDF file to the API.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            job_id from the API response
            
        Raises:
            ReproCliError: If upload fails
        """
        url = urljoin(self.base_url, self.UPLOAD_ENDPOINT)
        
        try:
            with open(pdf_path, 'rb') as f:
                files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
                print(f"📤 Uploading {Path(pdf_path).name}...")
                response = self.session.post(url, files=files, timeout=30)
        except FileNotFoundError:
            raise ReproCliError(f"PDF file not found: {pdf_path}")
        except requests.exceptions.ConnectionError:
            raise ReproCliError(f"Failed to connect to API at {self.base_url}")
        except requests.exceptions.Timeout:
            raise ReproCliError("Upload request timed out")
        except requests.exceptions.RequestException as e:
            raise ReproCliError(f"Upload request failed: {e}")
        
        if response.status_code == 401:
            raise ReproCliError("Authentication failed: Invalid API key")
        elif response.status_code == 403:
            raise ReproCliError("Authentication failed: Forbidden")
        elif response.status_code >= 400:
            try:
                error_detail = response.json().get('error', response.text)
            except:
                error_detail = response.text
            raise ReproCliError(f"Upload failed ({response.status_code}): {error_detail}")
        
        try:
            data = response.json()
            job_id = data.get('job_id')
            if not job_id:
                raise ReproCliError("No job_id in API response")
            return job_id
        except json.JSONDecodeError:
            raise ReproCliError(f"Invalid JSON response from API: {response.text}")
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the full status of a job.
        
        Args:
            job_id: The job ID to check
            
        Returns:
            Full job status dictionary
            
        Raises:
            ReproCliError: If status check fails
        """
        url = urljoin(self.base_url, self.STATUS_ENDPOINT.format(job_id=job_id))
        
        try:
            response = self.session.get(url, timeout=10)
        except requests.exceptions.ConnectionError:
            raise ReproCliError(f"Failed to connect to API at {self.base_url}")
        except requests.exceptions.Timeout:
            raise ReproCliError("Status check request timed out")
        except requests.exceptions.RequestException as e:
            raise ReproCliError(f"Status check request failed: {e}")
        
        if response.status_code == 401:
            raise ReproCliError("Authentication failed: Invalid API key")
        elif response.status_code == 404:
            raise ReproCliError(f"Job not found: {job_id}")
        elif response.status_code >= 400:
            try:
                error_detail = response.json().get('error', response.text)
            except:
                error_detail = response.text
            raise ReproCliError(f"Status check failed ({response.status_code}): {error_detail}")
        
        try:
            return response.json()
        except json.JSONDecodeError:
            raise ReproCliError(f"Invalid JSON response from API: {response.text}")


def validate_url(url: str) -> None:
    """Validate that the URL is properly formatted."""
    if not url.startswith(('http://', 'https://')):
        raise ReproCliError("Invalid URL: must start with http:// or https://")


def validate_api_key(key: str) -> None:
    """Validate that the API key has the correct format."""
    if not key.startswith('prc_sk_'):
        raise ReproCliError("Invalid API key format: must start with 'prc_sk_'")


def print_progress(job_data: Dict[str, Any]) -> None:
    """Print current job progress."""
    status = job_data.get('status', 'unknown')
    stage = job_data.get('current_stage', 'unknown')
    progress = job_data.get('progress', 0)
    
    print(f"Status: {status}, Stage: {stage}, Progress: {progress}%")


def poll_job_status(client: APIClient, job_id: str, timeout_seconds: int = 600) -> Dict[str, Any]:
    """
    Poll the job status until completion or failure.
    
    Args:
        client: API client instance
        job_id: Job ID to poll
        timeout_seconds: Maximum time to wait (default 10 minutes)
        
    Returns:
        Final job status dictionary
        
    Raises:
        ReproCliError: If timeout or job fails
    """
    start_time = time.time()
    poll_interval = 2  # seconds
    
    print(f"\n⏳ Polling for job results (timeout: {timeout_seconds}s)...")
    
    while True:
        elapsed = time.time() - start_time
        
        if elapsed > timeout_seconds:
            raise ReproCliError(
                f"Job polling timeout after {timeout_seconds}s. "
                f"Job ID: {job_id}. Check status manually."
            )
        
        try:
            job_data = client.get_job_status(job_id)
        except ReproCliError as e:
            print(f"⚠️  Status check error: {e}")
            print(f"⏳ Retrying in {poll_interval}s...")
            time.sleep(poll_interval)
            continue
        
        status = job_data.get('status', 'unknown')
        
        print_progress(job_data)
        
        if status == "completed":
            print("✅ Job completed successfully!")
            return job_data
        elif status == "failed":
            error_msg = job_data.get('error_message', 'No error message provided')
            raise ReproCliError(f"Job failed: {error_msg}")
        elif status == "pending":
            print("⏳ Job pending...")
        elif status == "processing":
            pass  # Already printed progress
        
        time.sleep(poll_interval)


def save_results(output_path: str, job_data: Dict[str, Any]) -> None:
    """Save job results to a JSON file."""
    try:
        with open(output_path, 'w') as f:
            json.dump(job_data, f, indent=2)
        print(f"\n📁 Results saved to {output_path}")
    except IOError as e:
        raise ReproCliError(f"Failed to save results: {e}")


def print_final_status(job_data: Dict[str, Any]) -> None:
    """Pretty print the final job status."""
    print("\n" + "="*60)
    print("FINAL STATUS")
    print("="*60)
    print(f"Status: {job_data.get('status')}")
    print(f"Stage: {job_data.get('current_stage')}")
    print(f"Progress: {job_data.get('progress')}%")
    
    if job_data.get('results'):
        print(f"\n📊 Results:")
        results = job_data.get('results', {})
        for key, value in results.items():
            print(f"  {key}: {value}")
    
    if job_data.get('error_message'):
        print(f"\n❌ Error: {job_data.get('error_message')}")
    
    print("="*60)


def main():
    """Main entry point for the CLI tool."""
    parser = argparse.ArgumentParser(
        description="Upload papers to the Paper Reproducibility Checker API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python repro-cli.py -u http://localhost:5000 -k prc_sk_abc123 -p paper.pdf
  python repro-cli.py --url http://localhost:5000 --key prc_sk_abc123 --pdf paper.pdf --output result.json
        """
    )
    
    parser.add_argument(
        '-u', '--url',
        required=True,
        help='Server URL (e.g., http://localhost:5000)'
    )
    parser.add_argument(
        '-k', '--key',
        required=True,
        help='API key (prc_sk_...)'
    )
    parser.add_argument(
        '-p', '--pdf',
        required=True,
        help='Path to PDF file to upload'
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output file path for JSON (default: job_{job_id}.json)'
    )
    
    args = parser.parse_args()
    
    try:
        # Validate arguments
        validate_url(args.url)
        validate_api_key(args.key)
        
        if not os.path.exists(args.pdf):
            raise ReproCliError(f"PDF file not found: {args.pdf}")
        
        # Initialize client
        client = APIClient(args.url, args.key)
        
        # Upload PDF
        job_id = client.upload_pdf(args.pdf)
        print(f"✅ Upload successful! Job ID: {job_id}\n")
        
        # Poll for results
        job_data = poll_job_status(client, job_id)
        
        # Determine output file
        output_file = args.output or f"job_{job_id}.json"
        
        # Save results
        save_results(output_file, job_data)
        
        # Print final status
        print_final_status(job_data)
        
        return 0
        
    except ReproCliError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
