import asyncio
import pytest
from app.api.chat import session_guard
from fastapi import HTTPException


def test_same_session_rejected_while_active_and_released():
    async def exercise():
        async with session_guard('session-a'):
            with pytest.raises(HTTPException) as error:
                async with session_guard('session-a'):
                    pass
            assert error.value.status_code == 409
            async with session_guard('session-b'):
                pass
        async with session_guard('session-a'):
            pass
    asyncio.run(exercise())
