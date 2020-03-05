import asyncio

from expert.expert import CombineExperts


async def main():
    experts = CombineExperts(acc_file="accounts.txt")
    await experts.vote_forever()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
