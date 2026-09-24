"""
Manual API test script for chat-service.

Run with:
    python scripts/test_api.py
"""

import asyncio
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8007"


async def test_chat_service():
    """Test all chat-service endpoints."""
    print("\n🧪 Testing chat-service API...\n")

    async with httpx.AsyncClient() as client:
        # 1. Health check
        print("1️⃣ Testing GET /health")
        response = await client.get(f"{BASE_URL}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}\n")
        assert response.status_code == 200

        # 2. Save user message
        print("2️⃣ Testing POST /chat/messages (user message)")
        test_window_id = f"test_zalo_{datetime.now().timestamp()}"
        msg1 = {
            "window_id": test_window_id,
            "role": "user",
            "content": "Xin chào! Tôi muốn tìm sữa cho bé 6 tháng.",
            "metadata": {"source": "test"}
        }
        response = await client.post(f"{BASE_URL}/chat/messages", json=msg1)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}\n")
        assert response.status_code == 201
        msg1_id = response.json()["id"]

        # 3. Save assistant message
        print("3️⃣ Testing POST /chat/messages (assistant message)")
        msg2 = {
            "window_id": test_window_id,
            "role": "assistant",
            "content": "Dạ em xin chào anh! Em có thể giúp anh tìm sữa cho bé 6 tháng tuổi.",
            "metadata": {"model": "test-model"}
        }
        response = await client.post(f"{BASE_URL}/chat/messages", json=msg2)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}\n")
        assert response.status_code == 201

        # 4. Fetch messages by window_id
        print("4️⃣ Testing GET /chat/messages?window_id=...")
        response = await client.get(
            f"{BASE_URL}/chat/messages",
            params={"window_id": test_window_id, "limit": 10}
        )
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Total messages: {data['total']}")
        print(f"   From cache: {data['from_cache']}")
        print(f"   Messages: {len(data['messages'])} returned\n")
        assert response.status_code == 200
        assert data['total'] == 2

        # 5. Fetch again (should be from cache)
        print("5️⃣ Testing GET /chat/messages (cache hit)")
        response = await client.get(
            f"{BASE_URL}/chat/messages",
            params={"window_id": test_window_id, "limit": 10}
        )
        data = response.json()
        print(f"   From cache: {data['from_cache']}")
        print(f"   Total: {data['total']}\n")
        assert data['from_cache'] is True

        # 6. Lookup user_id
        print("6️⃣ Testing GET /chat/user-id?window_id=...")
        response = await client.get(
            f"{BASE_URL}/chat/user-id",
            params={"window_id": test_window_id}
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}\n")
        assert response.status_code == 200

        # 7. Delete message
        print("7️⃣ Testing DELETE /chat/messages/{id}")
        response = await client.delete(f"{BASE_URL}/chat/messages/{msg1_id}")
        print(f"   Status: {response.status_code}")
        assert response.status_code == 204
        print(f"   Message {msg1_id} deleted\n")

        # 8. Verify deletion
        print("8️⃣ Testing GET /chat/messages (after delete)")
        response = await client.get(
            f"{BASE_URL}/chat/messages",
            params={"window_id": test_window_id, "limit": 10}
        )
        data = response.json()
        print(f"   Total messages: {data['total']}")
        assert data['total'] == 1
        print(f"   ✅ Message deleted successfully\n")

    print("✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_chat_service())
