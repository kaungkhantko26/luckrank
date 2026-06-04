#!/usr/bin/env python3
"""AI decision support system using OpenRouter model routing."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/auto"
DEFAULT_FALLBACK_MODELS = (
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o-mini",
    "google/gemini-flash-1.5",
)
DEFAULT_TIMEOUT_SECONDS = 8


def load_dotenv(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs without adding a runtime dependency."""
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


@dataclass(frozen=True)
class Route:
    name: str
    probability: float
    reward: float
    cost: float
    time: float
    risk: float
    do: float
    show: float
    reason: str
    action_plan: list[str]

    @property
    def luck(self) -> float:
        return self.do + self.show

    @property
    def adjusted_probability(self) -> float:
        """Blend base odds with execution and visibility.

        `Luck = Do + Show` is treated as an action multiplier, capped so the
        decision score stays realistic instead of pretending effort guarantees
        success.
        """
        luck_multiplier = 1 + min(max(self.luck, 0), 20) / 100
        return min(self.probability * luck_multiplier, 0.95)

    @property
    def score(self) -> float:
        denominator = safe_positive(self.cost) * safe_positive(self.time) * safe_positive(self.risk)
        return (self.adjusted_probability * safe_positive(self.reward)) / denominator


@dataclass(frozen=True)
class Analysis:
    understanding: str
    data_note: str
    assumptions: list[str]
    routes: list[Route]


def safe_positive(value: float) -> float:
    return max(float(value), 0.01)


def repeated_success_probability(p: float, n: int) -> float:
    return 1 - (1 - p) ** n


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        fallback_models: tuple[str, ...] = DEFAULT_FALLBACK_MODELS,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.fallback_models = fallback_models

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        errors: list[str] = []
        for model in (self.model, *self.fallback_models):
            try:
                return self._request(model, messages)
            except RuntimeError as exc:
                errors.append(f"{model}: {exc}")
        raise RuntimeError("All OpenRouter models failed:\n" + "\n".join(errors))

    def _request(self, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        body = {
            "model": model,
            "route": "fallback",
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.25,
        }
        request = urllib.request.Request(
            OPENROUTER_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
                "X-Title": os.getenv("OPENROUTER_APP_NAME", "AI Decision Support System"),
            },
            method="POST",
        )

        try:
            timeout = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(str(exc)) from exc

        try:
            content = payload["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid model response: {payload}") from exc


def build_prompt(problem: str, factors: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You generate decision routes as strict JSON. First understand the "
                "user's real problem from their words. Return an object with "
                "understanding, data_note, assumptions, and routes. understanding must "
                "be one short sentence. data_note must state that user input is factual "
                "and probabilities/scores are estimates unless verified data was "
                "provided. assumptions must be an array of up to 2 short assumptions. "
                "routes must be an array. Each route must include name, probability, reward, "
                "cost, time, risk, do, show, reason, and action_plan. probability is "
                "0-1. reward, cost, time, risk, do, and show are numeric 1-10. "
                "Return exactly 3 routes. Keep route names under 6 words. Keep reason "
                "under 14 words. action_plan must be an array of exactly 2 short step "
                "strings, not one long string. Each action step must be under 9 words. "
                "Do not invent external facts, prices, rules, deadlines, laws, or live "
                "market data. If the user did not provide a fact, treat it as an "
                "assumption. Use realistic estimates and avoid claiming certainty."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "problem": problem,
                    "factors": factors,
                    "scoring_formula": "Score = (P_success * Reward) / (Cost * Time * Risk)",
                    "luck_formula": "Luck = Do + Show",
                }
            ),
        },
    ]


def normalize_action_plan(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(step).strip() for step in value if str(step).strip()]
    if not isinstance(value, str):
        return []

    text = value.strip()
    if not text:
        return []

    steps: list[str] = []
    current = ""
    index = 0
    while index < len(text):
        if text[index].isdigit() and index + 1 < len(text) and text[index + 1] == ".":
            if current.strip():
                steps.append(current.strip())
            index += 2
            current = ""
            continue
        current += text[index]
        index += 1
    if current.strip():
        steps.append(current.strip())
    return steps or [text]


def parse_routes(data: dict[str, Any]) -> list[Route]:
    routes: list[Route] = []
    for item in data.get("routes", []):
        routes.append(
            Route(
                name=str(item["name"]),
                probability=float(item["probability"]),
                reward=float(item["reward"]),
                cost=float(item["cost"]),
                time=float(item["time"]),
                risk=float(item["risk"]),
                do=float(item.get("do", 5)),
                show=float(item.get("show", 5)),
                reason=str(item.get("reason", "")),
                action_plan=normalize_action_plan(item.get("action_plan", [])),
            )
        )
    if not routes:
        raise ValueError("No routes were returned by the model.")
    return sorted(routes, key=lambda route: route.score, reverse=True)


def parse_analysis(data: dict[str, Any]) -> Analysis:
    routes = parse_routes(data)
    assumptions = data.get("assumptions", [])
    if not isinstance(assumptions, list):
        assumptions = [str(assumptions)]

    return Analysis(
        understanding=trim_words(str(data.get("understanding", "I understood the problem and ranked practical options.")), 16),
        data_note=trim_words(
            str(
                data.get(
                    "data_note",
                    "User input is factual; probabilities and scores are estimates.",
                )
            ),
            18,
        ),
        assumptions=[trim_words(str(item), 12) for item in assumptions[:2] if str(item).strip()],
        routes=routes,
    )


def local_fallback_routes(problem: str) -> list[Route]:
    """Fast rule-based routes so the web app never gets stuck on an API call."""
    normalized_problem = trim_words(problem, 8) if problem.strip() else "your problem"
    routes = [
        Route(
            name="Quick practical plan",
            probability=0.68,
            reward=7,
            cost=2,
            time=2,
            risk=3,
            do=8,
            show=4,
            reason=f"Fastest low-cost way to act on {normalized_problem}.",
            action_plan=["Define one clear target", "Do the next small task"],
        ),
        Route(
            name="Ask expert help",
            probability=0.62,
            reward=8,
            cost=4,
            time=3,
            risk=2,
            do=5,
            show=5,
            reason="Outside feedback reduces mistakes and improves direction.",
            action_plan=["Ask one qualified person", "Apply the best feedback"],
        ),
        Route(
            name="Test small version",
            probability=0.58,
            reward=9,
            cost=3,
            time=4,
            risk=4,
            do=7,
            show=7,
            reason="A small test gives evidence before bigger effort.",
            action_plan=["Run one small experiment", "Keep what works"],
        ),
    ]
    return [compact_route(route) for route in sorted(routes, key=lambda route: route.score, reverse=True)]


def local_fallback_analysis(problem: str) -> Analysis:
    normalized_problem = trim_words(problem, 12) if problem.strip() else "your problem"
    return Analysis(
        understanding=f"You want the best practical route for: {normalized_problem}.",
        data_note="User input is real; scores are rule-based estimates.",
        assumptions=["Limited facts provided", "Lower cost and time are preferred"],
        routes=local_fallback_routes(problem),
    )


def route_to_dict(route: Route) -> dict[str, Any]:
    return {
        "name": route.name,
        "probability": route.probability,
        "adjusted_probability": route.adjusted_probability,
        "reward": route.reward,
        "cost": route.cost,
        "time": route.time,
        "risk": route.risk,
        "do": route.do,
        "show": route.show,
        "luck": route.luck,
        "score": route.score,
        "reason": route.reason,
        "action_plan": route.action_plan,
    }


def analysis_to_dict(analysis: Analysis) -> dict[str, Any]:
    return {
        "understanding": analysis.understanding,
        "data_note": analysis.data_note,
        "assumptions": analysis.assumptions,
        "routes": [route_to_dict(route) for route in analysis.routes],
        "best_route": route_to_dict(analysis.routes[0]),
    }


def generate_analysis(client: OpenRouterClient, problem: str, factors: dict[str, str]) -> Analysis:
    response = client.complete_json(build_prompt(problem, factors))
    analysis = parse_analysis(response)
    return Analysis(
        understanding=analysis.understanding,
        data_note=analysis.data_note,
        assumptions=analysis.assumptions,
        routes=[compact_route(route) for route in analysis.routes[:3]],
    )


def analyze_problem_data(client: OpenRouterClient, problem: str, factors: dict[str, str]) -> list[Route]:
    return generate_analysis(client, problem, factors).routes


def ask(label: str) -> str:
    return input(f"{label}\n> ").strip()


def collect_inputs() -> tuple[str, dict[str, str]]:
    problem = ask("Hi. What problem are you trying to solve?")
    return problem, {"input_style": "single prompt; infer missing factors carefully"}


def should_exit(value: str) -> bool:
    return value.strip().lower() in {"q", "quit", "exit", "stop"}


def trim_text(value: str, max_width: int) -> str:
    value = " ".join(value.split())
    if len(value) <= max_width:
        return value
    return value[: max_width - 3].rstrip() + "..."


def trim_words(value: str, max_words: int) -> str:
    words = value.split()
    if len(words) <= max_words:
        return value
    return " ".join(words[:max_words]).rstrip(".,") + "..."


def compact_route(route: Route) -> Route:
    return Route(
        name=trim_words(route.name, 6),
        probability=route.probability,
        reward=route.reward,
        cost=route.cost,
        time=route.time,
        risk=route.risk,
        do=route.do,
        show=route.show,
        reason=trim_words(route.reason, 14),
        action_plan=[trim_words(step, 9) for step in route.action_plan[:2]],
    )


def print_table(routes: list[Route]) -> None:
    headers = ("#", "Route", "Success", "Reward", "Cost", "Time", "Risk", "Luck", "Score")
    rows = [
        (
            str(index),
            trim_text(route.name, 31),
            f"{route.adjusted_probability:.0%}",
            f"{route.reward:.1f}",
            f"{route.cost:.1f}",
            f"{route.time:.1f}",
            f"{route.risk:.1f}",
            f"{route.luck:.1f}",
            f"{route.score:.4f}",
        )
        for index, route in enumerate(routes, start=1)
    ]
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]

    border = "+-" + "-+-".join("-" * width for width in widths) + "-+"
    header = "| " + " | ".join(cell.ljust(width) for cell, width in zip(headers, widths)) + " |"
    print(border)
    print(header)
    print(border)
    for row in rows:
        print("| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |")
    print(border)


def print_report(problem: str, routes: list[Route]) -> None:
    best = routes[0]
    print("\nAI Decision Support Report")
    print("=" * 26)
    print(f"\nProblem: {problem}")
    print("\nRoute Ranking")
    print_table(routes)
    print("\nBest Route")
    print("-" * 10)
    print(best.name)
    print(f"Success Probability: {best.adjusted_probability:.0%}")
    print(f"Score: {best.score:.4f}")
    print(f"Formula: ({best.adjusted_probability:.2f} * {best.reward:.1f}) / ({best.cost:.1f} * {best.time:.1f} * {best.risk:.1f})")
    print(f"Luck: Do {best.do:.1f} + Show {best.show:.1f} = {best.luck:.1f}")
    print(f"Reason: {best.reason}")
    if best.action_plan:
        print("\nAction Plan:")
        for index, step in enumerate(best.action_plan, start=1):
            print(f"{index}. {step}")


def analyze_problem(client: OpenRouterClient, problem: str, factors: dict[str, str]) -> None:
    routes = analyze_problem_data(client, problem, factors)
    print_report(problem, routes)


def create_client(api_key: str, use_fallbacks: bool = True) -> OpenRouterClient:
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    if use_fallbacks:
        fallbacks = tuple(
            model.strip()
            for model in os.getenv("OPENROUTER_FALLBACK_MODELS", ",".join(DEFAULT_FALLBACK_MODELS)).split(",")
            if model.strip()
        )
    else:
        fallbacks = ()
    return OpenRouterClient(api_key=api_key, model=model, fallback_models=fallbacks)


def run_chat_loop(client: OpenRouterClient) -> int:
    print("AI Decision Support Chat")
    print("Type quit, exit, stop, or q to close.\n")

    while True:
        problem, factors = collect_inputs()
        if should_exit(problem):
            print("Goodbye.")
            return 0
        if not problem:
            print("Please enter a problem, or type quit to close.\n")
            continue

        try:
            analyze_problem(client, problem, factors)
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            print(f"\nError: {exc}", file=sys.stderr)
            print("Try another problem, or type quit to close.\n")
            continue

        print("\nAsk another problem, or type quit to close.\n")


def run(problem: str | None = None, factors_json: str | None = None) -> int:
    load_dotenv()

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Missing OPENROUTER_API_KEY. Add it to .env or your environment first.", file=sys.stderr)
        return 2

    client = create_client(api_key)
    if problem is None:
        return run_chat_loop(client)

    factors = json.loads(factors_json or "{}")
    analyze_problem(client, problem, factors)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Decision Support System")
    parser.add_argument("--problem", help="Problem to analyze. If omitted, starts interactive mode.")
    parser.add_argument("--factors-json", help="JSON object with budget, time, skills, risk, etc.")
    args = parser.parse_args()
    return run(problem=args.problem, factors_json=args.factors_json)


if __name__ == "__main__":
    raise SystemExit(main())
