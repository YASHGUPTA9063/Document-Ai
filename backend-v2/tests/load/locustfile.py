"""
Load Testing with Locust
=========================
Simulates concurrent users hitting the Document AI API endpoints.

Usage:
    locust -f tests/load/locustfile.py --host=http://localhost:8000

Dashboard available at http://localhost:8089
"""

from locust import HttpUser, task, between


class DocumentAIUser(HttpUser):
    """Simulates a user interacting with the Document AI API."""

    wait_time = between(1, 3)

    @task(3)
    def upload_document(self):
        """Upload a document (heaviest endpoint)."""
        # Use a small test file to avoid overwhelming the system
        self.client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", b"Sample document content for load testing.", "text/plain")},
            name="/api/v1/documents/upload",
        )

    @task(5)
    def list_documents(self):
        """List all documents."""
        self.client.get(
            "/api/v1/documents",
            name="/api/v1/documents",
        )

    @task(3)
    def health_check(self):
        """Check system health."""
        self.client.get(
            "/health",
            name="/health",
        )

    @task(1)
    def list_claims(self):
        """List all claims."""
        self.client.get(
            "/api/v1/claims",
            name="/api/v1/claims",
        )

    @task(1)
    def metrics(self):
        """Fetch Prometheus metrics."""
        self.client.get(
            "/metrics",
            name="/metrics",
        )
