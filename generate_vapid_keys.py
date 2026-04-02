"""
generate_vapid_keys.py — One-time VAPID key pair generator

Run this ONCE locally to create your VAPID key pair, then add the output
values as GitHub Actions secrets (VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY).

Usage:
    pip install pywebpush
    python3 generate_vapid_keys.py

Never commit the private key. Add both values to:
    GitHub repo → Settings → Secrets and variables → Actions
"""

import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


def generate():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key  = private_key.public_key()

    # Private key — raw 32-byte scalar, base64url-encoded (no padding)
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    vapid_private = base64.urlsafe_b64encode(private_bytes).decode().rstrip("=")

    # Public key — uncompressed EC point (65 bytes: 0x04 + X + Y), base64url-encoded
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    vapid_public = base64.urlsafe_b64encode(public_bytes).decode().rstrip("=")

    print("\n✅ VAPID keys generated. Add these as GitHub Actions secrets:\n")
    print(f"VAPID_PUBLIC_KEY={vapid_public}")
    print(f"\nVAPID_PRIVATE_KEY={vapid_private}")
    print("\n⚠️  Never commit VAPID_PRIVATE_KEY to the repo.")
    print("    Add both to: GitHub repo → Settings → Secrets → Actions\n")


if __name__ == "__main__":
    generate()
