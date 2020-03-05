class BaseStrategy:
    upvote_value = 20
    downvote_value = -10

    def select_vote(self, rating: int):
        if rating >= self.upvote_value:
            return "+1"
        elif rating <= self.downvote_value:
            return "-1"
        return None


class TenStrategy(BaseStrategy):
    upvote_value = 10
    downvote_value = -10

    def __init__(self):
        super().__init__()


class FiveStrategy(BaseStrategy):
    upvote_value = 5
    downvote_value = -5

    def __init__(self):
        super().__init__()


class ShueStrategy(BaseStrategy):
    upvote_value = 1
    downvote_value = -1

    def __init__(self):
        super().__init__()
