"""AI generation for the ImpactFund AI campaign builder.

The Groq API is OpenAI-compatible, so we can use the ``openai`` package
with its base URL pointed at the Groq endpoint.
"""

import json
import os

import openai
from flask import current_app, render_template, request

from app.auth import organizer_required

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Minimal prompt used to turn a raw idea into a campaign plan. Kept short so
# the first call is cheap; can be replaced with a longer system prompt later.
SYSTEM_PROMPT = (
    "You are a crowdfunding campaign coach. Given an idea, a list of "
    "beneficiaries, and an optional budget, return a JSON object with "
    "story (2-4 sentences), suggested_budget (number), and milestones (array "
    "of 3 strings). Never return text outside the JSON object."
)


def create_ai_bp(app):
    """Mount the AI generator routes on the app."""

    @app.get("/ai/builder")
    @organizer_required
    def ai_builder():
        return render_template("ai_builder.html")

    @app.post("/ai/builder/generate")
    @organizer_required
    def ai_generate():
        form = {
            "idea": request.form.get("idea", "").strip()[:3000],
            "beneficiaries": request.form.get("beneficiaries", "").strip()[:300],
            "budget": request.form.get("budget", "").strip()[:20],
        }

        if not form["idea"]:
            return (
                render_template(
                    "ai_builder.html",
                    plan=None,
                    form=form,
                    error="Please describe your idea first.",
                ),
                400,
            )

        try:
            plan = _generate_plan(
                form["idea"], form["beneficiaries"], form["budget"]
            )
        except Exception:
            current_app.logger.exception("AI generation failed")
            return (
                render_template(
                    "ai_builder.html",
                    plan=None,
                    form=form,
                    error=(
                        "The AI builder could not generate a plan right now. "
                        "Please try again in a moment."
                    ),
                ),
                502,
            )

        return render_template(
            "ai_plan.html",
            plan=plan,
            idea=form["idea"],
            beneficiaries=form["beneficiaries"],
        )

    return app


def _generate_plan(idea, beneficiaries, budget):
    openai.api_key = os.getenv("GROQ_API_KEY")
    openai.base_url = GROQ_BASE_URL

    if not openai.api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    prompt = f"Ideas: {idea}\nBeneficiaries: {beneficiaries}\nBudget: {budget}"
    response = openai.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=400,
    )
    raw = response.choices[0].message.content or ""
    return _parse_plan(raw.strip())


def _parse_plan(raw):
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fall back to the last JSON object we can find in the response.
        start = raw.rfind("{")
        if start == -1:
            raise ValueError("Could not parse the AI response as JSON.")
        data = json.loads(raw[start:])

    if not isinstance(data, dict):
        raise ValueError("The AI response was not a JSON object.")

    story = data.get("story", "Your campaign story is being drafted.")

    try:
        suggested_budget = float(data.get("suggested_budget", 0) or 0)
    except (TypeError, ValueError):
        suggested_budget = 0

    milestones = data.get(
        "milestones",
        ["Draft your story", "Share with your community", "Reach your goal"],
    )
    if not isinstance(milestones, list):
        milestones = [milestones] if milestones else []
    milestones = [str(milestone) for milestone in milestones]

    return {
        "story": story,
        "suggested_budget": suggested_budget,
        "milestones": milestones,
    }
