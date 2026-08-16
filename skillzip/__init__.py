"""SkillZip: evaluation-free skill compression by discovering reusable structure.

SkillZip shrinks a self-evolving agent's skill document by recovering the typed
*behavioral contract* it encodes and re-expressing that contract in the shortest
faithful form. Compression is **evaluation-free**: it reads only the skill text,
never tasks, rewards, trajectories, or verifiers.

Public entry points:

    from skillzip import compress_oneshot, zip_on_write

    compress_oneshot(skill)                 # Algorithm 1: one-shot compression
    zip_on_write(initial_text, patches, n)  # Algorithm 2: continual compression

Module layout (mirrors the paper's appendix):
    scanner   deterministic markdown blocks + stable provenance
    extract   schema-constrained contract recovery (+ deterministic fallback)
    relations typed retrieval + relation checks (hard blocking keys, Eq. 12)
    workflow  workflow graph + repeated-sequence mining (Re-Pair)
    optimize  minimum-cost covering selection (Eq. 4, cost tests 8-11)
    render    deterministic fixed-template rendering
    audit     compressed-text contract diff + conservative recovery
    online    Zip-on-Write continual compression + write-ahead log
    cost      practical length model (Eq. 7/13)
    contract  typed contract data model (Eq. 1-3)
    refs      intra-document reference integrity (anchors <-> references)
    canon     per-unit minimal faithful phrasing (Eq. 5/13)

Supporting modules: `skill` (the Skill artifact), `llm` (the only model-backed
dependency), `prompts` (templates for the model-assisted stages), `cli`.
"""
from .api import compress_oneshot, zip_on_write, DEFAULT_CFG
from .contract import Contract, Library, Unit, ZipState

__version__ = "1.0.0"

__all__ = ["compress_oneshot", "zip_on_write", "DEFAULT_CFG",
           "Contract", "Library", "Unit", "ZipState", "__version__"]
