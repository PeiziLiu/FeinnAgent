"""Built-in skill templates that ship with FeinnAgent."""

from __future__ import annotations

from .loader import SkillTemplate, register_builtin_template

# ── /commit ────────────────────────────────────────────────────────────────

_COMMIT_TEMPLATE = """\
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

User context: $PARAMS
"""

# ── /review ────────────────────────────────────────────────────────────────

_REVIEW_TEMPLATE = """\
Review the code or pull request and provide structured feedback.

## Steps

1. Understand the scope:
   - If a PR number or URL is given in $PARAMS, use `gh pr view $PARAMS --patch` to get the diff.
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

User context: $PARAMS
"""

# ── /explain ───────────────────────────────────────────────────────────────

_EXPLAIN_TEMPLATE = """\
Explain the code in detail, suitable for a developer learning the codebase.

## Steps

1. Identify the target:
   - If $PARAMS contains a file path, read that file
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

User context: $PARAMS
"""

# ── /test ─────────────────────────────────────────────────────────────────

_TEST_TEMPLATE = """\
Generate comprehensive tests for the specified code.

## Steps

1. Identify the target:
   - If $PARAMS contains a file path, read that file
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

User context: $PARAMS
"""

# ── /doc ──────────────────────────────────────────────────────────────────

_DOC_TEMPLATE = """\
Generate or update documentation for the specified code.

## Steps

1. Identify the target:
   - If $PARAMS contains a file path, read that file
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

User context: $PARAMS
"""


def register_builtin_skills() -> None:
    """Register all built-in skill templates.

    Called during module initialization.
    """
    templates = [
        SkillTemplate(
            skill_id="commit",
            summary="Review staged changes and create a well-structured git commit",
            activators=["/commit"],
            allowed_tools=["Bash", "Read"],
            template=_COMMIT_TEMPLATE,
            origin="<builtin>",
            usage_context=(
                "Use when the user wants to commit changes. "
                "Activators: '/commit', 'commit changes', 'make a commit'."
            ),
            param_guide="[optional context]",
            param_names=[],
            visible_to_user=True,
            exec_mode="direct",
            origin_type="builtin",
        ),
        SkillTemplate(
            skill_id="review",
            summary="Review code changes or a pull request and provide structured feedback",
            activators=["/review", "/review-pr"],
            allowed_tools=["Bash", "Read", "Grep"],
            template=_REVIEW_TEMPLATE,
            origin="<builtin>",
            usage_context=(
                "Use when the user wants a code review. "
                "Activators: '/review', '/review-pr', 'review this PR'."
            ),
            param_guide="[PR number or URL]",
            param_names=["pr"],
            visible_to_user=True,
            exec_mode="direct",
            origin_type="builtin",
        ),
        SkillTemplate(
            skill_id="explain",
            summary="Explain code in detail for learning purposes",
            activators=["/explain"],
            allowed_tools=["Read", "Grep", "Glob"],
            template=_EXPLAIN_TEMPLATE,
            origin="<builtin>",
            usage_context=(
                "Use when the user wants to understand code. "
                "Activators: '/explain', 'explain this code'."
            ),
            param_guide="[file or symbol name]",
            param_names=[],
            visible_to_user=True,
            exec_mode="direct",
            origin_type="builtin",
        ),
        SkillTemplate(
            skill_id="test",
            summary="Generate comprehensive tests for code",
            activators=["/test"],
            allowed_tools=["Read", "Grep", "Glob", "Write", "Bash"],
            template=_TEST_TEMPLATE,
            origin="<builtin>",
            usage_context=(
                "Use when the user wants to create tests. "
                "Activators: '/test', 'write tests'."
            ),
            param_guide="[file or symbol name]",
            param_names=[],
            visible_to_user=True,
            exec_mode="direct",
            origin_type="builtin",
        ),
        SkillTemplate(
            skill_id="doc",
            summary="Generate or update documentation for code",
            activators=["/doc"],
            allowed_tools=["Read", "Grep", "Glob", "Write", "Edit"],
            template=_DOC_TEMPLATE,
            origin="<builtin>",
            usage_context=(
                "Use when the user wants documentation. "
                "Activators: '/doc', 'document this'."
            ),
            param_guide="[file or symbol name]",
            param_names=[],
            visible_to_user=True,
            exec_mode="direct",
            origin_type="builtin",
        ),
    ]

    for tmpl in templates:
        register_builtin_template(tmpl)
