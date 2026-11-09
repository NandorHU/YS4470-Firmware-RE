# YS-4470 account migration — 2026-11-09

This is the owner-requested transfer entry point for a new coordinating agent.
It supplements the ongoing project; it does not restart the reverse engineering.

1. Give the new agent [NEXT_AGENT_PROMPT_HU.txt](NEXT_AGENT_PROMPT_HU.txt).
2. Read [AGENT_HANDOFF.md](AGENT_HANDOFF.md) for the exact research checkpoint,
   evidence, limits and next bounded task.
3. Use [TOOLING_AND_SETUP.md](TOOLING_AND_SETUP.md) for tools, local model,
   setup and offline validation commands.
4. Read [ACCOUNT_AND_AUTOMATION.md](ACCOUNT_AND_AUTOMATION.md) before moving
   accounts or enabling a second daily automation.
5. [ARTIFACTS.json](ARTIFACTS.json) is a machine-readable input/evidence index.

The public development branch is `re/2026-11-04-pyghidra-fel`; `main` is older.
The last **analysis** commit before these migration documents is
`a2e5e7ebd2f661f37f88507f55a62a14c5df3f9f` (database 62 records, registry revision17).
The local transfer kit's TRANSFER_MANIFEST.json records the subsequent handoff
documentation commit and all archive checksums. Never confuse that documentation
commit with an additional firmware experiment.

The local kit includes a full public Git bundle, a source ZIP including both
approved original application images, verified historical beta.2 installer,
environment inventory and offline verifier. It excludes credentials, model
weights, personal full-flash/calibration backups and unpublished SDK archives.
The new agent can begin offline from the bundle; package installation and
upstream coordination still need their own permissions/network connection.

**Release availability changed:** the beta.2 release ID and tag API both returned
404 during migration, although its Git tag/source still exist. A previously
published/download-verified Windows ZIP is retained in the local kit. Its hash
is documented, and it was not republished. Cause unknown. The unpublished beta.1
draft is not a replacement. See AGENT_HANDOFF.md for exact identities and limits.

No physical device, main branch, repository ownership, account credentials or
automation schedule was changed by preparing this handoff. The project remains
incomplete; there is no defensible overall completion percentage.
