#!/usr/bin/env bash
# Download NCERT Class VIII Mathematics — Ganita Prakash Part I & II (NCF-SE 2023),
# chapter by chapter, from NCERT's official e-textbook portal into data/pdfs/.
#
# Usage:  data/fetch_ncert_pdfs.sh          (from the project root, or anywhere)
#
# The PDFs are NCERT copyright, so they are gitignored; run this to get them locally.
# Fallbacks if ncert.nic.in is down: diksha.gov.in or the ePathshala app (both official).
set -euo pipefail

BASE="https://ncert.nic.in/textbook/pdf"
OUT="$(cd "$(dirname "$0")" && pwd)/pdfs"
mkdir -p "$OUT"

# NCERT file code -> local filename
FILES=(
  "hegp1ps part1_ch00_prelims"
  "hegp101 part1_ch01_a_square_and_a_cube"
  "hegp102 part1_ch02_power_play"
  "hegp103 part1_ch03_a_story_of_numbers"
  "hegp104 part1_ch04_quadrilaterals"
  "hegp105 part1_ch05_number_play"
  "hegp106 part1_ch06_we_distribute_yet_things_multiply"
  "hegp107 part1_ch07_proportional_reasoning_1"
  "hegp2ps part2_ch00_prelims"
  "hegp201 part2_ch01_fractions_in_disguise"
  "hegp202 part2_ch02_the_baudhayana_pythagoras_theorem"
  "hegp203 part2_ch03_proportional_reasoning_2"
  "hegp204 part2_ch04_exploring_some_geometric_themes"
  "hegp205 part2_ch05_tales_by_dots_and_lines"
  "hegp206 part2_ch06_algebra_play"
  "hegp207 part2_ch07_area"
)

# ncert.nic.in does not send its Let's Encrypt intermediate (YE1), so plain curl fails
# with "unable to get local issuer certificate". Build a CA file = system roots + YE1.
CURL_TLS=()
if ! curl -sSfI -m 30 -o /dev/null "$BASE/hegp101.pdf" 2>/dev/null; then
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  ROOTS="${SSL_CERT_FILE:-${CURL_CA_BUNDLE:-}}"
  for c in /etc/ssl/certs/ca-certificates.crt /etc/pki/tls/certs/ca-bundle.crt \
           /etc/ssl/cert.pem /opt/homebrew/etc/ca-certificates/cert.pem; do
    [[ -z "$ROOTS" && -f "$c" ]] && ROOTS="$c"
  done
  [[ -n "$ROOTS" ]] || { echo "No system CA bundle found; set SSL_CERT_FILE." >&2; exit 1; }
  curl -sSf -m 30 -o "$TMP/ye1.pem" https://letsencrypt.org/certs/gen-y/int-ye1.pem
  cat "$ROOTS" "$TMP/ye1.pem" > "$TMP/ca.pem"
  CURL_TLS=(--cacert "$TMP/ca.pem")
fi

for entry in "${FILES[@]}"; do
  read -r code name <<<"$entry"
  dest="$OUT/$name.pdf"
  if [[ -s "$dest" ]]; then echo "skip  $name.pdf"; continue; fi
  echo "get   $name.pdf"
  curl "${CURL_TLS[@]}" -sSf -m 300 --retry 3 -A "Mozilla/5.0" -o "$dest.part" "$BASE/$code.pdf"
  head -c 4 "$dest.part" | grep -q '%PDF' || { echo "not a PDF: $code" >&2; rm -f "$dest.part"; exit 1; }
  mv "$dest.part" "$dest"
done
echo "Done -> $OUT"
