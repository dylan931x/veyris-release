# VEYRIS signed release source (reviewed export)

This is a **clean copy** of VEYRIS application files prepared for a GitHub repository.
It was copied separately from the live installation to avoid publishing personal data,
old backups, market data, Ollama models, logs, or local configuration.

## Status
- GitHub repository: **not created yet**; requires the owner's GitHub connection.
- Signing key: **not provisioned yet**.
- Client release channel: **disabled** until repository and public key are trusted.
- Local Windows application: still running independently.

## Release format
A tagged GitHub release (e.g. v2.5.0) contains exactly:
- veyris-release.zip (approved application source files)
- veyris-manifest.json (version and SHA-256 hashes of package and files)
- veyris-manifest.sig (Ed25519 signature over raw manifest bytes)

The VEYRIS client verifies the pinned publisher key, all file hashes, expected
filenames, semver progression and Python/JavaScript syntax before staging.
Verified updates install only when VEYRIS is next launched, with backup and startup rollback.
The installer/verification modules are *never replaced* by downloaded release files.

## First-time setup after connecting GitHub
1. Create a **public** repo containing only these reviewed files; the client
   reads public GitHub Releases without a personal access token.
2. Create GitHub Actions environment named "signed-release" with required review approval.
3. On your own PC, run publisher/generate_keypair_once.py. Treat terminal output as a secret.
4. Set VEYRIS_SIGNING_KEY_B64 as a GitHub Actions **environment secret** in
   that environment. Never put it in code, files committed to Git, or chat.
5. Set the client update_data/release-channel.json to:
   {
     "enabled": true,
     "owner": "YOUR_GITHUB_USERNAME",
     "repo": "YOUR_RELEASE_REPO",
     "public_key_b64": "YOUR_PINNED_ED25519_PUBLIC_KEY"
   }
   Only configure after verifying the exact repository and key yourself.
6. Update reviewed app files here, increment VERSION in server.py, commit,
   then push an approved version tag. The GitHub workflow signs/publishes release assets.
7. The Windows scheduled maintenance check will download and stage valid releases.
   At next desktop launch, launcher.py installs and health-checks them; a failed
   startup triggers rollback.

## Important restrictions
This setup does NOT give the LLM permission to generate and publish arbitrary code.
It does NOT install untrusted code from GitHub, random pull requests, or webpages.
Do not put your private signing key in a public GitHub repository.
Do not authorize releases from unknown accounts.
Publisher signatures prove origin and integrity, not code correctness. Review each release.

GitHub releases REST API: https://docs.github.com/en/rest/releases/releases
