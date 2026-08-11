#!/usr/bin/env python3
"""Offline provider-auth fixture used by container smoke checks."""

from __future__ import annotations

import json
import sys

args = sys.argv[1:]

if args == ["login", "--device-auth"]:
    print("Open https://auth.openai.com/codex/device", flush=True)
    raise SystemExit(0)
if args == ["login", "status"]:
    print("Logged in using fixture")
    raise SystemExit(0)
if args == ["logout"]:
    print("Logged out")
    raise SystemExit(0)

if args == ["auth", "login", "--claudeai"]:
    print("Open https://claude.ai/oauth/authorize?code=fixture", flush=True)
    if sys.stdin.readline().strip() != "fixture-code":
        raise SystemExit(9)
    print("Authorized", flush=True)
    raise SystemExit(0)
if args == ["auth", "status", "--json"]:
    print(json.dumps({"loggedIn": True, "authMethod": "fixture"}))
    raise SystemExit(0)
if args == ["auth", "logout"]:
    print("Logged out")
    raise SystemExit(0)

print(f"unexpected argv: {args!r}", file=sys.stderr)
raise SystemExit(8)
