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

set -euo pipefail

TFY_TMP="${TFY_TMP:-$HOME/.tfy-tmp}"          # must stay short: Unix socket paths cap at ~108 bytes
WHEELS="${WHEELS:-$HOME/.trueforge-wheels}"
LOG="${LOG:-$HOME/.tfy-harness.log}"

mkdir -p "$TFY_TMP"
chmod 700 "$TFY_TMP"

if ss -ltn 2>/dev/null | grep -q ':8790 '; then
  echo "harness already listening on 8790 — stop it first" >&2
  exit 1
fi

TMPDIR="$TFY_TMP" TMP="$TFY_TMP" TEMP="$TFY_TMP" \
PIP_NO_INDEX=1 PIP_FIND_LINKS="$WHEELS" \
  nohup npx @truefoundry/trueforge > "$LOG" 2>&1 &

for _ in $(seq 1 60); do
  ss -ltn 2>/dev/null | grep -q ':8790 ' && break
  sleep 1
done
ss -ltn 2>/dev/null | grep -q ':8790 ' || { echo "harness did not come up; see $LOG" >&2; exit 1; }

# Point tf_cms back at its own parent, so the allow-read path covers the socket.
rm -rf "$TFY_TMP/tf_cms"
ln -s "$TFY_TMP" "$TFY_TMP/tf_cms"

echo "harness up on :8790"
echo "  TMPDIR      $TFY_TMP"
echo "  tf_cms   -> $(readlink -f "$TFY_TMP/tf_cms")"
echo "  log         $LOG"
