"""Cryptographic integrity layer for artifacts.

This module provides cryptographic signing and verification for artifacts to:
- Ensure data integrity (detect tampering)
- Enable provenance tracking
- Support external sharing with verification
- Prevent recomputation confusion
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


LOGGER = logging.getLogger(__name__)

DEFAULT_SECRET_PATH = Path(__file__).resolve().parents[2] / "artifacts" / "artifact_secret.key"


@dataclass
class ArtifactSignature:
    """Cryptographic signature for an artifact."""
    hash_algorithm: str
    content_hash: str
    hmac_signature: str
    timestamp: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hash_algorithm": self.hash_algorithm,
            "content_hash": self.content_hash,
            "hmac_signature": self.hmac_signature,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArtifactSignature:
        """Create from dictionary."""
        return cls(
            hash_algorithm=data["hash_algorithm"],
            content_hash=data["content_hash"],
            hmac_signature=data["hmac_signature"],
            timestamp=data["timestamp"],
            metadata=data.get("metadata", {})
        )


class ArtifactSigner:
    """Sign and verify artifacts using cryptographic methods."""
    
    def __init__(self, secret_key: Optional[str] = None):
        """Initialize signer.

        Args:
            secret_key: Secret key for HMAC signing. If None, uses environment variable
                       ARTIFACT_SECRET_KEY or persists a key to disk.
        """
        self._secret_path = Path(
            os.environ.get("ARTIFACT_SECRET_PATH", DEFAULT_SECRET_PATH)
        )

        if secret_key:
            self.secret_key = secret_key.encode()
        else:
            env_key = os.environ.get("ARTIFACT_SECRET_KEY")
            if env_key:
                self.secret_key = env_key.encode()
            else:
                self.secret_key = self._load_or_create_secret()

    def _load_or_create_secret(self) -> bytes:
        """Load a persisted secret key or create a new one."""

        path = self._secret_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raw = path.read_text(encoding="utf-8").strip()
                if not raw:
                    raise ValueError("artifact secret key file is empty")
                try:
                    return bytes.fromhex(raw)
                except ValueError as exc:
                    raise ValueError("artifact secret key file must contain hex-encoded data") from exc

            token = secrets.token_hex(32)
            path.write_text(token, encoding="utf-8")
            LOGGER.info("artifact_secret_key_created path=%s", path)
            return bytes.fromhex(token)
        except Exception as exc:
            raise RuntimeError(f"Unable to initialize artifact signer secret at {path}: {exc}") from exc
    
    def compute_hash(self, content: str, algorithm: str = "sha256") -> str:
        """Compute cryptographic hash of content.
        
        Args:
            content: Content to hash
            algorithm: Hash algorithm (sha256, sha512)
            
        Returns:
            Hex-encoded hash
        """
        if algorithm == "sha256":
            hasher = hashlib.sha256()
        elif algorithm == "sha512":
            hasher = hashlib.sha512()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        
        hasher.update(content.encode('utf-8'))
        return hasher.hexdigest()
    
    def compute_hmac(self, content: str, algorithm: str = "sha256") -> str:
        """Compute HMAC signature of content.
        
        Args:
            content: Content to sign
            algorithm: Hash algorithm
            
        Returns:
            Hex-encoded HMAC
        """
        if algorithm == "sha256":
            return hmac.new(
                self.secret_key,
                content.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
        elif algorithm == "sha512":
            return hmac.new(
                self.secret_key,
                content.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    def sign_artifact(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        algorithm: str = "sha256"
    ) -> ArtifactSignature:
        """Sign an artifact with cryptographic signature.
        
        Args:
            content: Artifact content to sign
            metadata: Optional metadata to include in signature
            algorithm: Hash algorithm to use
            
        Returns:
            ArtifactSignature with hashes and signature
        """
        # Compute content hash
        content_hash = self.compute_hash(content, algorithm)
        
        # Compute HMAC signature
        hmac_signature = self.compute_hmac(content, algorithm)
        
        # Create signature object
        signature = ArtifactSignature(
            hash_algorithm=algorithm,
            content_hash=content_hash,
            hmac_signature=hmac_signature,
            timestamp=datetime.utcnow().isoformat() + "Z",
            metadata=metadata or {}
        )
        
        return signature
    
    def verify_artifact(
        self,
        content: str,
        signature: ArtifactSignature
    ) -> bool:
        """Verify artifact signature.
        
        Args:
            content: Artifact content to verify
            signature: Signature to verify against
            
        Returns:
            True if signature is valid, False otherwise
        """
        # Recompute content hash
        computed_hash = self.compute_hash(content, signature.hash_algorithm)
        if computed_hash != signature.content_hash:
            return False
        
        # Recompute HMAC
        computed_hmac = self.compute_hmac(content, signature.hash_algorithm)
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(computed_hmac, signature.hmac_signature)
    
    def sign_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sign a JSON payload and embed signature.
        
        Args:
            payload: Dictionary to sign
            
        Returns:
            Payload with embedded signature
        """
        # Convert payload to canonical JSON
        content = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        # Sign content
        signature = self.sign_artifact(content, metadata={
            "type": "json_payload",
            "keys": sorted(payload.keys())
        })
        
        # Add signature to payload
        signed_payload = payload.copy()
        signed_payload["_signature"] = signature.to_dict()
        
        return signed_payload
    
    def verify_payload(self, payload: Dict[str, Any]) -> bool:
        """Verify a signed JSON payload.
        
        Args:
            payload: Signed payload to verify
            
        Returns:
            True if signature is valid
        """
        if "_signature" not in payload:
            return False
        
        # Extract signature
        signature_dict = payload["_signature"]
        signature = ArtifactSignature.from_dict(signature_dict)
        
        # Remove signature from payload for verification
        payload_copy = payload.copy()
        del payload_copy["_signature"]
        
        # Convert to canonical JSON
        content = json.dumps(payload_copy, sort_keys=True, separators=(',', ':'))
        
        # Verify
        return self.verify_artifact(content, signature)


class RSAKeypairManager:
    """Manage RSA keypairs for public key cryptography (optional advanced feature)."""
    
    def __init__(self):
        """Initialize keypair manager."""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available. Install with: pip install cryptography")
        
        self.private_key: Optional[rsa.RSAPrivateKey] = None
        self.public_key: Optional[rsa.RSAPublicKey] = None
    
    def generate_keypair(self, key_size: int = 2048):
        """Generate new RSA keypair.
        
        Args:
            key_size: RSA key size in bits
        """
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
    
    def save_private_key(self, path: str, password: Optional[bytes] = None):
        """Save private key to file.
        
        Args:
            path: File path to save to
            password: Optional password for encryption
        """
        if not self.private_key:
            raise ValueError("No private key available")
        
        if password:
            encryption = serialization.BestAvailableEncryption(password)
        else:
            encryption = serialization.NoEncryption()
        
        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption
        )
        
        with open(path, 'wb') as f:
            f.write(pem)
    
    def save_public_key(self, path: str):
        """Save public key to file.
        
        Args:
            path: File path to save to
        """
        if not self.public_key:
            raise ValueError("No public key available")
        
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        with open(path, 'wb') as f:
            f.write(pem)
    
    def load_private_key(self, path: str, password: Optional[bytes] = None):
        """Load private key from file.
        
        Args:
            path: File path to load from
            password: Optional password for decryption
        """
        with open(path, 'rb') as f:
            pem_data = f.read()
        
        self.private_key = serialization.load_pem_private_key(
            pem_data,
            password=password,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
    
    def load_public_key(self, path: str):
        """Load public key from file.
        
        Args:
            path: File path to load from
        """
        with open(path, 'rb') as f:
            pem_data = f.read()
        
        self.public_key = serialization.load_pem_public_key(
            pem_data,
            backend=default_backend()
        )
    
    def sign_data(self, data: bytes) -> bytes:
        """Sign data with private key.
        
        Args:
            data: Data to sign
            
        Returns:
            Digital signature
        """
        if not self.private_key:
            raise ValueError("No private key available")
        
        signature = self.private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return signature
    
    def verify_signature(self, data: bytes, signature: bytes) -> bool:
        """Verify signature with public key.
        
        Args:
            data: Original data
            signature: Signature to verify
            
        Returns:
            True if signature is valid
        """
        if not self.public_key:
            raise ValueError("No public key available")
        
        try:
            self.public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False


# Global signer instance
_signer: Optional[ArtifactSigner] = None


def get_signer() -> ArtifactSigner:
    """Get global signer instance."""
    global _signer
    if _signer is None:
        _signer = ArtifactSigner()
    return _signer


def sign_artifact(content: str, metadata: Optional[Dict[str, Any]] = None) -> ArtifactSignature:
    """Convenience function to sign an artifact.
    
    Args:
        content: Artifact content
        metadata: Optional metadata
        
    Returns:
        ArtifactSignature
    """
    return get_signer().sign_artifact(content, metadata)


def verify_artifact(content: str, signature: ArtifactSignature) -> bool:
    """Convenience function to verify an artifact.
    
    Args:
        content: Artifact content
        signature: Signature to verify
        
    Returns:
        True if valid
    """
    return get_signer().verify_artifact(content, signature)
