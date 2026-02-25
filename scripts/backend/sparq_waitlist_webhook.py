"""Sparq Coach Waitlist — Wix webhook receiver.

STATUS: PLACEHOLDER — not yet implemented.
See docs/future_plans/PLATFORM_STRATEGY.md §13.5 for full spec.

Deploy on a $5 VPS (e.g. DigitalOcean, Hetzner).
Run: flask --app sparq_waitlist_webhook run --host 0.0.0.0 --port 5000

Wix setup:
  1. Create waitlist form (name, email, institution, instrument model)
  2. Wix Automations → "When form submitted" → "Send a webhook"
  3. Point webhook at: https://your-vps-ip:5000/sparq/waitlist

Nutshell API docs: https://developers.nutshell.com
"""

# TODO: pip install flask requests

# from flask import Flask, request, jsonify
# import requests

# app = Flask(__name__)

# NUTSHELL_USER  = "your@email.com"       # TODO: fill in
# NUTSHELL_TOKEN = "your_api_token"        # TODO: fill in from Nutshell → Profile → API keys
# NUTSHELL_API   = "https://app.nutshell.com/api/v1/json"

# WEBHOOK_SECRET = "your_wix_webhook_secret"  # TODO: set in Wix + here for request validation


# @app.route("/sparq/waitlist", methods=["POST"])
# def waitlist():
#     data = request.get_json(force=True)
#
#     # TODO: validate Wix webhook signature if Wix provides one
#
#     # Extract fields from Wix form submission payload
#     # TODO: adjust field names to match your actual Wix form field IDs
#     name        = data.get("name", "").strip()
#     email       = data.get("email", "").strip()
#     institution = data.get("institution", "").strip()
#     instrument  = data.get("instrument_model", "").strip()
#
#     if not email:
#         return jsonify({"error": "missing email"}), 400
#
#     # Create contact in Nutshell
#     payload = {
#         "method": "newContact",
#         "params": {
#             "contact": {
#                 "name": [{"givenName": name}],
#                 "email": [{"email": email}],
#                 "tags": ["sparq-waitlist"],
#                 "description": (
#                     f"Institution: {institution}\n"
#                     f"Instrument: {instrument}\n"
#                     f"Source: Sparq Coach waitlist (in-app button)"
#                 ),
#             }
#         },
#         "id": 1,
#     }
#     resp = requests.post(
#         NUTSHELL_API,
#         auth=(NUTSHELL_USER, NUTSHELL_TOKEN),
#         json=payload,
#         timeout=10,
#     )
#
#     # TODO: optionally create a Lead in Nutshell if instrument model is known
#     # TODO: log submission locally as backup
#
#     return jsonify({"ok": True}), 200


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000)
