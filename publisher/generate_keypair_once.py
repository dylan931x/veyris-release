"""Run LOCALLY once, after creating your trusted repository.

Outputs a new Ed25519 signing secret to THIS terminal only. Never share it in chat,
commit it to Git, log it, or store it in the VEYRIS install directory.
Add the private secret to a GitHub Actions environment secret called
VEYRIS_SIGNING_KEY_B64 and pin the public key in VEYRIS release-channel.json.
"""
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

priv = Ed25519PrivateKey.generate()
secret = base64.b64encode(priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())).decode()
public = base64.b64encode(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
print("PRIVATE SIGNING KEY — put in GitHub Actions 'signed-release' environment secret")
print(secret)
print("PUBLIC VERIFICATION KEY — add to VEYRIS update_data/release-channel.json")
print(public)
print("Never share either value if uncertain. The PRIVATE key must not be committed or kept on the client.")
