"""Shared app extensions / configuration."""

import os

import openai

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# ``app`` is imported in paypal.py for DB access; keep the factory's app
# reference here so other modules do not need to import the factory.
app = None


def init_extensions(app):
    """Initialize extensions that need the app or environment."""
    openai.api_key = os.getenv("GROQ_API_KEY")
    openai.base_url = GROQ_BASE_URL


def get_openai_client():
    """Return the configured OpenAI client configured for Groq."""
    return openai
