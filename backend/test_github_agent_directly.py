import asyncio
import time
import httpx
from app.agents.github_agent import analyze_user, redis_client

async def flush_cache():
    if redis_client:
        try:
            keys = await redis_client.keys("repo:*")
            if keys:
                print(f"Flushing {len(keys)} cached keys from Redis...")
                await redis_client.delete(*keys)
        except Exception as e:
            print(f"Failed to flush Redis: {e}")

async def main():
    # Set env vars or settings if needed
    from app.config import settings
    print(f"Database URL: {settings.database_url}")
    print(f"GitHub Token present: {bool(settings.github_token)}")
    print(f"Redis URL: {settings.redis_url}")
    
    await flush_cache()

    username = "octocat"
    
    async with httpx.AsyncClient() as client:
        # Run 1 (Cache Miss)
        print("\n--- AGENT RUN 1: Cache Miss ---")
        start = time.time()
        repos_1 = await analyze_user(username, client=client, limit=5)
        elapsed_1 = time.time() - start
        print(f"Run 1 completed in: {elapsed_1:.4f} seconds")
        print(f"Analyzed {len(repos_1)} repos.")

        # Run 2 (Cache Hit)
        print("\n--- AGENT RUN 2: Cache Hit ---")
        start = time.time()
        repos_2 = await analyze_user(username, client=client, limit=5)
        elapsed_2 = time.time() - start
        print(f"Run 2 completed in: {elapsed_2:.4f} seconds")
        print(f"Speedup factor: {elapsed_1 / elapsed_2:.1f}x")
        
    if redis_client:
        await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
