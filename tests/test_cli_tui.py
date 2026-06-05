"""Tests for cli_tui module — FeinnTUI class."""

import time
import threading
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from feinn_agent.cli_tui import FeinnTUI
from feinn_agent.types import PermissionMode


@pytest.fixture
def mock_pt():
    """Mock prompt_toolkit modules for FeinnTUI construction."""
    with patch("feinn_agent.cli_tui._import_pt") as mock_import:
        pt = {
            "print_formatted_text": MagicMock(),
            "Application": MagicMock(),
            "ANSI": MagicMock(),
            "Layout": MagicMock(),
            "HSplit": MagicMock(),
            "Window": MagicMock(),
            "FormattedTextControl": MagicMock(return_value=MagicMock()),
            "ConditionalContainer": MagicMock(),
            "Dimension": MagicMock(),
            "CompletionsMenu": MagicMock(),
            "TextArea": MagicMock(),
            "KeyBindings": MagicMock(),
            "Condition": MagicMock(side_effect=lambda fn: MagicMock()),
            "PTStyle": MagicMock(),
            "FileHistory": MagicMock(),
        }
        mock_import.return_value = pt
        yield pt


class TestFeinnTUIInit:
    def test_construction(self, mock_pt):
        config = {"model": "gpt-4o", "permission_mode": "auto"}
        tui = FeinnTUI(config)
        assert tui.config["model"] == "gpt-4o"
        assert tui._model_name == "gpt-4o"
        assert tui._permission_mode == "auto"
        assert tui._session_allowlist == set()

    def test_default_config_values(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        assert tui._permission_mode == PermissionMode.AUTO.value
        assert tui._status_bar_visible is True
        assert tui._agent_running is False
        assert tui._spinner_running is False
        assert tui._approval_state is None

    def test_raises_without_prompt_toolkit(self):
        with patch("feinn_agent.cli_tui._import_pt", return_value=None):
            with pytest.raises(ImportError):
                FeinnTUI({"model": "test"})


class TestFeinnTUISpinnerFragments:
    def test_spinner_empty_when_idle(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        fragments = tui._get_spinner_fragments()
        assert fragments == []

    def test_spinner_not_empty_when_running(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        tui._agent_running = True
        tui._spinner_text = "Thinking..."
        tui._tool_start_time = time.time()
        fragments = tui._get_spinner_fragments()
        assert len(fragments) > 0
        assert "Thinking..." in fragments[0][1]


class TestFeinnTUIStatusBar:
    def test_status_bar_visible(self, mock_pt):
        tui = FeinnTUI({"model": "gpt-4o"})
        tui._session_start = time.time() - 65  # 65 seconds ago
        fragments = tui._get_status_bar_fragments()
        assert len(fragments) > 0
        text = fragments[0][1]
        assert "gpt-4o" in text
        assert "⚕" in text

    def test_status_bar_hidden(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        tui._status_bar_visible = False
        assert tui._get_status_bar_fragments() == []

    def test_status_bar_tokens(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        tui._total_input_tokens = 100
        tui._total_output_tokens = 50
        fragments = tui._get_status_bar_fragments()
        text = fragments[0][1]
        assert "100" in text
        assert "50" in text


class TestFeinnTUIApproval:
    def test_approval_fragments_empty_when_no_state(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        assert tui._get_approval_fragments() == []

    def test_approval_fragments_with_state(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        request = MagicMock()
        request.name = "Bash"
        request.inputs = {"command": "ls -la"}
        tui._approval_state = {"request": request}
        fragments = tui._get_approval_fragments()
        assert len(fragments) > 0
        texts = "".join(t for _, t in fragments)
        assert "Bash" in texts
        assert "ls -la" in texts
        assert "Allow?" in texts

    def test_is_approval_mode(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        assert tui._is_approval_mode() is False
        tui._approval_state = {"request": MagicMock()}
        assert tui._is_approval_mode() is True

    def test_is_input_mode_true_when_idle(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        assert tui._is_input_mode() is True

    def test_is_input_mode_false_when_agent_running(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        tui._agent_running = True
        assert tui._is_input_mode() is False

    def test_is_input_mode_false_when_approval(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        tui._approval_state = {"request": MagicMock()}
        assert tui._is_input_mode() is False


class TestFeinnTUIPermissionCallback:
    def test_session_allowlist_bypasses_panel(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        tui._session_allowlist.add("Bash")
        request = MagicMock()
        request.name = "Bash"
        result = tui._tui_permission_callback(request)
        assert result is True
        assert tui._approval_state is None

    def test_accept_all_bypasses_panel(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        tui._permission_mode = PermissionMode.ACCEPT_ALL.value
        request = MagicMock()
        request.name = "Bash"
        result = tui._tui_permission_callback(request)
        assert result is True

    def test_panel_shown_and_responded(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        request = MagicMock()
        request.name = "Write"
        request.inputs = {"file_path": "/tmp/test.txt"}

        # Mock the approval done event to simulate user pressing 'y'
        def _mock_wait():
            tui._approval_state["result"] = True

        with patch.object(threading.Event, "wait", side_effect=_mock_wait):
            result = tui._tui_permission_callback(request)

        assert result is True

    def test_panel_denied(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        request = MagicMock()
        request.name = "Bash"

        def _mock_wait():
            tui._approval_state["result"] = False
            tui._approval_state = None

        with patch.object(threading.Event, "wait", side_effect=_mock_wait):
            result = tui._tui_permission_callback(request)

        assert result is False


class TestFeinnTUISafeOutput:
    def test_safe_output_no_app(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        with patch.object(tui, "_raw_print") as mock_print:
            tui._safe_output("hello")
            mock_print.assert_called_once_with("hello\n")

    def test_safe_output_empty_text_with_newline(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        with patch.object(tui, "_raw_print") as mock_print:
            tui._safe_output("")
            mock_print.assert_called_once_with("\n")

    def _make_bg_thread(self):
        """Simulate being in a background thread by returning a non-main thread."""
        t = threading.Thread(target=lambda: None)
        return patch.object(threading, "current_thread", return_value=t)

    def test_streaming_chunks_accumulate(self, mock_pt):
        """Streaming chunks (end="") accumulate in buffer, not flushed per-call."""
        tui = FeinnTUI({"model": "test"})
        mock_app = MagicMock()
        mock_app._is_running = True
        tui._app = mock_app

        with self._make_bg_thread(), patch.object(tui, "_raw_print") as mock_print:
            tui._safe_output("你好", end="")
            tui._safe_output("世界", end="")
            # No raw_print called — text is buffered
            mock_print.assert_not_called()
            # Accumulator has the text
            assert tui._output_accumulator == "你好世界"

    def test_streaming_schedules_one_flush(self, mock_pt):
        """First streaming chunk schedules flush; subsequent chunks don't."""
        tui = FeinnTUI({"model": "test"})
        mock_app = MagicMock()
        mock_app._is_running = True
        tui._app = mock_app

        with self._make_bg_thread():
            tui._safe_output("chunk1", end="")
            assert mock_app.loop.call_soon_threadsafe.call_count == 1

            tui._safe_output("chunk2", end="")
            # No additional schedule
            assert mock_app.loop.call_soon_threadsafe.call_count == 1

    def test_complete_line_flushes_immediately(self, mock_pt):
        """Complete lines (end='\\n') schedule a flush."""
        tui = FeinnTUI({"model": "test"})
        mock_app = MagicMock()
        mock_app._is_running = True
        tui._app = mock_app

        with self._make_bg_thread():
            tui._safe_output("hello\nworld", end="\n")
            # Flush scheduled via loop.call_soon_threadsafe
            assert mock_app.loop.call_soon_threadsafe.call_count == 1
            # No raw_print (everything goes through _flush_output → print)
            assert tui._output_accumulator == "hello\nworld\n"

    def test_flush_output_sends_accumulated_text(self, mock_pt):
        """_flush_output sends buffered text via print()."""
        tui = FeinnTUI({"model": "test"})
        tui._output_accumulator = "你好世界"
        tui._flush_pending = True

        with patch("builtins.print") as mock_print:
            tui._flush_output()

        mock_print.assert_called_once_with("你好世界", end="", flush=True)
        assert tui._output_accumulator == ""
        assert tui._flush_pending is False

    def test_flush_output_empty_noop(self, mock_pt):
        """_flush_output with empty buffer is a no-op."""
        tui = FeinnTUI({"model": "test"})
        with patch("builtins.print") as mock_print:
            tui._flush_output()
            mock_print.assert_not_called()

    def test_interleaved_streaming_and_lines(self, mock_pt):
        """Streaming chunks + complete lines: all buffered, line triggers flush."""
        tui = FeinnTUI({"model": "test"})
        mock_app = MagicMock()
        mock_app._is_running = True
        tui._app = mock_app

        with self._make_bg_thread():
            tui._safe_output("stream", end="")
            tui._safe_output("ing", end="")
            tui._safe_output("line1", end="\n")
            tui._safe_output("more_stream", end="")

        # All text accumulated (including end chars)
        assert "stream" in tui._output_accumulator
        assert "ing" in tui._output_accumulator
        assert "line1\n" in tui._output_accumulator
        assert "more_stream" in tui._output_accumulator
        # flush scheduled at least once (on first chunk + on line)
        assert mock_app.loop.call_soon_threadsafe.call_count >= 1


class TestFeinnTUIHandleCommand:
    def test_quit(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        with patch.object(tui, "stop") as mock_stop:
            result = tui._handle_command("/quit")
            assert result is True
            mock_stop.assert_called_once()

    def test_help(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        with patch.object(tui, "_safe_output") as mock_out:
            result = tui._handle_command("/help")
            assert result is True
            # Should print help text
            calls = [c[0][0] for c in mock_out.call_args_list if c[0][0]]
            help_calls = [c for c in calls if "Commands" in str(c)]
            assert len(help_calls) > 0

    def test_model_show(self, mock_pt):
        tui = FeinnTUI({"model": "gpt-4o"})
        with patch.object(tui, "_safe_output") as mock_out:
            result = tui._handle_command("/model")
            assert result is True
            mock_out.assert_called_with("Current model: gpt-4o")

    def test_model_set(self, mock_pt):
        tui = FeinnTUI({"model": "old-model"})
        with patch.object(tui, "_safe_output") as mock_out:
            result = tui._handle_command("/model new-model")
            assert result is True
            assert tui._model_name == "new-model"
            assert tui.config["model"] == "new-model"

    def test_accept_all(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        with patch.object(tui, "_safe_output"):
            result = tui._handle_command("/accept-all")
            assert result is True
            assert tui._permission_mode == PermissionMode.ACCEPT_ALL.value

    def test_auto(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        with patch.object(tui, "_safe_output"):
            result = tui._handle_command("/auto")
            assert result is True
            assert tui._permission_mode == PermissionMode.AUTO.value

    def test_manual(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        with patch.object(tui, "_safe_output"):
            result = tui._handle_command("/manual")
            assert result is True
            assert tui._permission_mode == PermissionMode.MANUAL.value

    def test_interrupt(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        with patch.object(tui, "_safe_output"):
            result = tui._handle_command("/interrupt")
            assert result is True
            assert tui._interrupt_requested is True

    def test_unknown_command(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        result = tui._handle_command("/nonexistent")
        assert result is False


class TestFeinnTUISkillHandling:
    def test_try_handle_skill_no_match(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        with patch("feinn_agent.skill.find_skill", return_value=None):
            result = tui._try_handle_skill("hello world")
            assert result is None

    def test_try_handle_skill_with_result(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        skill = MagicMock()
        skill.activators = ["/commit"]
        skill.param_names = ["message"]
        skill.template = "commit: {message}"

        with (
            patch("feinn_agent.skill.find_skill", return_value=skill),
            patch("feinn_agent.skill.render_template", return_value="commit: fix bug"),
        ):
            result = tui._try_handle_skill("/commit fix bug")
            assert result == "commit: fix bug"


class TestFeinnTUIStop:
    def test_stop_sets_flags(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        tui._app = MagicMock()
        tui.stop()
        assert tui._agent_running is False
        assert tui._spinner_running is False
        assert tui._interrupt_requested is True
        tui._app.exit.assert_called_once()

    def test_stop_no_app(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        tui.stop()
        # Should not crash


class TestFeinnTUIBuildCompleter:
    def test_build_completer(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        with patch("feinn_agent.cli.FeinnCompleter.refresh_skills") as mock_refresh:
            completer = tui._build_completer()
            mock_refresh.assert_called_once()


class TestFeinnTUIGetApprovalFragments:
    def test_approval_fragments_show_tool_args(self, mock_pt):
        tui = FeinnTUI({"model": "test"})
        request = MagicMock()
        request.name = "Edit"
        request.inputs = {"file_path": "main.py", "old_string": "foo", "new_string": "bar"}
        tui._approval_state = {"request": request}
        fragments = tui._get_approval_fragments()
        concat = "".join(t for _, t in fragments)
        assert "Edit" in concat
        assert "file_path" in concat
        assert "main.py" in concat
        assert "Allow?" in concat
