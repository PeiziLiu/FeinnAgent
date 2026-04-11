"""FeinnAgent Skill system — reusable prompt templates with triggers and arguments.

Skills are markdown files with YAML frontmatter that define reusable workflows.
They can be invoked by triggers (e.g., "/commit") or via the Skill tool.

Example skill file (`.feinn/skills/commit.md`):
    ---
    name: commit
    description: Create a well-structured git commit
    triggers: ["/commit", "commit changes"]
    tools: ["Bash", "Read"]
    when_to_use: "Use when user wants to commit changes"
    argument_hint: "[optional context]"
    ---

    Review the git state and create a commit:
    1. Run `git status` and `git diff --staged`
    2. Analyze changes and write a concise commit message
    3. Execute `git commit -m "<message>"`

    User context: $ARGUMENTS
"""

from .builtin import register_builtin_skills
from .executor import execute_skill
from .loader import SkillDef, find_skill, load_skills, substitute_arguments

__all__ = [
    "SkillDef",
    "load_skills",
    "find_skill",
    "substitute_arguments",
    "execute_skill",
    "register_builtin_skills",
]
