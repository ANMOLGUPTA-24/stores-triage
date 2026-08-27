#!/usr/bin/env bash
# Start TrueForge with a local sandbox that can actually reach the network.
#
# Upstream bug (TrueForge 0.1.4 + @anthropic-ai/sandbox-runtime 0.0.71, Linux):
# the sandbox talks to the outside world through a filtering proxy reached over a
# Unix socket that SRT creates at `os.tmpdir()/claude-http-<id>.sock`. But
# TrueForge's Linux allow-read list (ALLOW_READ_BY_PLATFORM.linux) is
#
#     /usr/bin /bin /usr/sbin /sbin /lib /lib64 /usr/lib /usr/lib64
#     /usr/local /etc /dev /proc /sys  + the SRT vendor dir
#
# and does NOT include /tmp. So the sandboxed process cannot see the socket, every
# outbound connection dies with "Proxy CONNECT aborted", and the very first thing
# the sandbox does - `pip install pydantic` into its venv - always fails. On Linux
# that makes the local sandbox unusable, which also takes the skill with it,
# because skills require a sandbox.
#
# We do not patch the package. TrueForge already adds one more path to the
# allow-read list at runtime: the Code Mode socket parent, which it computes as
# `os.tmpdir()/tf_cms` and then realpath()s. So if TMPDIR is a directory we own
# and `tf_cms` inside it resolves back to that same directory, the allowed path
# becomes TMPDIR itself - and the proxy socket, which lives in TMPDIR, falls
# inside it.
#
# The link has to be made *after* the server boots: TrueForge rm -rf's
# `$TMPDIR/tf_cms` and recreates it as a real directory on startup, and only
# reads it later, when the first sandbox is created.
#
# This is a workaround for specific versions, so the version is pinned. If you
# raise it, re-verify that the sandbox still comes up before trusting a run:
# drive SRT's CLI with TrueForge's filesystem policy and check that a request to
# pypi.org returns 200 rather than "Proxy CONNECT aborted".

set -euo pipefail

TFY_VERSION="${TFY_VERSION:-0.1.4}"           # the version this workaround was verified against
TFY_SRT_VERIFIED="0.0.71"                     # sandbox-runtime it was verified against
TFY_TMP="${TFY_TMP:-$HOME/.tfy-tmp}"          # must stay short: Unix socket paths cap at ~108 bytes
WHEELS="${WHEELS:-$HOME/.trueforge-wheels}"
LOG="${LOG:-$HOME/.tfy-harness.log}"
BASE_URL="${TRUEFORGE_BASE_URL:-http://localhost:8790}"

command -v npx >/dev/null || { echo "npx not found (install Node.js)" >&2; exit 1; }
command -v curl >/dev/null || { echo "curl not found (apt install curl)" >&2; exit 1; }

ready() { curl -sf -o /dev/null --max-time 2 "$BASE_URL/api/v1/capabilities"; }

if ready; then
  echo "a harness is already answering on $BASE_URL — stop it first" >&2
  exit 1
fi

mkdir -p "$TFY_TMP"
chmod 700 "$TFY_TMP"

TMPDIR="$TFY_TMP" TMP="$TFY_TMP" TEMP="$TFY_TMP" \
PIP_NO_INDEX=1 PIP_FIND_LINKS="$WHEELS" \
  nohup npx "@truefoundry/trueforge@${TFY_VERSION}" > "$LOG" 2>&1 &
harness_pid=$!

# Until the symlink is in place the harness is not usable, so any early exit has
# to take it with us rather than leave it to bind the port after we have given up.
cleanup() { kill "$harness_pid" 2>/dev/null || true; wait "$harness_pid" 2>/dev/null || true; }
trap cleanup EXIT

for _ in $(seq 1 60); do
  ready && break
  kill -0 "$harness_pid" 2>/dev/null || { echo "harness exited during startup; see $LOG" >&2; exit 1; }
  sleep 1
done
ready || { echo "harness did not answer on $BASE_URL within 60s; see $LOG" >&2; exit 1; }

# Point tf_cms back at its own parent, so the allow-read path covers the socket.
rm -rf "$TFY_TMP/tf_cms"
ln -s "$TFY_TMP" "$TFY_TMP/tf_cms"

trap - EXIT

srt_pkg=$(find "$HOME/.npm/_npx" -path '*@anthropic-ai/sandbox-runtime/package.json' -print -quit 2>/dev/null || true)
if [ -n "$srt_pkg" ]; then
  srt_version=$(node -p "require('$srt_pkg').version" 2>/dev/null || echo unknown)
  if [ "$srt_version" != "$TFY_SRT_VERIFIED" ]; then
    echo "warning: sandbox-runtime is $srt_version, workaround verified against $TFY_SRT_VERIFIED" >&2
    echo "         re-verify the sandbox comes up before trusting a run" >&2
  fi
fi

echo "harness up on $BASE_URL  (trueforge $TFY_VERSION)"
echo "  TMPDIR      $TFY_TMP"
echo "  tf_cms   -> $(readlink -f "$TFY_TMP/tf_cms")"
echo "  log         $LOG"
