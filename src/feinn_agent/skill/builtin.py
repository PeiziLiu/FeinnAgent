"""Built-in skills that ship with FeinnAgent."""

from __future__ import annotations

from .loader import SkillDef, register_builtin_skill

# ── /commit ────────────────────────────────────────────────────────────────

_COMMIT_PROMPT = """\
Review the current git state and create a well-structured commit.

## Steps

1. Run `git status` and `git diff --staged` to see what is staged.
   - If nothing is staged, run `git diff` to see unstaged changes, then stage relevant files.
2. Analyze the changes:
   - Summarize the nature of the change (feature, bug fix, refactor, docs, etc.)
   - Write a concise commit title (≤72 chars) focusing on *why*, not just *what*.
   - If multiple logical changes exist, ask the user whether to split them.
3. Create the commit:
   ```
   git commit -m "<title>"
   ```
   If additional context is needed, add a body separated by a blank line.
4. Print the commit hash and summary when done.

**Rules:**
- Never use `--no-verify`.
- Never commit files that likely contain secrets (.env, credentials, keys).
- Prefer imperative mood in the title: "Add X", "Fix Y", "Refactor Z".

User context: $ARGUMENTS
"""

# ── /review ────────────────────────────────────────────────────────────────

_REVIEW_PROMPT = """\
Review the code or pull request and provide structured feedback.

## Steps

1. Understand the scope:
   - If a PR number or URL is given in $ARGUMENTS, use `gh pr view $ARGUMENTS --patch` to get the diff.
   - Otherwise, use `git diff main...HEAD` (or `git diff HEAD~1`) for local changes.
2. Analyze the diff:
   - Correctness: Are there bugs, edge cases, or logic errors?
   - Security: Injection, auth issues, exposed secrets, unsafe operations?
   - Performance: N+1 queries, unnecessary allocations, blocking calls?
   - Style: Does it follow existing conventions in the codebase?
   - Tests: Are new behaviors tested? Do existing tests cover the change?
3. Write a structured review:
   ```
   ## Summary
   One-line overview of what the change does.

   ## Issues
   - [CRITICAL/MAJOR/MINOR] Description and location

   ## Suggestions
   - Nice-to-have improvements

   ## Verdict
   APPROVE / REQUEST CHANGES / COMMENT
   ```
4. If changes are needed, list specific file:line references.

User context: $ARGUMENTS
"""

# ── /explain ───────────────────────────────────────────────────────────────

_EXPLAIN_PROMPT = """\
Explain the code in detail, suitable for a developer learning the codebase.

## Steps

1. Identify the target:
   - If $ARGUMENTS contains a file path, read that file
   - If it contains a function/class name, search for it
   - If no argument given, ask the user what to explain

2. Analyze the code:
   - What is the overall purpose?
   - What are the key components (functions, classes, modules)?
   - What are the inputs and outputs?
   - Are there any important design patterns used?

3. Provide explanation:
   - Start with a high-level summary
   - Break down complex parts
   - Use analogies where helpful
   - Mention any gotchas or edge cases

User context: $ARGUMENTS
"""

# ── /test ─────────────────────────────────────────────────────────────────

_TEST_PROMPT = """\
Generate comprehensive tests for the specified code.

## Steps

1. Identify the target:
   - If $ARGUMENTS contains a file path, read that file
   - If it contains a function/class name, search for it

2. Analyze the code to understand:
   - What functionality needs testing?
   - What are the edge cases?
   - What are the expected inputs/outputs?

3. Generate tests:
   - Use the appropriate testing framework (pytest, jest, etc.)
   - Cover happy paths
   - Cover edge cases and error conditions
   - Add descriptive test names
   - Include docstrings explaining what each test verifies

4. Write tests to appropriate test file or create new one

User context: $ARGUMENTS
"""

# ── /doc ──────────────────────────────────────────────────────────────────

_DOC_PROMPT = """\
Generate or update documentation for the specified code.

## Steps

1. Identify the target:
   - If $ARGUMENTS contains a file path, read that file
   - If it contains a function/class name, search for it

2. Analyze the code:
   - What is the public API?
   - What are the key functions/classes?
   - What are the parameters and return values?
   - Are there any usage examples?

3. Generate documentation:
   - Add/update docstrings (Google/NumPy style)
   - Add type hints if missing
   - Create/update README if needed
   - Add usage examples

User context: $ARGUMENTS
"""


def register_builtin_skills() -> None:
    """Register all built-in skills.

    Called during module initialization.
    """
    skills = [
        SkillDef(
            name="commit",
            description="Review staged changes and create a well-structured git commit",
            triggers=["/commit"],
            tools=["Bash", "Read"],
            prompt=_COMMIT_PROMPT,
            file_path="<builtin>",
            when_to_use=(
                "Use when the user wants to commit changes. "
                "Triggers: '/commit', 'commit changes', 'make a commit'."
            ),
            argument_hint="[optional context]",
            arguments=[],
            user_invocable=True,
            context="inline",
            source="builtin",
        ),
        SkillDef(
            name="review",
            description="Review code changes or a pull request and provide structured feedback",
            triggers=["/review", "/review-pr"],
            tools=["Bash", "Read", "Grep"],
            prompt=_REVIEW_PROMPT,
            file_path="<builtin>",
            when_to_use="Use when the user wants a code review. Triggers: '/review', '/review-pr', 'review this PR'.",
            argument_hint="[PR number or URL]",
            arguments=["pr"],
            user_invocable=True,
            context="inline",
            source="builtin",
        ),
        SkillDef(
            name="explain",
            description="Explain code in detail for learning purposes",
            triggers=["/explain"],
            tools=["Read", "Grep", "Glob"],
            prompt=_EXPLAIN_PROMPT,
            file_path="<builtin>",
            when_to_use="Use when the user wants to understand code. Triggers: '/explain', 'explain this code'.",
            argument_hint="[file or symbol name]",
            arguments=[],
            user_invocable=True,
            context="inline",
            source="builtin",
        ),
        SkillDef(
            name="test",
            description="Generate comprehensive tests for code",
            triggers=["/test"],
            tools=["Read", "Grep", "Glob", "Write", "Bash"],
            prompt=_TEST_PROMPT,
            file_path="<builtin>",
            when_to_use="Use when the user wants to create tests. Triggers: '/test', 'write tests'.",
            argument_hint="[file or symbol name]",
            arguments=[],
            user_invocable=True,
            context="inline",
            source="builtin",
        ),
        SkillDef(
            name="doc",
            description="Generate or update documentation for code",
            triggers=["/doc"],
            tools=["Read", "Grep", "Glob", "Write", "Edit"],
            prompt=_DOC_PROMPT,
            file_path="<builtin>",
            when_to_use="Use when the user wants documentation. Triggers: '/doc', 'document this'.",
            argument_hint="[file or symbol name]",
            arguments=[],
            user_invocable=True,
            context="inline",
            source="builtin",
        ),
    ]

    for skill in skills:
        register_builtin_skill(skill)


# Auto-register on import
register_builtin_skills()
