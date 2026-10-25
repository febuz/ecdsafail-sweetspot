# Circuit sources

The upstream point-addition circuits span multiple Rust modules and data tables. A single `.rs` file would not reproduce them. [manifest.json](manifest.json) pins each complete upstream commit and records which metrics are official and which experiments remain unvalidated.

The repository-level runner fetches the full pinned source into a new destination, applies a declared editable-path patch where present, and runs the upstream harness unchanged:

```bash
./benchmark.sh q999 /tmp/ecdsa-q999-reproduction
./benchmark.sh q1050 /tmp/ecdsa-q1050-experiment
./benchmark.sh q1080_reference /tmp/ecdsa-q1080-reference
```

The destination must not already exist. Add `--prepare-only` as a third argument to fetch and check the source without running a long benchmark. Rust, Cargo, Git, and a C linker must already be installed. No API key is required for a local run. The runner does not submit to ECDSA.fail.
