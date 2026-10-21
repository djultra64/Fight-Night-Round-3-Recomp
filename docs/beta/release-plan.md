# Beta 0.7 release plan

Project: Fight Night Round 3 Recomp. Original project work: djultra64 (DJ Ultra 64).

The approved release retains the original game clock and repaired Xenos runtime. It ships native graphics options, a private-data installer, a verified Linux package, English documentation, public source, and a GitHub prerelease tagged v0.7. Windows source support is documented separately from verified binaries.

- [x] Import the supported owned ISO into a fresh private folder and verify the complete extracted tree.
- [x] Package the compiled Linux host, matching runtime/plugin, pinned ISO extractor, scripts, and dependency licenses.
- [x] Curate the complete active source and English docs, excluding game data, generated guest sources, retired experiments, local logs, and credentials.
- [x] Run source/installer/package/CPU checks and inspect the release archive.
- [x] Verify repository author and committer identity resolves to djultra64.
- [ ] Publish the public repository, GitHub Pages project page, and v0.7 prerelease with checksum files.
- [ ] Verify the published repository, workflow results, release assets and page; record any external limitation honestly.

The local development workspace and earlier accepted baselines remain intact. Source publication uses an isolated release checkout so the development index and historical experiments are not accidentally committed.
