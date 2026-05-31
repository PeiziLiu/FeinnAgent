"""Tests for closed-loop learning system.

Covers:
- Nudge counters (increment, reset, hydrate, suppress)
- Background review (spawn, prompt selection, thread safety)
- Session store (SQLite CRUD, FTS5 search, session chains)
- Session search tool (DISCOVER, SCROLL, BROWSE modes)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from feinn_agent.learning import (
    BackgroundReviewer,
    NudgeConfig,
    NudgeCounter,
)
from feinn_agent.learning.session_store import (
    MessageRecord,
    SessionRecord,
    SessionStore,
)
from feinn_agent.learning.session_search import (
    SESSION_SEARCH_TOOL_DEF,
    _session_search_tool,
)


class TestNudgeConfig:
    """Test NudgeConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = NudgeConfig()
        assert config.memory_nudge_interval == 10
        assert config.skill_nudge_interval == 10
        assert config.enabled is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = NudgeConfig(
            memory_nudge_interval=5,
            skill_nudge_interval=3,
            enabled=False,
        )
        assert config.memory_nudge_interval == 5
        assert config.skill_nudge_interval == 3
        assert config.enabled is False


class TestNudgeCounter:
    """Test NudgeCounter behavior."""

    def test_initial_state(self):
        """Test initial counter state."""
        counter = NudgeCounter()
        assert counter.should_review_memory is False
        assert counter.should_review_skill is False
        assert counter.should_review_any is False

    def test_memory_nudge_triggers_at_threshold(self):
        """Test memory nudge triggers at configured interval."""
        counter = NudgeCounter(NudgeConfig(memory_nudge_interval=3, skill_nudge_interval=100))

        # Turn 1: should not trigger
        counter.record_turn()
        assert counter.should_review_memory is False

        # Turn 2
        counter.record_turn()
        assert counter.should_review_memory is False

        # Turn 3: should trigger
        counter.record_turn()
        assert counter.should_review_memory is True

    def test_skill_nudge_triggers_at_threshold(self):
        """Test skill nudge triggers at configured interval."""
        counter = NudgeCounter(NudgeConfig(memory_nudge_interval=100, skill_nudge_interval=5))

        # 4 iterations: should not trigger
        counter.record_tool_iterations(4)
        assert counter.should_review_skill is False

        # 5th iteration: should trigger
        counter.record_tool_iterations(1)
        assert counter.should_review_skill is True

    def test_reset_memory_nudge(self):
        """Test memory nudge reset."""
        counter = NudgeCounter(NudgeConfig(memory_nudge_interval=2))
        counter.record_turn()
        counter.record_turn()
        assert counter.should_review_memory is True

        counter.reset_memory_nudge()
        assert counter.should_review_memory is False

    def test_reset_skill_nudge(self):
        """Test skill nudge reset."""
        counter = NudgeCounter(NudgeConfig(skill_nudge_interval=3))
        counter.record_tool_iterations(3)
        assert counter.should_review_skill is True

        counter.reset_skill_nudge()
        assert counter.should_review_skill is False

    def test_reset_all(self):
        """Test resetting all counters."""
        counter = NudgeCounter(NudgeConfig(memory_nudge_interval=2, skill_nudge_interval=2))
        counter.record_turn()
        counter.record_turn()
        counter.record_tool_iterations(2)
        assert counter.should_review_any is True

        counter.reset_all()
        assert counter.should_review_memory is False
        assert counter.should_review_skill is False

    def test_suppress_skill_nudge(self):
        """Test skill nudge suppression."""
        counter = NudgeCounter(NudgeConfig(skill_nudge_interval=3))
        counter.record_tool_iterations(3)
        assert counter.should_review_skill is True

        counter.suppress_skill_nudge()
        assert counter.should_review_skill is False

    def test_disabled_nudge(self):
        """Test that disabled nudge never triggers."""
        counter = NudgeCounter(NudgeConfig(enabled=False))
        counter.record_turn()
        counter.record_tool_iterations(100)
        assert counter.should_review_memory is False
        assert counter.should_review_skill is False
        assert counter.should_review_any is False

    def test_zero_interval_no_trigger(self):
        """Test that zero interval disables that nudge type."""
        counter = NudgeCounter(NudgeConfig(memory_nudge_interval=0, skill_nudge_interval=0))
        counter.record_turn()
        counter.record_tool_iterations(100)
        assert counter.should_review_memory is False
        assert counter.should_review_skill is False

    def test_hydrate_from_history(self):
        """Test counter hydration prevents immediate trigger on resume."""
        counter = NudgeCounter(NudgeConfig(memory_nudge_interval=10, skill_nudge_interval=10))

        # Hydrate from 25 prior turns → 25 % 10 = 5, so 5 more turns needed
        counter.hydrate_from_history(prior_turns=25, prior_tool_iters=0)
        assert counter.should_review_memory is False

        counter.record_turn()  # 6
        counter.record_turn()  # 7
        counter.record_turn()  # 8
        counter.record_turn()  # 9
        counter.record_turn()  # 10 → trigger
        assert counter.should_review_memory is True

    def test_should_review_any(self):
        """Test 'any' check returns True when either threshold is met."""
        counter = NudgeCounter(NudgeConfig(memory_nudge_interval=2, skill_nudge_interval=100))
        counter.record_turn()
        assert counter.should_review_any is False

        counter.record_turn()
        assert counter.should_review_memory is True
        assert counter.should_review_any is True


class TestBackgroundReviewer:
    """Test BackgroundReviewer basic functionality."""

    def test_init(self):
        """Test reviewer initialization."""
        agent = object()
        reviewer = BackgroundReviewer(agent, {"review_timeout": 15})
        assert reviewer._review_timeout == 15

    def test_spawn_memory_only(self):
        """Test spawning memory-only review."""
        agent = object()
        reviewer = BackgroundReviewer(agent, {})
        # Should not raise
        reviewer.spawn([], review_memory=True, review_skill=False)

    def test_spawn_skill_only(self):
        """Test spawning skill-only review."""
        agent = object()
        reviewer = BackgroundReviewer(agent, {})
        reviewer.spawn([], review_memory=False, review_skill=True)

    def test_spawn_combined(self):
        """Test spawning combined review."""
        agent = object()
        reviewer = BackgroundReviewer(agent, {})
        reviewer.spawn([], review_memory=True, review_skill=True)

    def test_spawn_noop(self):
        """Test that spawn is a no-op when neither flag is set."""
        agent = object()
        reviewer = BackgroundReviewer(agent, {})
        reviewer.spawn([], review_memory=False, review_skill=False)
        # No exception means success


class TestSessionStore:
    """Test SQLite session storage."""

    @pytest.fixture
    def store(self):
        """Create a temporary session store for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        store = SessionStore(db_path=db_path)
        yield store
        Path(db_path).unlink(missing_ok=True)

    def test_create_session(self, store):
        """Test creating a new session."""
        session = store.create_session(model="test-model")
        assert session.id is not None
        assert session.model == "test-model"
        assert session.parent_session_id is None
        assert session.token_count == 0

    def test_create_session_with_parent(self, store):
        """Test creating a session with a parent reference."""
        parent = store.create_session()
        child = store.create_session(parent_id=parent.id)
        assert child.parent_session_id == parent.id

    def test_end_session(self, store):
        """Test ending a session with a title."""
        session = store.create_session()
        store.end_session(session.id, title="Test Session")
        retrieved = store.get_session(session.id)
        assert retrieved is not None
        assert retrieved.title == "Test Session"

    def test_get_session_not_found(self, store):
        """Test getting a non-existent session."""
        session = store.get_session("nonexistent")
        assert session is None

    def test_append_message(self, store):
        """Test appending a message to a session."""
        session = store.create_session()
        msg = store.append_message(
            session_id=session.id,
            role="user",
            content="Hello, world!",
            tokens=10,
        )
        assert msg.id > 0
        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert msg.tokens == 10

    def test_append_tool_calls(self, store):
        """Test appending a message with tool calls."""
        session = store.create_session()
        tool_calls = [{"name": "Read", "input": {"file_path": "test.py"}}]
        msg = store.append_message(
            session_id=session.id,
            role="assistant",
            content="Let me read that file",
            tool_calls=tool_calls,
        )
        assert msg.tool_calls is not None
        parsed = json.loads(msg.tool_calls)
        assert parsed == tool_calls

    def test_search_found(self, store):
        """Test FTS5 search finds matching content."""
        session = store.create_session()
        store.append_message(session.id, "user", "I love Python programming")
        store.append_message(session.id, "assistant", "Python is great for automation")

        results = store.search("Python")
        assert len(results) >= 2
        assert all("Python" in r.snippet for r in results)

    def test_search_not_found(self, store):
        """Test FTS5 search with no matches."""
        session = store.create_session()
        store.append_message(session.id, "user", "Hello world")
        results = store.search("nonexistent")
        assert len(results) == 0

    def test_scroll(self, store):
        """Test SCROLL mode returns ±window around a message."""
        session = store.create_session()
        msg_ids = []
        for i in range(10):
            msg = store.append_message(
                session.id,
                "user" if i % 2 == 0 else "assistant",
                f"Message {i}",
            )
            msg_ids.append(msg.id)

        mid_idx = len(msg_ids) // 2
        around = msg_ids[mid_idx]
        results = store.scroll(session.id, around, window=2)
        assert len(results) <= 5  # ±2 + anchor
        assert results[0].id >= around - 2
        assert results[-1].id <= around + 2

    def test_browse(self, store):
        """Test BROWSE mode lists recent sessions."""
        s1 = store.create_session()
        store.end_session(s1.id, title="First")
        s2 = store.create_session()
        store.end_session(s2.id, title="Second")

        sessions = store.browse(limit=10)
        assert len(sessions) >= 2

    def test_message_updates_token_count(self, store):
        """Test that appending messages updates session token count."""
        session = store.create_session()
        store.append_message(session.id, "user", "Hello", tokens=5)
        store.append_message(session.id, "assistant", "Hi there", tokens=7)

        retrieved = store.get_session(session.id)
        assert retrieved is not None
        assert retrieved.token_count == 12

    def test_empty_content_not_indexed(self, store):
        """Test that empty content is not added to FTS index."""
        session = store.create_session()
        store.append_message(session.id, "tool", "", tokens=0)
        results = store.search("")
        assert len(results) == 0


class TestSessionSearchTool:
    """Test the SessionSearch tool definition and handler."""

    def test_tool_definition(self):
        """Test that SessionSearch tool has correct schema."""
        assert SESSION_SEARCH_TOOL_DEF.name == "SessionSearch"
        assert SESSION_SEARCH_TOOL_DEF.read_only is True
        assert SESSION_SEARCH_TOOL_DEF.concurrent_safe is True
        assert "query" in SESSION_SEARCH_TOOL_DEF.input_schema.get("properties", {})

    @pytest.mark.asyncio
    async def test_browse_mode(self):
        """Test BROWSE mode (no args)."""
        result = await _session_search_tool({}, {})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_discover_mode(self):
        """Test DISCOVER mode with a query."""
        result = await _session_search_tool({"query": "python"}, {})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_scroll_mode_missing_message_id(self):
        """Test SCROLL mode with session_id but no around_message_id."""
        result = await _session_search_tool({"session_id": "sess_test"}, {})
        assert isinstance(result, str)
        # Should fall through to BROWSE since no query and around_message_id is None
        # The handler first checks query + session_id, so this should work

    @pytest.mark.asyncio
    async def test_no_params(self):
        """Test with no parameters results in browse mode."""
        result = await _session_search_tool({}, {})
        assert isinstance(result, str)
        assert "session" in result.lower() or "no results" in result.lower()


class TestSkillAutoCreate:
    """Test skill auto-creation."""

    def test_create_skill(self):
        """Test creating a skill file."""
        from feinn_agent.skill.auto_create import create_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_file = create_skill(
                skill_id="test-skill",
                summary="A test skill",
                template_body="Do the thing with $PARAMS",
                activators=["/test-skill"],
                tools=["Bash", "Read"],
                param_guide="[args]",
                param_names=["args"],
                skill_dir=tmpdir,
            )
            assert skill_file.exists()
            content = skill_file.read_text(encoding="utf-8")
            assert "test-skill" in content
            assert "A test skill" in content
            assert "/test-skill" in content
            assert "Do the thing with $PARAMS" in content

    def test_create_skill_rejects_path_traversal(self):
        """Test that path traversal in skill_id is rejected."""
        from feinn_agent.skill.auto_create import create_skill

        with pytest.raises(ValueError, match="path traversal"):
            create_skill(
                skill_id="../malicious",
                summary="Bad",
                template_body="content",
                skill_dir="/tmp",
            )

    def test_create_skill_security_scan_block(self):
        """Test that dangerous content is blocked."""
        from feinn_agent.skill.auto_create import create_skill

        with pytest.raises(ValueError, match="blocked by security scan"):
            create_skill(
                skill_id="bad-skill",
                summary="Bad",
                template_body="Run rm -rf / to clean up",
                skill_dir="/tmp",
            )

    def test_patch_nonexistent_skill(self):
        """Test patching a non-existent skill returns False."""
        from feinn_agent.skill.auto_create import patch_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            result = patch_skill("nonexistent", template_body="new content", skill_dir=tmpdir)
            assert result is False


class TestSkillUsage:
    """Test skill usage telemetry."""

    def test_record_use(self):
        """Test recording a skill use."""
        from feinn_agent.skill.usage import UsageStore

        with tempfile.TemporaryDirectory() as tmpdir:
            usage_path = Path(tmpdir) / ".usage.json"
            store = UsageStore(usage_path=str(usage_path))
            store.record_use("test-skill")

            usage = store.get_usage("test-skill")
            assert usage is not None
            assert usage.use_count == 1

    def test_record_view_and_patch(self):
        """Test recording view and patch operations."""
        from feinn_agent.skill.usage import UsageStore

        with tempfile.TemporaryDirectory() as tmpdir:
            usage_path = Path(tmpdir) / ".usage.json"
            store = UsageStore(usage_path=str(usage_path))
            store.record_use("test-skill")
            store.record_view("test-skill")
            store.record_patch("test-skill")

            usage = store.get_usage("test-skill")
            assert usage is not None
            assert usage.use_count == 1
            assert usage.view_count == 1
            assert usage.patch_count == 1

    def test_get_nonexistent_usage(self):
        """Test getting usage for non-existent skill."""
        from feinn_agent.skill.usage import UsageStore

        with tempfile.TemporaryDirectory() as tmpdir:
            usage_path = Path(tmpdir) / ".usage.json"
            store = UsageStore(usage_path=str(usage_path))
            usage = store.get_usage("nonexistent")
            assert usage is None

    def test_persistence_across_instances(self):
        """Test that usage data persists across store instances."""
        from feinn_agent.skill.usage import UsageStore

        with tempfile.TemporaryDirectory() as tmpdir:
            usage_path = Path(tmpdir) / ".usage.json"

            store1 = UsageStore(usage_path=str(usage_path))
            store1.record_use("test-skill")

            store2 = UsageStore(usage_path=str(usage_path))
            usage = store2.get_usage("test-skill")
            assert usage is not None
            assert usage.use_count == 1

    def test_list_stale_skills(self):
        """Test listing stale skills."""
        from feinn_agent.skill.usage import UsageStore

        with tempfile.TemporaryDirectory() as tmpdir:
            usage_path = Path(tmpdir) / ".usage.json"
            store = UsageStore(usage_path=str(usage_path))
            store.record_use("active-skill")

            # With default days, a just-created skill is not stale
            stale = store.list_stale_skills(days=30)
            assert len(stale) == 0

    def test_set_state(self):
        """Test setting skill lifecycle state."""
        from feinn_agent.skill.usage import SkillState, UsageStore

        with tempfile.TemporaryDirectory() as tmpdir:
            usage_path = Path(tmpdir) / ".usage.json"
            store = UsageStore(usage_path=str(usage_path))
            store.record_use("test-skill")
            store.set_state("test-skill", SkillState.PINNED)

            usage = store.get_usage("test-skill")
            assert usage is not None
            assert usage.state == SkillState.PINNED


class TestSkillCurator:
    """Test skill lifecycle curation."""

    def test_run_curation_no_stale_skills(self):
        """Test curation with no stale skills."""
        from feinn_agent.skill.curator import run_curation

        with tempfile.TemporaryDirectory() as tmpdir:
            actions = run_curation(skill_dir=tmpdir, stale_days=0, dry_run=True)
            assert isinstance(actions, list)

    def test_archive_and_restore(self):
        """Test archiving and restoring a skill."""
        from feinn_agent.skill.auto_create import create_skill
        from feinn_agent.skill.curator import archive_skill, restore_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            create_skill(
                skill_id="archivable",
                summary="Will be archived",
                template_body="Some content",
                skill_dir=tmpdir,
            )
            result = archive_skill("archivable", tmpdir)
            assert result is True

            archived_path = Path(tmpdir) / ".archive" / "archivable"
            assert archived_path.exists()

            result = restore_skill("archivable", tmpdir)
            assert result is True
            assert (Path(tmpdir) / "archivable" / "SKILL.md").exists()

    def test_archive_nonexistent(self):
        """Test archiving a non-existent skill returns False."""
        from feinn_agent.skill.curator import archive_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            result = archive_skill("nonexistent", tmpdir)
            assert result is False

    def test_pin_skill(self):
        """Test pinning a skill."""
        from feinn_agent.skill.curator import pin_skill
        from feinn_agent.skill.usage import SkillState, UsageStore

        with tempfile.TemporaryDirectory() as tmpdir:
            usage_path = Path(tmpdir) / ".usage.json"
            store = UsageStore(usage_path=str(usage_path))
            store.record_use("pinned-skill")
            pin_skill("pinned-skill", tmpdir)

            # Reload from disk to get updated state
            store2 = UsageStore(usage_path=str(usage_path))
            usage = store2.get_usage("pinned-skill")
            assert usage is not None
            assert usage.state == SkillState.PINNED
