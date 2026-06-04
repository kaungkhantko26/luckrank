import os
import unittest
from tempfile import NamedTemporaryFile
from unittest.mock import patch

from decision_support import (
    Route,
    analysis_to_dict,
    compact_route,
    load_dotenv,
    local_fallback_analysis,
    local_fallback_routes,
    normalize_action_plan,
    parse_routes,
    repeated_success_probability,
    route_to_dict,
    should_exit,
)


class DecisionSupportTests(unittest.TestCase):
    def test_load_dotenv_sets_missing_values(self):
        with NamedTemporaryFile("w", encoding="utf-8") as env_file:
            env_file.write("OPENROUTER_API_KEY=test-key\n")
            env_file.flush()

            with patch.dict("os.environ", {}, clear=True):
                load_dotenv(env_file.name)
                self.assertEqual("test-key", os.environ["OPENROUTER_API_KEY"])

    def test_repeated_success_probability(self):
        self.assertAlmostEqual(repeated_success_probability(0.2, 10), 0.8926258176)

    def test_should_exit(self):
        self.assertTrue(should_exit("quit"))
        self.assertTrue(should_exit(" EXIT "))
        self.assertFalse(should_exit("start a business"))

    def test_normalize_action_plan_splits_numbered_string(self):
        self.assertEqual(
            normalize_action_plan("1. Book appointment. 2. Bring draft. 3. Apply feedback."),
            ["Book appointment.", "Bring draft.", "Apply feedback."],
        )

    def test_luck_adjusts_probability_with_cap(self):
        route = Route(
            name="Freelancing",
            probability=0.75,
            reward=8,
            cost=2,
            time=3,
            risk=3,
            do=8,
            show=7,
            reason="Strong skill match",
            action_plan=[],
        )

        self.assertAlmostEqual(route.luck, 15)
        self.assertAlmostEqual(route.adjusted_probability, 0.8625)

    def test_route_to_dict_exports_web_fields(self):
        route = Route(
            name="Freelancing",
            probability=0.75,
            reward=8,
            cost=2,
            time=3,
            risk=3,
            do=8,
            show=7,
            reason="Strong skill match",
            action_plan=["Start outreach"],
        )

        data = route_to_dict(route)

        self.assertEqual(data["name"], "Freelancing")
        self.assertEqual(data["action_plan"], ["Start outreach"])
        self.assertIn("score", data)

    def test_compact_route_limits_text_and_steps(self):
        route = Route(
            name="A very long route name that should be shortened for display",
            probability=0.75,
            reward=8,
            cost=2,
            time=3,
            risk=3,
            do=8,
            show=7,
            reason="This is a very long explanation that should be shortened because the web report should stay compact for the user.",
            action_plan=[
                "This is a long action step that should also be shortened for display",
                "Second step",
                "Third step",
                "Fourth step should not be included",
            ],
        )

        compact = compact_route(route)

        self.assertLessEqual(len(compact.name.split()), 7)
        self.assertLessEqual(len(compact.reason.split()), 15)
        self.assertEqual(len(compact.action_plan), 2)
        self.assertLessEqual(len(compact.action_plan[0].split()), 10)

    def test_local_fallback_returns_compact_routes(self):
        routes = local_fallback_routes("I need to choose a study plan")

        self.assertEqual(len(routes), 3)
        self.assertTrue(routes[0].action_plan)
        self.assertLessEqual(len(routes[0].action_plan), 2)

    def test_local_fallback_analysis_explains_data_quality(self):
        analysis = local_fallback_analysis("I need to choose a study plan")
        data = analysis_to_dict(analysis)

        self.assertIn("understanding", data)
        self.assertIn("data_note", data)
        self.assertEqual(len(data["routes"]), 3)

    def test_parse_routes_ranks_by_score(self):
        routes = parse_routes(
            {
                "routes": [
                    {
                        "name": "SaaS",
                        "probability": 0.2,
                        "reward": 10,
                        "cost": 9,
                        "time": 10,
                        "risk": 8,
                        "do": 6,
                        "show": 6,
                    },
                    {
                        "name": "Freelancing",
                        "probability": 0.75,
                        "reward": 7,
                        "cost": 2,
                        "time": 3,
                        "risk": 3,
                        "do": 8,
                        "show": 7,
                    },
                ]
            }
        )

        self.assertEqual(routes[0].name, "Freelancing")


if __name__ == "__main__":
    unittest.main()
