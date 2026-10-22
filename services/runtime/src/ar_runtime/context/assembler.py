"""Re-export. The assembler lives in the domain so chat can hash prompts."""

from ar_domain.prompts.assembler import PromptBundle, build_prompt

__all__ = ["PromptBundle", "build_prompt"]
