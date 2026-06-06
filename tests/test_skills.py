"""Tests for FeinnAgent skills functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from feinn_agent.tools.skills import (
    _skill_tool,
    _skill_list_tool,
    _skill_manage_tool,
    SKILL_TOOL_DEF,
    SKILL_LIST_TOOL_DEF,
    SKILL_MANAGE_TOOL_DEF,
)


class TestSkillTool:
    """Test _skill_tool handler."""

    @pytest.mark.asyncio
    @patch("feinn_agent.tools.skills.get_skill_by_name")
    @patch("feinn_agent.tools.skills.find_skill")
    @patch("feinn_agent.tools.skills.render_template")
    async def test_skill_tool(self, mock_render, mock_find, mock_get):
        mock_template = Mock()
        mock_template.skill_id = "test-skill"
        mock_template.template = "Test template $PARAMS"
        mock_template.param_names = []

        mock_get.return_value = mock_template
        mock_find.return_value = None
        mock_render.return_value = "Rendered test template"

        result = await _skill_tool({"id": "test-skill", "params": "test params"}, {})
        assert "[Skill: test-skill]" in result
        assert "Rendered test template" in result

        result = await _skill_tool({"name": "test-skill", "args": "test args"}, {})
        assert "[Skill: test-skill]" in result

        result = await _skill_tool({}, {})
        assert "Error: skill id is required" in result

        mock_get.return_value = None
        mock_find.return_value = None
        with patch("feinn_agent.tools.skills.load_skills") as mock_load:
            mock_load.return_value = []
            result = await _skill_tool({"id": "nonexistent"}, {})
            assert "Error: skill 'nonexistent' not found" in result

    @pytest.mark.asyncio
    @patch("feinn_agent.tools.skills.load_skills")
    async def test_skill_list_tool(self, mock_load):
        mock_template1 = Mock()
        mock_template1.skill_id = "test-skill-1"
        mock_template1.activators = ["/test1"]
        mock_template1.summary = "Test skill 1"
        mock_template1.param_guide = "param1, param2"
        mock_template1.usage_context = "When you need to test"
        mock_template1.allowed_tools = ["Read", "Write"]
        mock_template1.exec_mode = "direct"
        mock_template1.visible_to_user = True

        mock_template2 = Mock()
        mock_template2.skill_id = "test-skill-2"
        mock_template2.activators = ["/test2"]
        mock_template2.summary = "Test skill 2"
        mock_template2.param_guide = ""
        mock_template2.usage_context = ""
        mock_template2.allowed_tools = []
        mock_template2.exec_mode = "direct"
        mock_template2.visible_to_user = True

        mock_template3 = Mock()
        mock_template3.visible_to_user = False

        mock_load.return_value = [mock_template1, mock_template2, mock_template3]

        result = await _skill_list_tool({}, {})
        assert "Available skill templates:" in result
        assert "test-skill-1" in result
        assert "test-skill-2" in result
        assert "Test skill 1" in result
        assert "Test skill 2" in result

        mock_load.return_value = []
        result = await _skill_list_tool({}, {})
        assert "No skills available" in result

    def test_skill_tool_def(self):
        assert SKILL_TOOL_DEF.name == "Skill"
        assert "Invoke a named skill template" in SKILL_TOOL_DEF.description
        assert "id" in SKILL_TOOL_DEF.input_schema["properties"]
        assert "params" in SKILL_TOOL_DEF.input_schema["properties"]

    def test_skill_list_tool_def(self):
        assert SKILL_LIST_TOOL_DEF.name == "SkillList"
        assert "List all available skill templates" in SKILL_LIST_TOOL_DEF.description
        assert SKILL_LIST_TOOL_DEF.input_schema["properties"] == {}


class TestSkillManageTool:
    """Test _skill_manage_tool handler."""

    @pytest.mark.asyncio
    async def test_missing_action(self):
        result = await _skill_manage_tool({}, {})
        assert "Error: 'action' is required" in result

    @pytest.mark.asyncio
    async def test_missing_id(self):
        result = await _skill_manage_tool({"action": "create"}, {})
        assert "Error: 'id' is required" in result

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        result = await _skill_manage_tool({"action": "unknown", "id": "test"}, {})
        assert "unknown action" in result

    @pytest.mark.asyncio
    @patch("feinn_agent.skill.auto_create.create_skill")
    async def test_create_skill(self, mock_create):
        mock_create.return_value = "/path/to/skill.md"
        result = await _skill_manage_tool(
            {"action": "create", "id": "my-skill", "template": "Do something"},
            {},
        )
        assert "Created skill: my-skill" in result
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    @patch("feinn_agent.skill.auto_create.create_skill")
    async def test_create_skill_error(self, mock_create):
        mock_create.side_effect = ValueError("Invalid template")
        result = await _skill_manage_tool(
            {"action": "create", "id": "bad-skill", "template": ""},
            {},
        )
        assert "Error creating skill" in result

    @pytest.mark.asyncio
    @patch("feinn_agent.skill.auto_create.patch_skill")
    async def test_patch_skill(self, mock_patch):
        mock_patch.return_value = True
        result = await _skill_manage_tool(
            {"action": "patch", "id": "my-skill", "template": "Updated"},
            {},
        )
        assert "Patched skill: my-skill" in result

    @pytest.mark.asyncio
    @patch("feinn_agent.skill.auto_create.patch_skill")
    async def test_patch_skill_not_found(self, mock_patch):
        mock_patch.return_value = False
        result = await _skill_manage_tool(
            {"action": "patch", "id": "nonexistent"},
            {},
        )
        assert "not found or patch blocked" in result

    @pytest.mark.asyncio
    @patch("feinn_agent.skill.curator.archive_skill")
    @patch("feinn_agent.tools.skills.Path")
    async def test_delete_skill(self, mock_path, mock_archive):
        mock_archive.return_value = True
        result = await _skill_manage_tool(
            {"action": "delete", "id": "old-skill"},
            {},
        )
        assert "Deleted (archived) skill: old-skill" in result

    @pytest.mark.asyncio
    @patch("feinn_agent.skill.curator.archive_skill")
    @patch("feinn_agent.tools.skills.Path")
    async def test_delete_skill_not_found(self, mock_path, mock_archive):
        mock_archive.return_value = False
        result = await _skill_manage_tool(
            {"action": "delete", "id": "nonexistent"},
            {},
        )
        assert "not found or deletion failed" in result

    def test_skill_manage_tool_def(self):
        assert SKILL_MANAGE_TOOL_DEF.name == "SkillManage"
        assert "Create, patch, or delete skills" in SKILL_MANAGE_TOOL_DEF.description
        assert "action" in SKILL_MANAGE_TOOL_DEF.input_schema["properties"]
        assert "id" in SKILL_MANAGE_TOOL_DEF.input_schema["properties"]
