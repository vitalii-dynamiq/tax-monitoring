"""Tests for AgentRunRecorder: per-turn capture and flush to DB."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select

from app.models.agent_run_turn import AgentRunTurn
from app.services.agent_run_recorder import AgentRunRecorder, _count_web_searches
from tests.factories import create_jurisdiction, create_monitoring_job


def _fake_text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="text",
        text=text,
        model_dump=lambda mode="json", exclude_none=False: {"type": "text", "text": text},
    )


def _fake_server_tool_use_web_search() -> SimpleNamespace:
    payload = {"type": "server_tool_use", "name": "web_search", "input": {"query": "ny tax"}}
    return SimpleNamespace(
        type="server_tool_use",
        name="web_search",
        model_dump=lambda mode="json", exclude_none=False: payload,
    )


def _fake_tool_use(name: str, inp: dict) -> SimpleNamespace:
    payload = {"type": "tool_use", "name": name, "input": inp, "id": "toolu_x"}
    return SimpleNamespace(
        type="tool_use",
        name=name,
        input=inp,
        model_dump=lambda mode="json", exclude_none=False: payload,
    )


def _fake_response(*, content: list, usage: dict, stop_reason: str = "tool_use",
                   model: str = "claude-sonnet-4-6") -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        usage=SimpleNamespace(**usage),
        stop_reason=stop_reason,
        model=model,
    )


class TestRecordTurn:
    def test_records_basic_turn(self):
        rec = AgentRunRecorder(model="claude-sonnet-4-6", system_prompt="sys", initial_user_prompt="u")
        resp = _fake_response(
            content=[_fake_text_block("hello")],
            usage={"input_tokens": 100, "output_tokens": 20,
                   "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
        )
        t0 = datetime.now(UTC)
        rec.record_turn(
            response=resp, started_at=t0, completed_at=t0 + timedelta(milliseconds=1234),
            request_messages=[{"role": "user", "content": "u"}],
        )
        assert len(rec.turns) == 1
        turn = rec.turns[0]
        assert turn.turn_index == 0
        assert turn.input_tokens == 100
        assert turn.output_tokens == 20
        assert turn.latency_ms == 1234
        assert turn.web_search_count == 0
        assert turn.response_content[0]["text"] == "hello"

    def test_counts_web_searches_in_response(self):
        rec = AgentRunRecorder(model="claude-sonnet-4-6", system_prompt="", initial_user_prompt="")
        resp = _fake_response(
            content=[
                _fake_server_tool_use_web_search(),
                _fake_server_tool_use_web_search(),
                _fake_text_block("ok"),
            ],
            usage={"input_tokens": 5, "output_tokens": 5,
                   "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
        )
        rec.record_turn(
            response=resp,
            started_at=datetime.now(UTC), completed_at=datetime.now(UTC),
            request_messages=[],
        )
        assert rec.turns[0].web_search_count == 2

    def test_captures_tool_use_blocks(self):
        rec = AgentRunRecorder(model="claude-sonnet-4-6", system_prompt="", initial_user_prompt="")
        rec.record_turn(
            response=_fake_response(
                content=[_fake_tool_use("report_tax_findings", {"rates": []})],
                usage={"input_tokens": 0, "output_tokens": 0,
                       "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
                stop_reason="end_turn",
            ),
            started_at=datetime.now(UTC), completed_at=datetime.now(UTC),
            request_messages=[],
        )
        block = rec.turns[0].response_content[0]
        assert block["type"] == "tool_use"
        assert block["name"] == "report_tax_findings"

    def test_truncates_huge_text_block(self):
        rec = AgentRunRecorder(model="claude-sonnet-4-6", system_prompt="", initial_user_prompt="")
        big = "x" * 100_000
        rec.record_turn(
            response=_fake_response(
                content=[_fake_text_block(big)],
                usage={"input_tokens": 0, "output_tokens": 0,
                       "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
            ),
            started_at=datetime.now(UTC), completed_at=datetime.now(UTC),
            request_messages=[],
        )
        stored = rec.turns[0].response_content[0]["text"]
        assert "[truncated" in stored
        assert len(stored) < 20_000


class TestFlush:
    async def test_writes_turns_and_aggregates(self, db):
        j = await create_jurisdiction(db)
        job = await create_monitoring_job(db, jurisdiction_id=j.id)
        await db.commit()

        rec = AgentRunRecorder(
            model="claude-sonnet-4-6",
            system_prompt="SYSTEM",
            initial_user_prompt="Research NY hotel tax",
        )
        for i in range(3):
            rec.record_turn(
                response=_fake_response(
                    content=[_fake_server_tool_use_web_search()] if i == 1 else [_fake_text_block("ok")],
                    usage={
                        "input_tokens": 1000 + i,
                        "output_tokens": 500 + i,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                    },
                ),
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC) + timedelta(milliseconds=100),
                request_messages=[{"role": "user", "content": f"turn {i}"}],
            )

        await rec.flush(db, job.id)
        await db.commit()

        rows = (await db.execute(
            select(AgentRunTurn).where(AgentRunTurn.monitoring_job_id == job.id)
            .order_by(AgentRunTurn.turn_index)
        )).scalars().all()
        assert [r.turn_index for r in rows] == [0, 1, 2]
        assert [r.input_tokens for r in rows] == [1000, 1001, 1002]

        await db.refresh(job)
        assert job.total_input_tokens == 1000 + 1001 + 1002
        assert job.total_output_tokens == 500 + 501 + 502
        assert job.total_web_search_count == 1
        assert job.model == "claude-sonnet-4-6"
        assert job.system_prompt == "SYSTEM"
        assert job.initial_user_prompt == "Research NY hotel tax"
        # 3003 input * 3 / 1M = 0.009009; 1503 out * 15 / 1M = 0.022545; web=0.01
        # total ≈ 0.0416
        assert job.estimated_cost_usd > Decimal("0.04")
        assert job.estimated_cost_usd < Decimal("0.05")


def test_count_web_searches_handles_non_dict():
    assert _count_web_searches([]) == 0
    assert _count_web_searches([{"type": "text"}]) == 0
    assert _count_web_searches([
        {"type": "server_tool_use", "name": "web_search"},
        {"type": "server_tool_use", "name": "other_tool"},
    ]) == 1
