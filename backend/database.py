"""Small SQLite repository. Source messages are immutable observations."""

import json
from pathlib import Path
from typing import Iterable
from datetime import datetime

import aiosqlite

from .models.schema import (
    APScore,
    Activity,
    AgentBranch,
    AgentStatus,
    Channel,
    ChannelStatus,
    ChannelType,
    DashboardSummary,
    DeploymentConfig,
    Message,
    Process,
    ProcessEdge,
    ProcessMetrics,
)

DB_PATH = Path(__file__).resolve().parent / "autopilot.db"


def _json(value: object) -> str:
    return json.dumps(value, default=str)


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                thread_id TEXT,
                metadata TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS processes (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scores (
                process_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            """
        )
        await db.commit()


async def upsert_channel(channel: Channel) -> Channel:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO channels (id, type, name, status, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name, status=excluded.status""",
            (channel.id, channel.type.value, channel.name, channel.status.value, channel.created_at.isoformat()),
        )
        await db.commit()
    return channel


async def get_channels() -> list[Channel]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT c.id, c.type, c.name, c.status, c.created_at, COUNT(m.id)
               FROM channels c LEFT JOIN messages m ON m.channel_id=c.id
               GROUP BY c.id ORDER BY c.created_at"""
        )
        rows = await cursor.fetchall()
    return [
        Channel(
            id=row[0], type=ChannelType(row[1]), name=row[2], status=ChannelStatus(row[3]),
            created_at=row[4], message_count=row[5],
        )
        for row in rows
    ]


async def get_channel(channel_id: str) -> Channel | None:
    return next((channel for channel in await get_channels() if channel.id == channel_id), None)


async def create_messages(messages: Iterable[Message]) -> None:
    rows = [
        (message.id, message.channel_id, message.sender, message.content, message.timestamp.isoformat(), message.thread_id, _json(message.metadata))
        for message in messages
    ]
    if not rows:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT OR IGNORE INTO messages (id, channel_id, sender, content, timestamp, thread_id, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        await db.commit()


async def get_messages(channel_id: str | None = None) -> list[Message]:
    query = "SELECT id, channel_id, sender, content, timestamp, thread_id, metadata FROM messages"
    values: tuple[object, ...] = ()
    if channel_id:
        query += " WHERE channel_id = ?"
        values = (channel_id,)
    query += " ORDER BY timestamp"
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(query, values)
        rows = await cursor.fetchall()
    return [
        Message(id=row[0], channel_id=row[1], sender=row[2], content=row[3], timestamp=row[4], thread_id=row[5], metadata=json.loads(row[6]))
        for row in rows
    ]


async def latest_message_timestamp(channel_id: str) -> datetime | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT MAX(timestamp) FROM messages WHERE channel_id = ?", (channel_id,))
        row = await cursor.fetchone()
    return datetime.fromisoformat(row[0]) if row and row[0] else None


async def replace_discovery_results(processes: Iterable[Process], scores: Iterable[APScore]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM processes")
        await db.execute("DELETE FROM scores")
        await db.executemany(
            "INSERT INTO processes (id, payload) VALUES (?, ?)",
            [(process.id, process.model_dump_json()) for process in processes],
        )
        await db.executemany(
            "INSERT INTO scores (process_id, payload) VALUES (?, ?)",
            [(score.process_id, score.model_dump_json()) for score in scores],
        )
        await db.commit()


async def get_processes() -> list[Process]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT payload FROM processes ORDER BY id")
        rows = await cursor.fetchall()
    return [Process.model_validate_json(row[0]) for row in rows]


async def get_process(process_id: str) -> Process | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT payload FROM processes WHERE id = ?", (process_id,))
        row = await cursor.fetchone()
    return Process.model_validate_json(row[0]) if row else None


async def get_scores() -> list[APScore]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT payload FROM scores")
        rows = await cursor.fetchall()
    return sorted((APScore.model_validate_json(row[0]) for row in rows), key=lambda score: score.score, reverse=True)


async def get_score(process_id: str) -> APScore | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT payload FROM scores WHERE process_id = ?", (process_id,))
        row = await cursor.fetchone()
    return APScore.model_validate_json(row[0]) if row else None


async def create_agent(agent: AgentBranch) -> AgentBranch:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO agents (id, payload) VALUES (?, ?)", (agent.id, agent.model_dump_json()))
        await db.commit()
    return agent


async def get_agents() -> list[AgentBranch]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT payload FROM agents")
        rows = await cursor.fetchall()
    return sorted((AgentBranch.model_validate_json(row[0]) for row in rows), key=lambda agent: agent.created_at, reverse=True)


async def get_agent(agent_id: str) -> AgentBranch | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT payload FROM agents WHERE id = ?", (agent_id,))
        row = await cursor.fetchone()
    return AgentBranch.model_validate_json(row[0]) if row else None


async def save_agent(agent: AgentBranch) -> AgentBranch:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("UPDATE agents SET payload = ? WHERE id = ?", (agent.model_dump_json(), agent.id))
        await db.commit()
    if cursor.rowcount == 0:
        raise KeyError(agent.id)
    return agent


async def delete_agent(agent_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        await db.commit()
    return cursor.rowcount > 0


async def dashboard_summary() -> DashboardSummary:
    processes, scores, agents = await get_processes(), await get_scores(), await get_agents()
    return DashboardSummary(
        processes_discovered=len(processes),
        average_opportunity_score=round(sum(score.score for score in scores) / len(scores), 1) if scores else 0,
        evidence_backed_hours=round(sum(score.estimated_hours_saved_monthly for score in scores), 1),
        active_agents=sum(agent.status == AgentStatus.RUNNING for agent in agents),
        pending_approvals=sum(agent.status == AgentStatus.PENDING_APPROVAL for agent in agents),
    )
