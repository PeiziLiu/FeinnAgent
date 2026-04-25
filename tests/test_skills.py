"""Tests for FeinnAgent skills functionality."""

import asyncio
import unittest
from unittest.mock import Mock, patch, MagicMock

from feinn_agent.tools.skills import _skill_tool, _skill_list_tool, SKILL_TOOL_DEF, SKILL_LIST_TOOL_DEF


class TestSkills(unittest.TestCase):
    """Test skills functionality."""

    @patch('feinn_agent.tools.skills.get_skill_by_name')
    @patch('feinn_agent.tools.skills.find_skill')
    @patch('feinn_agent.tools.skills.render_template')
    async def test_skill_tool(self, mock_render, mock_find, mock_get):
        """Test skill tool execution."""
        # Mock skill template
        mock_template = Mock()
        mock_template.skill_id = "test-skill"
        mock_template.template = "Test template $PARAMS"
        mock_template.param_names = []
        
        # Mock functions
        mock_get.return_value = mock_template
        mock_find.return_value = None
        mock_render.return_value = "Rendered test template"
        
        # Test with id parameter
        result = await _skill_tool({"id": "test-skill", "params": "test params"}, {})
        self.assertIn("[Skill: test-skill]", result)
        self.assertIn("Rendered test template", result)
        
        # Test with name parameter (backward compatibility)
        result = await _skill_tool({"name": "test-skill", "args": "test args"}, {})
        self.assertIn("[Skill: test-skill]", result)
        
        # Test with no skill id
        result = await _skill_tool({}, {})
        self.assertIn("Error: skill id is required", result)
        
        # Test with non-existent skill
        mock_get.return_value = None
        mock_find.return_value = None
        with patch('feinn_agent.tools.skills.load_skills') as mock_load:
            mock_load.return_value = []
            result = await _skill_tool({"id": "nonexistent"}, {})
            self.assertIn("Error: skill 'nonexistent' not found", result)

    @patch('feinn_agent.tools.skills.load_skills')
    async def test_skill_list_tool(self, mock_load):
        """Test skill list tool."""
        # Mock skill templates
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
        mock_template3.visible_to_user = False  # Should not be included
        
        mock_load.return_value = [mock_template1, mock_template2, mock_template3]
        
        result = await _skill_list_tool({}, {})
        self.assertIn("Available skill templates:", result)
        self.assertIn("test-skill-1", result)
        self.assertIn("test-skill-2", result)
        self.assertIn("Test skill 1", result)
        self.assertIn("Test skill 2", result)
        
        # Test with no skills
        mock_load.return_value = []
        result = await _skill_list_tool({}, {})
        self.assertIn("No skills available", result)

    def test_skill_tool_def(self):
        """Test Skill tool definition."""
        self.assertEqual(SKILL_TOOL_DEF.name, "Skill")
        self.assertIn("Invoke a named skill template", SKILL_TOOL_DEF.description)
        self.assertIn("id", SKILL_TOOL_DEF.input_schema["properties"])
        self.assertIn("params", SKILL_TOOL_DEF.input_schema["properties"])

    def test_skill_list_tool_def(self):
        """Test SkillList tool definition."""
        self.assertEqual(SKILL_LIST_TOOL_DEF.name, "SkillList")
        self.assertIn("List all available skill templates", SKILL_LIST_TOOL_DEF.description)
        self.assertEqual(SKILL_LIST_TOOL_DEF.input_schema["properties"], {})


if __name__ == "__main__":
    unittest.main()
