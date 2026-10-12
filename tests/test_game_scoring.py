import unittest

from services.xp_service import fight_winner, level_for_xp


class GameScoringTests(unittest.TestCase):
    def test_fight_scoring_is_symmetric_and_draws_are_explicit(self):
        self.assertEqual(fight_winner(10, 10), 0)
        self.assertEqual(fight_winner(99, 20), 1)
        self.assertEqual(fight_winner(20, 99), 2)

    def test_uniform_roll_space_has_equal_win_and_loss_counts(self):
        outcomes = {0: 0, 1: 0, 2: 0}
        for first in range(1, 101):
            for second in range(1, 101):
                outcomes[fight_winner(first, second)] += 1
        self.assertEqual(outcomes[1], outcomes[2])
        self.assertEqual(outcomes[0], 100)

    def test_level_thresholds(self):
        self.assertEqual(level_for_xp(0), 1)
        self.assertEqual(level_for_xp(99), 1)
        self.assertEqual(level_for_xp(100), 2)
        self.assertEqual(level_for_xp(400), 3)


if __name__ == "__main__":
    unittest.main()
