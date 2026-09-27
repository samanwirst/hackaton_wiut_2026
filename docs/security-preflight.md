# Pre-publication privacy review

Checked on 27 September 2026 before changing repository visibility.

- Gitleaks 8.30.1 was downloaded from its official GitHub release and its archive SHA-256
  matched the release checksum list. No scanner binary or credential is added to the repo.
- `gitleaks git --redact=100 --log-opts='--all --full-history'` scanned all 34 commits then
  reachable from local refs, through `aded919`: no findings. Repeat on the final commit.
- New `demo/server/` deployment files were scanned separately: no findings.
- Targeted tracked-text and historical-path checks found no private keys, authentication
  headers/tokens, browser session cookies, SSH credentials or private portal registration files.
- Original downloads, environments, local caches, browser-session materials and scanner
  reports stay outside Git. Only confirmed team names/roles are used in the public content.
- The model runs with bundled open weights; no hosted-model credentials are required.

These are scoped checks, not a guarantee that a scanner recognises every possible secret.
Do not paste SSH passwords, access tokens, contact details or portal receipts into commits,
workflow logs, screenshots, release notes or website data. No credential rotation or changes
to unrelated accounts/services were performed as part of this review.
