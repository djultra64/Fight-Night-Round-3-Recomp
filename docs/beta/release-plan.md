# Beta 0.7 release plan

Project: Fight Night Round 3 Recomp. Original project work: djultra64 (DJ Ultra 64).

The approved release retains the original game clock and repaired Xenos runtime. It ships native graphics options, a private-data installer, a verified Linux package, English documentation, public source, and a GitHub prerelease tagged v0.7. Windows source support is documented separately from verified binaries.

- [x] Import the supported owned ISO into a fresh private folder and verify the complete extracted tree.
- [x] Package the compiled Linux host, matching runtime/plugin, pinned ISO extractor, scripts, and dependency licenses.
- [x] Curate the complete active source and English docs, excluding game data, generated guest sources, retired experiments, local logs, and credentials.
- [x] Run source/installer/package/CPU checks and inspect the release archive.
- [x] Verify repository author and committer identity resolves to djultra64.
- [x] Publish the public repository, GitHub Pages project page, and v0.7 prerelease with checksum files.
- [x] Verify the published repository, workflow results, release assets and page; record any external limitation honestly.

The local development workspace and earlier accepted baselines remain intact. Source publication uses an isolated release checkout so the development index and historical experiments are not accidentally committed.

## Publication evidence

- [Beta 0.7 release](https://github.com/djultra64/Fight-Night-Round-3-Recomp/releases/tag/v0.7): published prerelease, Linux archive and SHA256SUMS.
- [Source checks](https://github.com/djultra64/Fight-Night-Round-3-Recomp/actions/runs/39522880664): passed on the tagged source commit.
- [Project page deployment](https://github.com/djultra64/Fight-Night-Round-3-Recomp/actions/runs/39522880625): passed; published HTML matched the reviewed page byte for byte.
- Linux archive SHA-256: `d4806b72cc0e0d6dbcc9a1a3acaf79e0c0ccd522374e8b523bb5da9970681821`; GitHub reports the same uploaded asset digest.
- Windows binary validation remains outside this Linux beta release.
