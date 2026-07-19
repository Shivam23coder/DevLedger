import asyncio
import redis.asyncio as aioredis

async def main():
    url = "redis://localhost:6379/0"
    client = aioredis.from_url(url, decode_responses=True)
    try:
        # Get all keys matching "repo:*"
        keys = await client.keys("repo:*")
        print(f"Total keys found matching 'repo:*': {len(keys)}")
        for key in keys:
            val = await client.get(key)
            print(f"Key: {key}")
            # print snippet of value
            print(f"Value snippet: {val[:150]}...")
    except Exception as e:
        print(f"Error checking cache: {e}")
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
