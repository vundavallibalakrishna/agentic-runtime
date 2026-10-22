"""Context assembly. Spec: docs/03-specs/07-agent-runtime.md §4."""

from ar_domain.prompts.assembler import PromptBundle, build_prompt
from ar_domain.skills.sections import capabilities_block, loaded_skills_block

__all__ = ["PromptBundle", "build_prompt", "capabilities_block", "loaded_skills_block"]
