"""Integration tests for file/document management and stored files."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


class TestStoredFiles:
    def test_create_stored_file(self, api_client):
        test_file = SimpleUploadedFile("test_doc.pdf", b"fake pdf content", content_type="application/pdf")
        resp = api_client.post("/api/v1/stored-files/", {
            "file": test_file,
            "original_name": "test_doc.pdf",
            "version_label": "1.0",
        }, format="multipart")
        assert resp.status_code == 201
        assert resp.data["original_name"] == "test_doc.pdf"

    def test_file_versioning(self, api_client):
        f1 = SimpleUploadedFile("drawing_v1.dxf", b"v1 content")
        r1 = api_client.post("/api/v1/stored-files/", {
            "file": f1, "original_name": "drawing.dxf",
            "version_label": "1.0",
        }, format="multipart")
        assert r1.status_code == 201

        f2 = SimpleUploadedFile("drawing_v2.dxf", b"v2 content")
        r2 = api_client.post("/api/v1/stored-files/", {
            "file": f2, "original_name": "drawing.dxf",
            "version_label": "2.0",
        }, format="multipart")
        assert r2.status_code == 201
        assert r2.data["version_label"] == "2.0"

    def test_search_files(self, api_client):
        f = SimpleUploadedFile("bracket_cad.step", b"step content")
        api_client.post("/api/v1/stored-files/", {
            "file": f, "original_name": "bracket_cad.step",
            "version_label": "1.0",
        }, format="multipart")
        resp = api_client.get("/api/v1/stored-files/?search=bracket")
        assert resp.data["count"] >= 1


class TestQuoteAttachments:
    def test_upload_attachment_to_quote(self, api_client, customer_entity):
        q = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-ATTACH",
            "customer": str(customer_entity.id),
        })
        quote_id = q.data["id"]
        f = SimpleUploadedFile("spec.pdf", b"spec content", content_type="application/pdf")
        att = api_client.post("/api/v1/quote-attachments/", {
            "quote": quote_id,
            "file": f,
            "original_name": "spec.pdf",
            "content_type": "application/pdf",
        }, format="multipart")
        assert att.status_code == 201

        attachments = api_client.get(f"/api/v1/quote-attachments/?quote={quote_id}")
        assert attachments.data["count"] == 1
