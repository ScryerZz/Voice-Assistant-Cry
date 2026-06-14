import unittest
from unittest.mock import patch

from src.skills import news


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class NewsSkillTests(unittest.TestCase):
    def test_extract_query_removes_long_patterns_before_short_ones(self):
        self.assertEqual(news._extract_query("последние новости технологии"), "технологии")
        self.assertEqual(news._extract_query("найди последние новости про ии"), "ии")

    def test_generic_news_uses_top_headlines(self):
        config = {"news": {"api_key": "key"}}
        payload = {"articles": [{"url": "https://example.com/1"}, {"url": "https://example.com/2"}]}

        with (
            patch("src.skills.news.requests.get", return_value=FakeResponse(payload=payload)) as get,
            patch("src.skills.news.webbrowser.open") as open_browser,
        ):
            response = news.search_news(text="последние новости", config=config)

        self.assertIn("Нашёл 2 новости", response)
        self.assertEqual(open_browser.call_count, 2)
        self.assertEqual(get.call_args.args[0], "https://newsapi.org/v2/top-headlines")
        self.assertEqual(get.call_args.kwargs["params"]["country"], "ru")

    def test_topic_news_uses_everything_query(self):
        config = {"news": {"api_key": "key"}}
        payload = {"articles": [{"url": "https://example.com/1"}]}

        with (
            patch("src.skills.news.requests.get", return_value=FakeResponse(payload=payload)) as get,
            patch("src.skills.news.webbrowser.open") as open_browser,
        ):
            response = news.search_news(text="последние новости технологии", config=config)

        self.assertIn("«технологии»", response)
        self.assertEqual(open_browser.call_count, 1)
        self.assertEqual(get.call_args.args[0], "https://newsapi.org/v2/everything")
        self.assertEqual(get.call_args.kwargs["params"]["q"], "технологии")

    def test_generic_news_falls_back_when_top_headlines_empty(self):
        config = {"news": {"api_key": "key"}}
        empty = FakeResponse(payload={"articles": []})
        fallback = FakeResponse(payload={"articles": [{"url": "https://example.com/1"}]})

        with (
            patch("src.skills.news.requests.get", side_effect=[empty, fallback]) as get,
            patch("src.skills.news.webbrowser.open") as open_browser,
        ):
            response = news.search_news(text="последние новости", config=config)

        self.assertIn("Нашёл 1 новость", response)
        self.assertEqual(open_browser.call_count, 1)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[1].args[0], "https://newsapi.org/v2/everything")
        self.assertEqual(get.call_args_list[1].kwargs["params"]["q"], "Россия")


if __name__ == "__main__":
    unittest.main()
