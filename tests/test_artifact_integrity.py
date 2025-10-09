"""Tests for artifact integrity and cryptographic signing."""

import json
import pytest

from src.security.artifact_integrity import (
    ArtifactSigner,
    ArtifactSignature,
    get_signer,
    sign_artifact,
    verify_artifact,
)


class TestArtifactSigner:
    """Test cryptographic artifact signing."""
    
    def test_compute_hash_sha256(self):
        """Test SHA-256 hash computation."""
        signer = ArtifactSigner()
        content = "Test artifact content"
        hash_value = signer.compute_hash(content, algorithm="sha256")
        
        assert len(hash_value) == 64  # SHA-256 produces 64 hex characters
        assert hash_value.isalnum()
    
    def test_compute_hash_sha512(self):
        """Test SHA-512 hash computation."""
        signer = ArtifactSigner()
        content = "Test artifact content"
        hash_value = signer.compute_hash(content, algorithm="sha512")
        
        assert len(hash_value) == 128  # SHA-512 produces 128 hex characters
        assert hash_value.isalnum()
    
    def test_hash_consistency(self):
        """Test that same content produces same hash."""
        signer = ArtifactSigner()
        content = "Consistent content"
        
        hash1 = signer.compute_hash(content)
        hash2 = signer.compute_hash(content)
        
        assert hash1 == hash2
    
    def test_hash_different_for_different_content(self):
        """Test that different content produces different hashes."""
        signer = ArtifactSigner()
        
        hash1 = signer.compute_hash("Content A")
        hash2 = signer.compute_hash("Content B")
        
        assert hash1 != hash2
    
    def test_compute_hmac(self):
        """Test HMAC signature computation."""
        signer = ArtifactSigner(secret_key="test_secret_key")
        content = "Test content"
        hmac_sig = signer.compute_hmac(content)
        
        assert len(hmac_sig) == 64  # HMAC-SHA256 produces 64 hex characters
        assert hmac_sig.isalnum()
    
    def test_hmac_consistency(self):
        """Test that HMAC is consistent with same key."""
        signer = ArtifactSigner(secret_key="test_secret_key")
        content = "Test content"
        
        hmac1 = signer.compute_hmac(content)
        hmac2 = signer.compute_hmac(content)
        
        assert hmac1 == hmac2
    
    def test_hmac_different_with_different_keys(self):
        """Test that different keys produce different HMACs."""
        content = "Test content"
        
        signer1 = ArtifactSigner(secret_key="key1")
        signer2 = ArtifactSigner(secret_key="key2")
        
        hmac1 = signer1.compute_hmac(content)
        hmac2 = signer2.compute_hmac(content)
        
        assert hmac1 != hmac2
    
    def test_sign_artifact(self):
        """Test artifact signing."""
        signer = ArtifactSigner()
        content = "# Test Artifact\n\nSome content here."
        metadata = {"title": "Test", "type": "markdown"}
        
        signature = signer.sign_artifact(content, metadata=metadata)
        
        assert isinstance(signature, ArtifactSignature)
        assert signature.hash_algorithm == "sha256"
        assert len(signature.content_hash) == 64
        assert len(signature.hmac_signature) == 64
        assert signature.timestamp.endswith("Z")
        assert signature.metadata == metadata
    
    def test_verify_valid_artifact(self):
        """Test verification of valid artifact."""
        signer = ArtifactSigner(secret_key="test_key")
        content = "Valid artifact content"
        
        signature = signer.sign_artifact(content)
        is_valid = signer.verify_artifact(content, signature)
        
        assert is_valid
    
    def test_verify_tampered_content(self):
        """Test detection of tampered content."""
        signer = ArtifactSigner(secret_key="test_key")
        original_content = "Original content"
        
        signature = signer.sign_artifact(original_content)
        
        # Tamper with content
        tampered_content = "Tampered content"
        is_valid = signer.verify_artifact(tampered_content, signature)
        
        assert not is_valid
    
    def test_verify_with_wrong_key(self):
        """Test that verification fails with wrong key."""
        signer1 = ArtifactSigner(secret_key="key1")
        signer2 = ArtifactSigner(secret_key="key2")
        
        content = "Test content"
        signature = signer1.sign_artifact(content)
        
        # Try to verify with different key
        is_valid = signer2.verify_artifact(content, signature)
        
        assert not is_valid
    
    def test_signature_to_dict(self):
        """Test signature serialization to dict."""
        signer = ArtifactSigner()
        content = "Test"
        signature = signer.sign_artifact(content, metadata={"key": "value"})
        
        sig_dict = signature.to_dict()
        
        assert isinstance(sig_dict, dict)
        assert "hash_algorithm" in sig_dict
        assert "content_hash" in sig_dict
        assert "hmac_signature" in sig_dict
        assert "timestamp" in sig_dict
        assert "metadata" in sig_dict
    
    def test_signature_from_dict(self):
        """Test signature deserialization from dict."""
        sig_dict = {
            "hash_algorithm": "sha256",
            "content_hash": "a" * 64,
            "hmac_signature": "b" * 64,
            "timestamp": "2025-10-08T12:00:00Z",
            "metadata": {"test": "data"}
        }
        
        signature = ArtifactSignature.from_dict(sig_dict)
        
        assert signature.hash_algorithm == "sha256"
        assert signature.content_hash == "a" * 64
        assert signature.hmac_signature == "b" * 64
        assert signature.timestamp == "2025-10-08T12:00:00Z"
        assert signature.metadata == {"test": "data"}
    
    def test_round_trip_serialization(self):
        """Test that signature survives round-trip serialization."""
        signer = ArtifactSigner()
        content = "Test content"
        
        original_signature = signer.sign_artifact(content)
        sig_dict = original_signature.to_dict()
        restored_signature = ArtifactSignature.from_dict(sig_dict)
        
        # Verify with restored signature
        is_valid = signer.verify_artifact(content, restored_signature)
        assert is_valid


class TestPayloadSigning:
    """Test JSON payload signing."""
    
    def test_sign_payload(self):
        """Test signing of JSON payload."""
        signer = ArtifactSigner(secret_key="test_key")
        payload = {
            "title": "Test Token",
            "gem_score": 0.85,
            "confidence": 0.92,
            "timestamp": "2025-10-08T12:00:00Z"
        }
        
        signed_payload = signer.sign_payload(payload)
        
        assert "_signature" in signed_payload
        assert "hash_algorithm" in signed_payload["_signature"]
        assert "content_hash" in signed_payload["_signature"]
        assert "hmac_signature" in signed_payload["_signature"]
        
        # Original data should still be present
        assert signed_payload["title"] == "Test Token"
        assert signed_payload["gem_score"] == 0.85
    
    def test_verify_valid_payload(self):
        """Test verification of valid signed payload."""
        signer = ArtifactSigner(secret_key="test_key")
        payload = {"data": "test", "value": 123}
        
        signed_payload = signer.sign_payload(payload)
        is_valid = signer.verify_payload(signed_payload)
        
        assert is_valid
    
    def test_verify_tampered_payload(self):
        """Test detection of tampered payload."""
        signer = ArtifactSigner(secret_key="test_key")
        payload = {"data": "test", "value": 123}
        
        signed_payload = signer.sign_payload(payload)
        
        # Tamper with data
        signed_payload["value"] = 456
        
        is_valid = signer.verify_payload(signed_payload)
        assert not is_valid
    
    def test_verify_payload_without_signature(self):
        """Test that unsigned payload fails verification."""
        signer = ArtifactSigner()
        payload = {"data": "test"}
        
        is_valid = signer.verify_payload(payload)
        assert not is_valid
    
    def test_canonical_json_ordering(self):
        """Test that key ordering doesn't affect signature."""
        signer = ArtifactSigner(secret_key="test_key")
        
        payload1 = {"b": 2, "a": 1, "c": 3}
        payload2 = {"a": 1, "b": 2, "c": 3}
        
        signed1 = signer.sign_payload(payload1)
        signed2 = signer.sign_payload(payload2)
        
        # Signatures should be identical (canonical ordering)
        assert signed1["_signature"]["content_hash"] == signed2["_signature"]["content_hash"]


class TestConvenienceFunctions:
    """Test convenience wrapper functions."""
    
    def test_sign_artifact_function(self):
        """Test sign_artifact convenience function."""
        content = "Test artifact"
        signature = sign_artifact(content, metadata={"type": "test"})
        
        assert isinstance(signature, ArtifactSignature)
        assert signature.metadata["type"] == "test"
    
    def test_verify_artifact_function(self):
        """Test verify_artifact convenience function."""
        content = "Test artifact"
        signature = sign_artifact(content)
        
        is_valid = verify_artifact(content, signature)
        assert is_valid
    
    def test_global_signer_instance(self):
        """Test that global signer is reused."""
        signer1 = get_signer()
        signer2 = get_signer()
        
        assert signer1 is signer2


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_content(self):
        """Test signing empty content."""
        signer = ArtifactSigner()
        signature = signer.sign_artifact("")
        
        assert isinstance(signature, ArtifactSignature)
        is_valid = signer.verify_artifact("", signature)
        assert is_valid
    
    def test_large_content(self):
        """Test signing large content."""
        signer = ArtifactSigner()
        large_content = "x" * 1000000  # 1MB of data
        
        signature = signer.sign_artifact(large_content)
        is_valid = signer.verify_artifact(large_content, signature)
        
        assert is_valid
    
    def test_unicode_content(self):
        """Test signing Unicode content."""
        signer = ArtifactSigner()
        unicode_content = "Test with émojis 🚀 and spëcial çhars"
        
        signature = signer.sign_artifact(unicode_content)
        is_valid = signer.verify_artifact(unicode_content, signature)
        
        assert is_valid
    
    def test_invalid_algorithm(self):
        """Test that invalid algorithm raises error."""
        signer = ArtifactSigner()
        
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            signer.compute_hash("test", algorithm="md5")
    
    def test_metadata_preservation(self):
        """Test that metadata is preserved in signature."""
        signer = ArtifactSigner()
        metadata = {
            "title": "Test Artifact",
            "author": "System",
            "version": "1.0",
            "tags": ["test", "crypto"]
        }
        
        signature = signer.sign_artifact("content", metadata=metadata)
        
        assert signature.metadata == metadata
        assert signature.metadata["title"] == "Test Artifact"
        assert "test" in signature.metadata["tags"]


class TestIntegrationWithExporter:
    """Test integration scenarios with artifact exporter."""
    
    def test_markdown_artifact_signing(self):
        """Test signing of markdown artifact."""
        signer = ArtifactSigner()
        
        markdown_content = """# Token Analysis Report

## Summary
GemScore: 0.85
Confidence: 0.92

## Lore
Ancient protocols whisper of hidden value...

## Data Snapshot
- Price: $1.23
- Volume: $1M
"""
        
        signature = signer.sign_artifact(markdown_content, metadata={
            "type": "markdown_artifact",
            "title": "Token Analysis"
        })
        
        assert signature.metadata["type"] == "markdown_artifact"
        is_valid = signer.verify_artifact(markdown_content, signature)
        assert is_valid
    
    def test_html_artifact_signing(self):
        """Test signing of HTML artifact."""
        signer = ArtifactSigner()
        
        html_content = """<!DOCTYPE html>
<html>
<head><title>Test Artifact</title></head>
<body>
<h1>Token Report</h1>
<p>Score: 0.85</p>
</body>
</html>"""
        
        signature = signer.sign_artifact(html_content, metadata={
            "type": "html_artifact",
            "format": "dashboard"
        })
        
        is_valid = signer.verify_artifact(html_content, signature)
        assert is_valid
    
    def test_detect_whitespace_tampering(self):
        """Test that even minor whitespace changes are detected."""
        signer = ArtifactSigner()
        original = "Line 1\nLine 2\nLine 3"
        
        signature = signer.sign_artifact(original)
        
        # Add extra whitespace
        tampered = "Line 1\nLine 2 \nLine 3"
        
        is_valid = signer.verify_artifact(tampered, signature)
        assert not is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
