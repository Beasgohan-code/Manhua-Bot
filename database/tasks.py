# Manhua-Bot - Tasks mixin (PostgreSQL)

import json

class TasksMixin:
    async def add_task(self, name, data=None):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO tasks (name, data) VALUES ($1, $2::jsonb) RETURNING id",
                name, json.dumps(data or {}, default=str)
            )
            return row["id"]

    async def get_tasks(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, data FROM tasks WHERE status = 'pending' ORDER BY id"
            )
            return [
                {"_id": r["id"], "name": r["name"], "data": r["data"]}
                for r in rows
            ]

    async def del_task(self, task_id):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE tasks SET status = 'done' WHERE id = $1", int(task_id)
            )
