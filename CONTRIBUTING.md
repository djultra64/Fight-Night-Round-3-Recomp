# Contributing

Read the [build guide](docs/beta/building.md) and [known issues](docs/beta/known-issues.md) before proposing changes. Keep public documentation, issue reports and pull requests in English.

Provide a reproducible problem and explain the resulting behavior. Include relevant automated checks with code changes. Keep public documentation focused on product behavior, requirements and limitations; omit personal testing reports, device histories and gameplay validation narratives.

Preserve the original game clock in the production target. Keep experimental timing and renderer work out of production changes unless explicitly agreed. Separate logical actions from physical buttons, account for Nintendo's exchanged A/B and X/Y positions, preserve optional remapping, and check prompts and actions together. Automatic prompts should follow the last active device, with manual family selection available.

Do not submit disc images, XEX files, original assets, generated PowerPC sources, game-derived overrides, shaders or diagnostic textures. Supply only original project code, patches, safe metadata and tests that do not embed proprietary material. Preserve authentic third-party authorship and required notices.

The project maintainer's work is attributed to **DJ Ultra 64 — djultra64**. Do not substitute personal system-account names or email addresses. Contributors retain their own authentic attribution. Licensing must be reviewed before adding a dependency or granting reuse terms for code whose provenance is unclear.

Report vulnerabilities according to [SECURITY.md](SECURITY.md). Review logs and screenshots for private paths or data before sharing.
