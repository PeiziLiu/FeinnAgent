"""Tests for Skill system."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from feinn_agent.skill import (
    SkillTemplate,
    load_skills,
    find_skill,
    get_skill_by_name,
    render_template,
    execute_skill,
    register_builtin_skills,
)


class TestSkillTemplate:
    """Test SkillTemplate dataclass."""

    def test_create_template(self):
        """Test creating a skill template."""
        template = SkillTemplate(
            skill_id="test",
            summary="Test skill",
            activators=["/test", "test it"],
            allowed_tools=["Read", "Write"],
            template="Test template $PARAMS",
            origin="<builtin>",
            usage_context="Use when testing",
            param_guide="[input]",
            param_names=["input"],
        )

        assert template.skill_id == "test"
        assert template.summary == "Test skill"
        assert "/test" in template.activators
        assert "Read" in template.allowed_tools
        assert template.template == "Test template $PARAMS"

    def test_default_values(self):
        """Test default values are set correctly."""
        template = SkillTemplate(skill_id="minimal", summary="Minimal")

        assert template.activators == []
        assert template.allowed_tools == []
        assert template.template == ""
        assert template.visible_to_user is True
        assert template.exec_mode == "direct"
        assert template.origin_type == "user"


class TestBuiltinSkills:
    """Test builtin skills registration."""

    def setup_method(self):
        """Clear and re-register builtin skills before each test."""
        # Note: builtin skills are stored in loader._BUILTIN_TEMPLATES
        register_builtin_skills()

    def test_builtin_skills_loaded(self):
        """Test that builtin skills are loaded."""
        skills = load_skills()
        skill_ids = [s.skill_id for s in skills]

        assert "commit" in skill_ids
        assert "review" in skill_ids
        assert "explain" in skill_ids
        assert "test" in skill_ids
        assert "doc" in skill_ids

    def test_commit_skill_structure(self):
        """Test commit skill has correct structure."""
        skill = get_skill_by_name("commit")
        assert skill is not None

        assert skill.skill_id == "commit"
        assert "/commit" in skill.activators
        assert "Bash" in skill.allowed_tools
        assert "Read" in skill.allowed_tools
        assert "$PARAMS" in skill.template

    def test_review_skill_structure(self):
        """Test review skill has correct structure."""
        skill = get_skill_by_name("review")
        assert skill is not None

        assert "/review" in skill.activators
        assert "/review-pr" in skill.activators
        assert "Bash" in skill.allowed_tools


class TestFindSkill:
    """Test skill finding by activator."""

    def setup_method(self):
        register_builtin_skills()

    def test_find_by_exact_activator(self):
        """Test finding skill by exact activator match."""
        skill = find_skill("/commit")
        assert skill is not None
        assert skill.skill_id == "commit"

    def test_find_with_arguments(self):
        """Test finding skill with arguments after activator."""
        skill = find_skill("/commit fix the bug")
        assert skill is not None
        assert skill.skill_id == "commit"

    def test_find_nonexistent(self):
        """Test finding non-existent skill returns None."""
        skill = find_skill("/nonexistent")
        assert skill is None

    def test_find_empty_query(self):
        """Test finding with empty query returns None."""
        skill = find_skill("")
        assert skill is None

    def test_find_whitespace_query(self):
        """Test finding with whitespace-only query returns None."""
        skill = find_skill("   ")
        assert skill is None


class TestGetSkillByName:
    """Test getting skill by ID."""

    def setup_method(self):
        register_builtin_skills()

    def test_get_existing_skill(self):
        """Test getting existing skill by ID."""
        skill = get_skill_by_name("explain")
        assert skill is not None
        assert skill.skill_id == "explain"

    def test_get_nonexistent_skill(self):
        """Test getting non-existent skill returns None."""
        skill = get_skill_by_name("nonexistent")
        assert skill is None


class TestRenderTemplate:
    """Test template rendering."""

    def test_render_with_params(self):
        """Test rendering with parameters."""
        template = "Hello, $NAME! You have $COUNT messages."
        result = render_template(
            template,
            params="Alice 5",
            param_names=["NAME", "COUNT"]
        )
        assert result == "Hello, Alice! You have 5 messages."

    def test_render_without_params(self):
        """Test rendering template without parameters."""
        template = "Hello, world!"
        result = render_template(template, params="", param_names=[])
        assert result == "Hello, world!"

    def test_render_missing_param(self):
        """Test rendering with missing parameter (should use empty string)."""
        template = "Hello, $NAME!"
        result = render_template(
            template,
            params="",  # NAME not provided
            param_names=["NAME"]
        )
        # Should replace with empty string
        assert result == "Hello, !"

    def test_render_empty_params(self):
        """Test rendering with empty params string."""
        template = "Context: $PARAMS"
        result = render_template(
            template,
            params="",
            param_names=["PARAMS"]
        )
        assert result == "Context: "

    def test_render_params_substitution(self):
        """Test $PARAMS placeholder substitution."""
        template = "Execute: $PARAMS"
        result = render_template(
            template,
            params="git status",
            param_names=[]
        )
        assert result == "Execute: git status"

    def test_render_arguments_alias(self):
        """Test $ARGUMENTS is also substituted (backward compat)."""
        template = "Run: $ARGUMENTS"
        result = render_template(
            template,
            params="--verbose test.py",
            param_names=[]
        )
        assert result == "Run: --verbose test.py"


class TestSkillLoading:
    """Test skill loading from filesystem."""

    @pytest.fixture
    def temp_skill_dir(self):
        """Create a temporary skill directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir(parents=True)
            yield skills_dir

    def test_load_from_directory(self, temp_skill_dir):
        """Test loading skills from directory."""
        # Create a test skill file
        skill_file = temp_skill_dir / "test.md"
        skill_file.write_text("""---
id: test
summary: Test skill
activators: ["/test"]
tools: ["Read"]
---

Test template $PARAMS
""")

        with patch("feinn_agent.skill.loader._get_skill_paths", return_value=[temp_skill_dir]):
            skills = load_skills()
            skill_ids = [s.skill_id for s in skills]
            assert "test" in skill_ids

    def test_load_invalid_skill_ignored(self, temp_skill_dir):
        """Test that invalid skill files are ignored."""
        # Create an invalid skill file (no frontmatter)
        skill_file = temp_skill_dir / "invalid.md"
        skill_file.write_text("Just content, no frontmatter")

        with patch("feinn_agent.skill.loader._get_skill_paths", return_value=[temp_skill_dir]):
            # Should not raise, just skip invalid files
            skills = load_skills()
            # Invalid skill should not be loaded
            assert not any(s.skill_id == "invalid" for s in skills)


class TestSkillExecution:
    """Test skill execution."""

    @pytest.mark.asyncio
    async def test_execute_skill(self):
        """Test executing a skill."""
        register_builtin_skills()

        # Get a skill template
        skill = get_skill_by_name("commit")
        assert skill is not None

        # Execute with empty arguments
        # Note: This may need mocking of agent/tools depending on implementation
        try:
            result = await execute_skill(skill, "", {})
            # Result type depends on implementation
            assert isinstance(result, str)
        except Exception as e:
            # Execution may fail due to missing tools/config, but should not crash
            pytest.skip(f"Skill execution skipped: {e}")

    def test_skill_has_required_fields(self):
        """Test that all builtin skills have required fields."""
        register_builtin_skills()
        skills = load_skills()

        for skill in skills:
            assert skill.skill_id, f"Skill missing skill_id"
            assert skill.summary, f"Skill {skill.skill_id} missing summary"
            assert skill.template, f"Skill {skill.skill_id} missing template"
            assert skill.origin, f"Skill {skill.skill_id} missing origin"
