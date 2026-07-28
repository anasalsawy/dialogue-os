import asyncio

from dialogue_os.chief_lane import ChiefLane


async def test_submit_returns_before_chief_finishes():
    release = asyncio.Event()

    async def execute(prompt):
        await release.wait()
        return {"ok": True, "text": prompt}

    lane = ChiefLane(execute)
    lane.start()
    queued = await lane.submit("delegate this", source="test")

    assert queued["status"] == "queued"
    assert lane.get(queued["command_id"])["status"] in {"queued", "running"}

    release.set()
    await asyncio.wait_for(lane._queue.join(), timeout=1)
    completed = lane.get(queued["command_id"])
    assert completed["status"] == "completed"
    assert completed["result"]["text"] == "delegate this"
    await lane.stop()


async def test_priority_lane_runs_owner_before_background():
    order = []
    gate = asyncio.Event()

    async def execute(prompt):
        order.append(prompt)
        if prompt == "first":
            await gate.wait()
        return {"ok": True, "text": prompt}

    lane = ChiefLane(execute)
    await lane.submit("background", source="supervisor", priority=50)
    await lane.submit("owner", source="telegram", priority=0)
    lane.start()
    await asyncio.wait_for(lane._queue.join(), timeout=1)

    assert order == ["owner", "background"]
    await lane.stop()

