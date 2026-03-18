import unittest
from main import get_api_base_from_url

class TestUrlLogic(unittest.TestCase):
    def test_dev88(self):
        url = "https://dev88.newtalk.tw/news/view/2025-01-22/123"
        self.assertEqual(get_api_base_from_url(url), "https://dev88.newtalk.tw/aiArticle")

    def test_stage(self):
        url = "https://stage.newtalk.tw/news/view/2025-01-22/123"
        self.assertEqual(get_api_base_from_url(url), "https://stage.newtalk.tw/aiArticle")

    def test_prod(self):
        url = "https://newtalk.tw/news/view/2025-01-22/123"
        self.assertEqual(get_api_base_from_url(url), "https://api.newtalk.tw/aiArticle")

    def test_prod_www(self):
        url = "https://www.newtalk.tw/news/view/2025-01-22/123"
        self.assertEqual(get_api_base_from_url(url), "https://api.newtalk.tw/aiArticle")

    def test_ambiguous_dev(self):
        # This currently hits "newtalk.tw" in the OLD logic if using 'in', which is dangerous.
        # In NEW logic, hostname 'dev-other.newtalk.tw' != 'newtalk.tw', so it returns DEFAULT (stage).
        url = "https://dev-other.newtalk.tw/news/view/123"
        # DEFAULT_API_BASE in main.py is "https://stage.newtalk.tw/aiArticle" by default
        expected = "https://stage.newtalk.tw/aiArticle" 
        self.assertEqual(get_api_base_from_url(url), expected)

if __name__ == '__main__':
    unittest.main()
