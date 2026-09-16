import asyncio
import uvicorn

async def main():
    config = uvicorn.Config("app.main:app", host="127.0.0.1", port=8015)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
