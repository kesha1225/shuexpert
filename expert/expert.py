import asyncio
from datetime import datetime

import aiohttp
import requests

from expert.exceptions import NotAnExpertException
from expert.strategy import *


class ExpertBase:
    def __init__(self, login: str, password: str):
        self.session = aiohttp.ClientSession()
        self.base_url = "https://api.vk.com/method/"
        self.login = login
        self.password = password

        self.access_token = self.get_token()
        self.expert_token = self.get_expert_token()

        self.feed_types_dict = {
            7: "IT",
            12: "Games",
            16: "Music",
            19: "Photo",
            21: "Science",
            32: "Humor",
        }

    @staticmethod
    def format_error(response: dict) -> str:
        error = response["error"]
        return f"[{error['error_code']}] {error['error_msg']}"

    async def api_request(self, method: str, params: dict = None) -> dict:
        if params is None:
            params = {}

        base_params = {"v": "5.109", "access_token": self.access_token}
        base_params.update(params)

        async with self.session.get(
            self.base_url + method, params=base_params
        ) as response:
            response = await response.json()
            if response.get("error") and response["error"]["error_code"] == 5:
                print("Creating new token...")
                self.expert_token = self.get_expert_token()
                return await self.api_request(method, params)

            elif response.get("error"):
                print(self.format_error(response))
                await asyncio.sleep(5)
                return await self.api_request(method, params)
            return response

    def get_token(self) -> str:
        params = {
            "grant_type": "password",
            "scope": "all",
            "client_id": 2274003,
            "client_secret": "hHbZxrka2uZ6jB1inYsH",
            "username": self.login,
            "password": self.password,
            "2fa_supported": 1,
            "v": "5.109",
        }

        token = requests.get("https://oauth.vk.com/token", params=params).json()
        return token["access_token"]

    def get_expert_token(self) -> str:
        params = {
            "source_url": "https://static.vk.com/experts/?vk_access_token_settings=notify,menu",
            "redirect_uri": "https://oauth.vk.com/blank.html",
            "client_id": 7171491,
            "vk_app_id": 7171491,
            "access_token": self.access_token,
            "response_type": "token",
            "v": "5.116",
        }

        url = requests.get("https://oauth.vk.com/authorize", params=params).url
        expert_token = url.split("access_token")[1].split("=")[1].split("&")[0]
        return expert_token


class Expert(ExpertBase):
    def __init__(
        self,
        login: str,
        password: str,
        strategy: "BaseStrategy" = BaseStrategy,
        feed_id: int = 7,
    ):
        self.strategy = strategy
        self.feed_id = feed_id

        self.voted = 0
        self.skipped = []

        super().__init__(login, password)

    async def get_feed_posts(self, start_from: int) -> dict:
        params = {
            "count": 50,
            "start_from": start_from,
            "extended": 1,
            "feed_id": f"discover_category_full/{self.feed_id}",
        }

        posts = await self.api_request("execute.getNewsfeedCustom", params)
        return posts

    async def get_expert_card(self) -> dict:
        params = {"access_token": self.expert_token}
        response = await self.api_request("newsfeed.getExpertCard", params=params)
        if response["response"] == 0:
            raise NotAnExpertException(f"{self.login} is not an expert")
        return response

    async def vote(self, owner_id: int, post_id: int, rating: int):
        vote = self.strategy.select_vote(self.strategy, rating)
        if vote is None:
            return

        params = {
            "new_vote": vote,
            "post_id": post_id,
            "owner_id": owner_id,
        }

        await self.api_request("newsfeed.setPostVote", params)
        self.voted += 1
        await asyncio.sleep(0.33)

    async def output_stats(self, loop: int):
        expert_card = await self.get_expert_card()
        expert_card = expert_card["response"]

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"({expert_card['first_name']} {expert_card['last_name']}:"
            f" {self.feed_types_dict[self.feed_id]})"
            f" [{now} {self.strategy.__name__}] Loop #{loop}."
            f" Rating: {expert_card['points']}."
            f" Votes/skips - {self.voted}/{len(self.skipped)}"
        )

    async def vote_forever(self):
        start_from = i = 0

        while True:
            feed_posts = await self.get_feed_posts(start_from)

            items = feed_posts["response"]["items"]
            for item in items:
                if item["rating"]["rated"] != 0:
                    if item["track_code"] not in self.skipped:  # Don't count the same post as skipped
                        self.skipped.append(item["track_code"])
                    continue

                rating = int(item["rating"]["value"])
                await self.vote(
                    owner_id=item["source_id"], post_id=item["post_id"], rating=rating
                )

            start_from = feed_posts["response"]["next_from"]
            if not start_from:
                if i % 5 == 0:  # Output stats every 5 loops
                    await self.output_stats(i)
                start_from = 0
                i += 1


class CombineExperts:
    def __init__(self, acc_file=None, *experts: Expert):
        self.experts = list(experts)

        if acc_file is not None:
            with open(acc_file) as file:
                accounts = file.read().split("\n")
            for account in accounts:
                if not account.split(":")[0]:
                    continue
                if len(account.split(":")) < 4:
                    login, password, feed_id = account.split(":")
                    strategy = BaseStrategy
                else:
                    login, password, feed_id, strategy = account.split(":")
                    strategy = eval(strategy)

                expert = Expert(
                    login=login,
                    password=password,
                    feed_id=int(feed_id),
                    strategy=strategy,
                )
                self.experts.append(expert)

    async def vote_forever(self):
        loop = asyncio.get_running_loop()
        for expert in self.experts:
            await expert.get_expert_card()  # Make sure the account is expert
            loop.create_task(expert.vote_forever())
