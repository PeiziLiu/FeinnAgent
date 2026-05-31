"""Tests for display module — SpinnerEngine, tool cards, diff rendering."""


from feinn_agent.display import (
    Colors,
    SpinnerEngine,
    get_tool_emoji,
    render_diff_summary,
    render_diff_text,
    render_tool_card,
)


class TestSpinnerEngine:
    def test_render_basic(self):
        """Spinner render returns expected format at known elapsed time."""
        spinner = SpinnerEngine(use_color=False)
        spinner._frame_index = 0
        spinner._face_index = 0
        result = spinner.render(elapsed=5.0, message="Hello")
        assert "Hello" in result
        assert "00:05" in result  # 5 seconds → 00:05

    def test_render_without_message(self):
        spinner = SpinnerEngine(use_color=False)
        result = spinner.render(elapsed=0.0)
        # Should still contain elapsed and a spinner char
        assert "00:00" in result
        assert any(c in result for c in "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")

    def test_render_thinking_mode(self):
        spinner = SpinnerEngine(use_color=False)
        spinner._frame_index = 0
        spinner._face_index = 0
        result = spinner.render(elapsed=10.5, message="Thinking...", thinking=True)
        assert "Thinking..." in result
        assert "00:10" in result  # 10 seconds → 00:10

    def test_render_hour_format(self):
        spinner = SpinnerEngine(use_color=False)
        result = spinner.render(elapsed=3661, message="")
        assert "01:01:01" in result

    def test_frame_rotation(self):
        spinner = SpinnerEngine(use_color=False)
        frames = set()
        for _ in range(20):
            frames.add(spinner.render(elapsed=1.0, message=""))
        assert len(frames) > 1  # frames rotate

    def test_face_rotation(self):
        spinner = SpinnerEngine(use_color=False)
        faces = set()
        for _ in range(20):
            f = spinner.render(elapsed=1.0, message="")
            # Extract face from output (content between spinner and elapsed)
            faces.add(f)
        assert len(faces) > 1


class TestToolEmoji:
    def test_known_tools(self):
        assert get_tool_emoji("Bash") == "⚡"
        assert get_tool_emoji("Read") == "📖"
        assert get_tool_emoji("Write") == "📝"
        assert get_tool_emoji("Edit") == "✏️"
        assert get_tool_emoji("Glob") == "🔍"
        assert get_tool_emoji("Grep") == "🔎"
        assert get_tool_emoji("WebFetch") == "🌐"

    def test_unknown_tool(self):
        assert get_tool_emoji("UnknownTool") == "⚙️"
        assert get_tool_emoji("") == "⚙️"


class TestRenderToolCard:
    def test_running_status(self):
        result = render_tool_card("Read", {"file_path": "test.py"}, status="running")
        assert "📖" in result
        assert "Read" in result
        assert "test.py" in result

    def test_success_status(self):
        result = render_tool_card("Bash", status="success")
        assert "✓" in result
        assert "Bash" in result
        assert "completed" in result

    def test_error_status(self):
        result = render_tool_card("Write", status="error")
        assert "✗" in result
        assert "Write" in result
        assert "failed" in result

    def test_denied_status(self):
        result = render_tool_card("Bash", status="denied")
        assert "✗" in result
        assert "Bash" in result
        assert "denied" in result

    def test_no_args(self):
        result = render_tool_card("Skill", status="running")
        assert "🧠" in result


class TestRenderDiffText:
    def test_colors_additions(self):
        diff = "+new line\n-context\n@@ -1,1 +1,2 @@\n"
        result = render_diff_text(diff, max_lines=20)
        assert Colors.GREEN in result
        assert Colors.RED in result
        assert Colors.CYAN in result

    def test_truncation(self):
        diff = "\n".join(f"+line {i}" for i in range(50))
        result = render_diff_text(diff, max_lines=10)
        assert "... (40 more lines)" in result


class TestRenderDiffSummary:
    def test_additions_and_removals(self):
        diff = "+add1\n+add2\n-rem1\n context\n"
        result = render_diff_summary(diff)
        assert "+2" in result
        assert "-1" in result

    def test_only_additions(self):
        diff = "+add1\n+add2\n+add3\n"
        result = render_diff_summary(diff)
        assert "+3" in result
        assert "-" not in result.replace("-", "", 1)

    def test_no_changes(self):
        result = render_diff_summary("context\nno changes\n")
        assert "no changes" in result or (Colors.BRIGHT_BLACK in result)
