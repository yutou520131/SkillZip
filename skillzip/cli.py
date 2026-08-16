#!/usr/bin/env python3
"""SkillZip command-line interface (paper Appendix B.1).

    skillzip compress SKILL.md --state skillzip.json --output SKILL.compact.md
    skillzip update  skillzip.json PATCH.md --output SKILL.md
    skillzip audit   SKILL.compact.md skillzip.json
    skillzip inspect skillzip.json --show-savings

The CLI writes through temporary files and replaces persistent state only after
schema/coverage validation and rendering succeed (B.1). Compression never reads
tasks, rewards, or verifiers.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Make the package importable when this file is run as a plain script.
# (this module lives at <root>/skillzip/cli.py -> add <root> to sys.path)
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from skillzip.skill import Skill                      # noqa: E402
from skillzip import compress_oneshot, zip_on_write, DEFAULT_CFG  # noqa: E402
from skillzip.contract import ZipState                # noqa: E402
from skillzip import online, render, extract, optimize, audit as auditmod  # noqa: E402


def _client(args):
    if args.no_llm:
        return None
    try:
        from skillzip.llm import LLMClient
        key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not key:
            return None
        return LLMClient(model=args.model, backend="real",
                         base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                         cache_dir=args.cache, timeout_s=90, enable_thinking=False)
    except Exception:
        return None


def _atomic_write(path: str, text: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def cmd_compress(args):
    skill = Skill.load(args.skill, os.path.splitext(os.path.basename(args.skill))[0])
    cli = _client(args)
    comp, report = compress_oneshot(skill, cli=cli)
    _atomic_write(args.output, comp.to_markdown())
    if args.state:
        contract = extract.extract_contract(comp.to_markdown(), cli=cli)
        lib = optimize.min_cost_cover(contract, cli=cli)
        ZipState(name=skill.name, library=lib).save(args.state)
    print(json.dumps({k: v for k, v in report.items() if k != "savings"}, indent=2))


def cmd_update(args):
    cli = _client(args)
    state = ZipState.load(args.state)
    patch_text = open(args.patch, encoding="utf-8").read()
    new_state, body = online.zip_update(state, patch_text, cli=cli)
    _atomic_write(args.output, Skill(name=state.name, body=body).to_markdown())
    new_state.save(args.state)                          # atomic commit last
    print(json.dumps({"name": state.name,
                      "units": len(new_state.library.units),
                      "residual": len(new_state.library.residual),
                      "compressed_tokens": Skill(name=state.name, body=body).tokens},
                     indent=2))


def cmd_audit(args):
    cli = _client(args)
    body = Skill.load(args.skill, "skill").body
    state = ZipState.load(args.state)
    from skillzip.contract import Contract
    source = Contract(units=state.library.all_units())
    _, restored = auditmod.audit_and_restore(body, state.library, source, cli=cli)
    print(json.dumps({"missing_restored": restored,
                      "ok": len(restored) == 0}, indent=2))


def cmd_inspect(args):
    state = ZipState.load(args.state)
    print(f"skill: {state.name}")
    print(f"units: {len(state.library.units)}  residual: {len(state.library.residual)}"
          f"  procedures: {len(state.library.procedures)}")
    if args.show_savings:
        for entry in state.log:
            print(json.dumps(entry))


def main():
    ap = argparse.ArgumentParser(prog="skillzip")
    ap.add_argument("--model", default="qwen3.7-max")
    ap.add_argument("--cache", default=".skillzip_cache")
    ap.add_argument("--no-llm", action="store_true",
                    help="use the deterministic parser/relation checker only")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compress"); c.add_argument("skill")
    c.add_argument("--state", default=""); c.add_argument("--output", required=True)
    c.set_defaults(fn=cmd_compress)

    u = sub.add_parser("update"); u.add_argument("state"); u.add_argument("patch")
    u.add_argument("--output", required=True); u.set_defaults(fn=cmd_update)

    a = sub.add_parser("audit"); a.add_argument("skill"); a.add_argument("state")
    a.set_defaults(fn=cmd_audit)

    i = sub.add_parser("inspect"); i.add_argument("state")
    i.add_argument("--show-savings", action="store_true"); i.set_defaults(fn=cmd_inspect)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
