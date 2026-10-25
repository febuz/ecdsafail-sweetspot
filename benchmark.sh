#!/usr/bin/env bash
# Fetch a complete immutable source tree, then use its unmodified evaluator.
set -euo pipefail

research_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case_name="${1:-q999}"
destination="${2:-${research_root}/.work/${case_name}}"
mode="${3:-}"
case "${mode}" in ""|--prepare-only) ;; *) echo "Unknown mode: ${mode}" >&2; exit 2 ;; esac
case "${case_name}" in
  q999|q1050) source_commit=f50ee007fdf84054fa44b71240c28a66a47aad8e ;;
  q1080_reference) source_commit=ea4ef4f6628339cfac747f4ca82df0d45ae12b6c ;;
  leader) source_commit=644857a7724560048a4ce23b3d8364a81010881c ;;
  *) echo "Choose q999, q1050, q1080_reference, or leader" >&2; exit 2 ;;
esac
if [[ -e "${destination}" ]]; then
  echo "Destination already exists; choose a new directory: ${destination}" >&2
  exit 2
fi
mkdir -p "$(dirname "${destination}")"
git clone --filter=blob:none --no-checkout https://github.com/Layr-Labs/ecdsafail-challenge "${destination}"
git -C "${destination}" checkout --detach "${source_commit}"
if [[ "${case_name}" == q1050 ]]; then
  git -C "${destination}" apply --check "${research_root}/experiments/q1050-width.patch"
  git -C "${destination}" apply "${research_root}/experiments/q1050-width.patch"
fi
printf 'Prepared %s at %s in %s\n' "${case_name}" "${source_commit}" "${destination}"
if [[ "${mode}" == --prepare-only ]]; then exit 0; fi
cd "${destination}"
cargo fetch --locked
exec ./benchmark.sh
