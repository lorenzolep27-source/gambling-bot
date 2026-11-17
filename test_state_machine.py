"""Simulated polling sequences for the state machine. Run: python -m unittest -v

Segments are (player_total, dealer_total, border_colour, seconds).
"""
import unittest

from recorder import validate
from state_machine import HandTracker, Observation

HZ = 8
CLEAR = (None, None, None, 1.5)     # badges gone between hands


def run(segments):
    tr = HandTracker()
    t, out = 0.0, []
    for seg in segments:
        player, dealer, color, secs = seg[:4]
        action = seg[4] if len(seg) > 4 else None
        for _ in range(int(secs * HZ)):
            rec = tr.step(Observation(t, player, dealer, color, action))
            if rec:
                out.append(rec)
            t += 1.0 / HZ
    return out, tr


class TestStateMachine(unittest.TestCase):
    def test_stand_and_win(self):
        recs, tr = run([CLEAR, (18, 8, "blue", 3), (18, 17, "green", 3), CLEAR])
        r = recs[0]
        self.assertEqual((r.dealer_show, r.player_start, r.player_end, r.n_hit, r.stood, r.outcome),
                         ("8", 18, 18, 0, True, "win"))
        self.assertEqual(tr.mismatches, 0)

    def test_hits_then_loss(self):
        recs, _ = run([(11, 10, "blue", 2), (17, 10, "blue", 2), (19, 10, "blue", 2),
                       (19, 20, "red", 3), CLEAR])
        r = recs[0]
        self.assertEqual((r.n_hit, r.player_start, r.player_end, r.outcome, r.stood),
                         (2, 11, 19, "loss", True))

    def test_player_bust(self):
        recs, _ = run([(14, 9, "blue", 2), (25, 9, "red", 3), CLEAR])
        r = recs[0]
        self.assertEqual((r.outcome, r.n_hit, r.stood, r.player_end), ("bust", 1, False, 25))

    def test_border_flips_before_total(self):
        # red border stabilises before the busting total does: must still record the hit
        recs, _ = run([(14, 9, "blue", 2), (14, 9, "red", 0.5), (25, 9, "red", 3), CLEAR])
        self.assertEqual((recs[0].outcome, recs[0].n_hit), ("bust", 1))

    def test_dealer_bust_is_win(self):
        recs, tr = run([(16, 6, "blue", 2), (16, 22, "green", 3), CLEAR])
        self.assertEqual(recs[0].outcome, "win")
        self.assertEqual(tr.mismatches, 0)

    def test_push(self):
        recs, _ = run([(18, 7, "blue", 2), (18, 18, "yellow", 3), CLEAR])
        self.assertEqual(recs[0].outcome, "push")

    def test_player_blackjack(self):
        recs, _ = run([(21, 10, "blue", 2), (21, 19, "green", 3), CLEAR])
        r = recs[0]
        self.assertEqual((r.outcome, r.stood, r.n_hit), ("BJ", False, 0))

    def test_player_bj_badge_blue_then_green(self):
        recs, _ = run([("BJ", 10, "blue", 1), ("BJ", 19, "green", 2), CLEAR])
        r = recs[0]
        self.assertEqual((r.player_start, r.player_end, r.n_hit, r.stood, r.outcome),
                         (21, 21, 0, False, "BJ"))

    def test_player_bj_badge_immediate_green(self):
        # Natural BJ often turns green immediately without dwelling on blue
        recs, _ = run([CLEAR, ("BJ", 10, "green", 2), CLEAR])
        r = recs[0]
        self.assertEqual((r.player_start, r.player_end, r.n_hit, r.stood, r.outcome),
                         (21, 21, 0, False, "BJ"))

    def test_ace_upcard_label(self):
        recs, _ = run([(12, 11, "blue", 2), (12, 20, "red", 3), CLEAR])
        self.assertEqual(recs[0].dealer_show, "A")

    def test_ocr_flicker_ignored(self):
        recs, _ = run([(18, 8, "blue", 2), (11, 8, "blue", 0.125), (18, 8, "blue", 2),
                       (18, 17, "green", 3), CLEAR])
        self.assertEqual(recs[0].n_hit, 0)

    def test_long_thinking_does_not_end_hand(self):
        recs, _ = run([(15, 10, "blue", 120), (15, 18, "red", 3), CLEAR])
        self.assertEqual(recs[0].outcome, "loss")

    def test_dealer_natural_discarded(self):
        recs, tr = run([(15, 10, "blue", 1), (15, 21, "red", 3), CLEAR])
        self.assertEqual(recs, [])
        self.assertEqual(tr.discarded, 1)

    def test_back_to_back_hands_colour_resets(self):
        # no badge-clear between hands: border returning to blue starts the next hand
        recs, _ = run([(18, 8, "blue", 2), (18, 17, "green", 3),
                       (13, 10, "blue", 2), (13, 20, "red", 3), CLEAR])
        self.assertEqual([r.outcome for r in recs], ["win", "loss"])

    def test_badges_lost_discards(self):
        recs, tr = run([(15, 10, "blue", 2), (None, None, None, 5), CLEAR])
        self.assertEqual(recs, [])
        self.assertEqual(tr.discarded, 1)

    def test_midhand_deal_ignored_until_plausible(self):
        recs, _ = run([(3, 10, "blue", 1), (13, 10, "blue", 2), (13, 19, "red", 3), CLEAR])
        self.assertEqual(recs[0].player_start, 13)

    def test_colour_total_mismatch_counted(self):
        # green but totals say loss: trust the game, flag the disagreement
        recs, tr = run([(15, 10, "blue", 2), (15, 19, "green", 3), CLEAR])
        self.assertEqual(recs[0].outcome, "win")
        self.assertEqual(tr.mismatches, 1)

    def test_dealer_natural_after_slow_insurance_decline(self):
        # ace upcard: player takes 8 s to decline insurance, then dealer reveals blackjack
        recs, tr = run([(15, 11, "blue", 8), (15, 21, "red", 3), CLEAR])
        self.assertEqual(recs, [])
        self.assertEqual(tr.discarded, 1)

    def test_ace_upcard_dealer_21_after_stand_is_kept(self):
        # player actually stood (palm icon) and dealer drew to 21: a real hand
        recs, _ = run([(15, 11, "blue", 8, None), (15, 11, "blue", 2, "stand"),
                       (15, 21, "red", 3, "stand"), CLEAR])
        self.assertEqual((recs[0].outcome, recs[0].stood, recs[0].dealer_show),
                         ("loss", True, "A"))

    def test_fast_play_result_flashes_briefly(self):
        # Result border visible for only ~0.3 s before the next hand is dealt: every
        # hand must still be recorded, with no clear gap between them.
        recs, tr = run([
            (18, 8, "blue", 2), (18, 17, "green", 0.3),
            (13, 10, "blue", 2, None), (13, 10, "blue", 0.5, "hit"), (20, 10, "blue", 1, "hit"),
            (20, 18, "green", 0.3),
            (17, 9, "blue", 2), (17, 19, "red", 0.3),
            (15, 6, "blue", 2),
        ])
        self.assertEqual([(r.player_start, r.player_end, r.n_hit, r.outcome) for r in recs],
                         [(18, 18, 0, "win"), (13, 20, 1, "win"), (17, 17, 0, "loss")])

    def test_badges_vanish_right_after_result(self):
        recs, tr = run([(18, 8, "blue", 2), (18, 17, "green", 0.3), CLEAR])
        self.assertEqual(len(recs), 1)
        self.assertEqual(tr.discarded, 0)

    def test_loss_after_one_hit_with_unreadable_badge_on_result(self):
        # win, then hit once and lose; the player badge OCR returns nothing while the
        # red result border is showing. The loss must still be recorded.
        recs, tr = run([
            (18, 8, "blue", 2), (18, 17, "green", 3), CLEAR,
            (12, 10, "blue", 2, None), (17, 10, "blue", 2, "hit"), (17, 10, "blue", 2, "stand"),
            (None, None, "red", 4, "stand"), CLEAR,
        ])
        self.assertEqual(tr.discarded, 0)
        self.assertEqual([(r.outcome, r.n_hit) for r in recs], [("win", 0), ("loss", 1)])

    def test_loss_after_one_hit(self):
        recs, _ = run([(12, 10, "blue", 2), (17, 10, "blue", 2, "hit"),
                       (17, 10, "blue", 1, "stand"), (17, 20, "red", 3, "stand"), CLEAR])
        r = recs[0]
        self.assertEqual((r.n_hit, r.player_end, r.outcome, r.stood), (1, 17, "loss", True))

    def test_hand_starts_even_if_border_unreadable_at_deal(self):
        # border reads None (not blue) the whole time until the result colour appears
        recs, tr = run([CLEAR, (18, 10, None, 4), (18, 10, None, 2, "stand"),
                        (18, 19, "red", 3), CLEAR])
        self.assertEqual([(r.player_start, r.outcome) for r in recs], [(18, "loss")])

    def test_unreadable_border_with_old_icon_does_not_start_hand(self):
        # mid-dealer-turn leftovers (grey border + an action icon) must not start a hand
        recs, tr = run([CLEAR, (18, 10, None, 4, "stand"), CLEAR])
        self.assertEqual(recs, [])
        self.assertEqual(tr.state.name, "WAIT_HAND")

    def test_validate(self):
        recs, _ = run([(18, 8, "blue", 2), (18, 17, "green", 3), CLEAR])
        self.assertIsNone(validate(recs[0]))

    # -- last-action icon (5th tuple element) ---------------------------------
    def test_icon_stand(self):
        recs, _ = run([(18, 8, "blue", 2, None), (18, 8, "blue", 2, "stand"),
                       (18, 17, "green", 3, "stand"), CLEAR])
        self.assertEqual((recs[0].stood, recs[0].n_hit), (True, 0))

    def test_icon_hit_to_21_is_not_stood(self):
        # hit to 21 ends play automatically: icon stays 'hit', so stood is False
        recs, _ = run([(11, 10, "blue", 2, None), (21, 10, "blue", 2, "hit"),
                       (21, 19, "green", 3, "hit"), CLEAR])
        r = recs[0]
        self.assertEqual((r.n_hit, r.stood, r.outcome), (1, False, "win"))

    def test_icon_hit_catches_same_total_hit(self):
        # soft 17 hits a 10 and stays at 17: total never changes, icon proves the hit,
        # then the player stands
        recs, _ = run([(17, 9, "blue", 2, None), (17, 9, "blue", 2, "hit"),
                       (17, 9, "blue", 2, "stand"), (17, 20, "red", 3, "stand"), CLEAR])
        self.assertEqual(recs[0].n_hit, 1)
        self.assertTrue(recs[0].stood)

    def test_stale_icon_from_previous_hand_ignored(self):
        # icon 'stand' lingers into the next hand (never changes): don't trust it,
        # fall back to inference rather than copying the old action
        recs, _ = run([(18, 8, "blue", 2, "stand"), (18, 17, "green", 3, "stand"),
                       (25, 8, "blue", 0.0, None),
                       (14, 9, "blue", 2, "stand"), (25, 9, "red", 3, "stand"), CLEAR])
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[1].outcome, "bust")
        self.assertFalse(recs[1].stood)


if __name__ == "__main__":
    unittest.main()
