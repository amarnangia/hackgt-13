#!/bin/bash
# One-time setup for the two secrets. Input is hidden, and nothing is printed or committed:
#   MODEL_API_KEY  -> .env in the repo (gitignored)
#   HuggingFace    -> ~/.cache/huggingface/token (via `hf auth login`)
# Usage: bash tools/setup_keys.sh
set -e
cd "$(dirname "$0")/.."

if grep -q '^MODEL_API_KEY=.\+' .env 2>/dev/null; then
  echo "Muse key: already in .env (delete that line to replace it)."
else
  read -rsp "Paste your Muse (Meta Model API) key, then press Enter: " KEY; echo
  [ -n "$KEY" ] || { echo "No key entered."; exit 1; }
  printf 'MODEL_API_KEY=%s\n' "$KEY" >> .env
  chmod 600 .env
  echo "Muse key saved to .env"
fi

if [ -s ~/.cache/huggingface/token ]; then
  echo "HuggingFace: already logged in."
else
  read -rsp "Paste your HuggingFace READ token (huggingface.co/settings/tokens), then press Enter: " HF; echo
  [ -n "$HF" ] || { echo "No token entered."; exit 1; }
  .venv-translate/bin/hf auth login --token "$HF" 2>&1 | tail -2
fi
echo "Done."
