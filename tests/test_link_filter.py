import unittest

from handlers.anti_spam import _approved_link


class LinkFilterTests(unittest.TestCase):
    def test_allowlist_matches_domain_and_subdomain(self):
        allowed = ["https://example.com/rules"]
        self.assertTrue(_approved_link("https://example.com/anything", allowed))
        self.assertTrue(_approved_link("https://docs.example.com/path", allowed))

    def test_allowlist_does_not_match_lookalike_domain(self):
        self.assertFalse(_approved_link("https://example.com.attacker.test/path", ["https://example.com"]))


if __name__ == "__main__":
    unittest.main()
