"""FeinnAgent Skill system — reusable prompt templates with activators and parameters.

Skill templates are markdown files with YAML frontmatter that define reusable workflows.
They can be invoked by activators (e.g., "/commit") or via the Skill tool.

Example skill template file (`.feinn/skills/commit.md`):
    ---
    id: commit
    summary: Create a well-structured git commit
    activators: ["/commit", "commit changes"]
    tools: ["Bash", "Read"]
    usage-context: "Use when user wants to commit changes"
    param-guide: "[optional context]"
    ---

    Review the git state and create a commit:
    1. Run `git status` and `git diff --staged`
    2. Analyze changes and write a concise commit message
    3. Execute `git commit -m "<message>"`

    User context: $PARAMS
"""

from .builtin import register_builtin_skills
from .executor import execute_skill
from .loader import (
    SkillTemplate,
    find_skill,
    get_skill_by_name,
    load_skills,
    render_template,
)

__all__ = [
    "SkillTemplate",
    "load_skills",
    "find_skill",
    "get_skill_by_name",
    "render_template",
    "execute_skill",
    "register_builtin_skills",
]
