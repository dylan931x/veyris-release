"""Display only the public Ed25519 verification key from the GitHub signing secret."""
import base64
import os
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

secret = os.environ.get("VEYRIS_SIGNING_KEY_B64", "").strip()
key_bytes = base64.b64decode(secret, validate=True)
if len(key_bytes) != 32:
    raise ValueError("GitHub environment signing secret is missing or invalid")
public = Ed25519PrivateKey.from_private_bytes(key_bytes).public_key().public_bytes(
    Encoding.Raw, PublicFormat.Raw
)
print("VEYRIS_PUBLIC_KEY_B64=" + base64.b64encode(public).decode("ascii"))
print("The private signing key was NOT printed or exported.")
