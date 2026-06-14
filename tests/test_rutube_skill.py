import unittest
from unittest.mock import patch

from src.skills import rutube, youtube


class RutubeSkillTests(unittest.TestCase):
    def test_search_rutube_opens_rutube_search_url(self):
        with patch("src.skills.rutube.webbrowser.open") as open_browser:
            response = rutube.search_rutube(text="найди на рутубе новости технологий")

        self.assertEqual(response, "Ищу на Rutube: новости технологий")
        open_browser.assert_called_once_with("https://rutube.ru/search/?query=%D0%BD%D0%BE%D0%B2%D0%BE%D1%81%D1%82%D0%B8+%D1%82%D0%B5%D1%85%D0%BD%D0%BE%D0%BB%D0%BE%D0%B3%D0%B8%D0%B9")

    def test_legacy_youtube_skill_redirects_to_rutube(self):
        with patch("src.skills.rutube.webbrowser.open") as open_browser:
            response = youtube.search_youtube(text="найди на ютубе обучение python")

        self.assertEqual(response, "Ищу на Rutube: обучение python")
        open_browser.assert_called_once()
        self.assertTrue(open_browser.call_args.args[0].startswith("https://rutube.ru/search/?query="))

    def test_empty_query_does_not_open_browser(self):
        with patch("src.skills.rutube.webbrowser.open") as open_browser:
            response = rutube.search_rutube(text="рутуб")

        self.assertEqual(response, "Не понял, что искать на Rutube.")
        open_browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
