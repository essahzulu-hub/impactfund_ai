# Hackathon Submission — ImpactFund AI

## Project overview
ImpactFund AI is a Flask crowdfunding platform that pairs **PayPal** (sandbox) with an
**AI** layer (Groq LLM). Users can make an impact case, get an AI-generated campaign plan,
create a fundraising campaign, and accept donations through PayPal.

## Features
- Email/password accounts with two roles: donor and project creator
- Facebook-style fundraising feed (stories, composer, posts, search)
- AI campaign builder (project creators)
- Campaign creation owned by the signed-in project creator
- Amount-aware PayPal sandbox donations (signed-in users)
- Campaign detail pages with progress and sharing

## Accounts and roles
Signup stores the chosen role against the email in `users`. Login only takes an email and
password and resolves the role from that account, so the email is the identity and the
account record decides whether the user is a donor or a project creator. Project creators
can create campaigns and use the AI planner; donors get the giving-focused interface.
Passwords are hashed with Werkzeug.

## How PayPal is used
PayPal is used via the official `paypalrestsdk` SDK in sandbox mode. The `/donate` route
creates a PayPal payment for the amount the donor picks. After approval, the
`/payment-executed` route executes the payment and adds the captured amount to
`amount_raised`.

## How AI is used
The `/ai/builder` + `/ai/builder/generate` routes call Groq's OpenAI-compatible API
(`llama-3.3-70b-versatile`) to generate a storytelling paragraph, suggested budget, and
milestones for a user's idea. Results render through `ai_plan.html` in the same feed shell
as the rest of the site.

## Tools used
- **Groq** — LLM (OpenAI-compatible)
- **PayPal** — payments (sandbox)
- **Flask**, **psycopg**, **python-dotenv**, **openai**, **paypalrestsdk**, **gunicorn**

## How to run
```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env with DATABASE_URL, GROQ_API_KEY, PAYPAL_* keys
psql "$DATABASE_URL" -f schema.sql
python run.py
```

## Judge-facing checklist
- [x] Source code + instructions in this repo
- [x] Apache-2.0 MIT license visible at the top of the repo
- [x] Doc-ready demo: `python run.py` and visit `/ai/builder`
- [x] Tools list in README.md
