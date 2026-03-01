"""Sparq Coach Beta — HTTP client service.

Handles two cloud features:
  1. Auto bug submission  → POST /sparq/bug
  2. Claude Haiku chat    → POST /sparq/coach/beta/chat

Both features require a registered Sparq account (config/sparq_account.json with a
valid api_key). If the account file is missing or has no key, is_available() returns
False and all methods return graceful failure tuples without making any network calls.

Backend: Cloudflare Worker at BASE_URL (see SPARQ_COACH_BETA_FRS.md).
"""

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_BASE_URL = "https://sparq-worker.jolly-pond-da61.workers.dev"  # TODO: move to sparq.affiniteinstruments.com once domain is routed
_ACCOUNT_CONFIG = Path("config/sparq_account.json")
_BUG_HISTORY = Path("data/spark/bug_history.json")

_TIMEOUT_BUG = 5      # seconds
_TIMEOUT_CHAT = 10    # seconds
_TIMEOUT_QUOTA = 3    # seconds

_MAX_SCREENSHOT_BYTES = 1_000_000   # 1 MB before base64 encoding

# Cached account data — loaded once per process, invalidated on None.
_account_cache: dict | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_account() -> dict | None:
    """Load and cache sparq_account.json. Returns None if file absent or invalid."""
    global _account_cache
    if _account_cache is not None:
        return _account_cache
    try:
        data = json.loads(_ACCOUNT_CONFIG.read_text(encoding="utf-8"))
        if data.get("api_key") and data.get("device_serial"):
            _account_cache = data
            return _account_cache
    except Exception:
        pass
    return None


def _auth_headers(account: dict) -> dict:
    return {
        "Authorization": f"Bearer {account['api_key']}",
        "X-Device-Serial": account["device_serial"],
        "Content-Type": "application/json",
    }


def _system_info() -> dict:
    import platform, sys
    return {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "machine": platform.machine(),
    }


def _app_version() -> str:
    try:
        from version import __version__
        return __version__
    except Exception:
        return "unknown"


def _append_bug_history(entry: dict) -> None:
    """Append one entry to the local bug history JSON file."""
    try:
        _BUG_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        history: list = []
        if _BUG_HISTORY.exists():
            try:
                history = json.loads(_BUG_HISTORY.read_text(encoding="utf-8"))
            except Exception:
                history = []
        history.append(entry)
        _BUG_HISTORY.write_text(json.dumps(history, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not write bug history: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SparqCoachService:
    """HTTP client for Sparq Coach Beta.

    Instantiate cheaply — no network calls on __init__.
    All methods are safe to call even when no account is registered.
    """

    def is_available(self) -> bool:
        """True if a registered Sparq account is present with a valid api_key."""
        return _load_account() is not None

    # ------------------------------------------------------------------
    # Bug reporting
    # ------------------------------------------------------------------

    def submit_bug_report(
        self,
        description: str,
        user_name: str = "",
        screenshot_bytes: bytes | None = None,
        additional_images: list[str] | None = None,
        report_type: str = "bug",
    ) -> tuple[bool, str]:
        """Auto-submit a bug report or support request to the Sparq backend.

        Args:
            report_type: 'bug' (default) or 'support_request' for unanswered Sparq questions.

        Returns:
            (True, ticket_id)        on success.
            (False, error_message)   on failure — caller should fall back to draft mode.
        """
        account = _load_account()
        if account is None:
            return False, "no_account"

        # Encode screenshot — skip if too large
        screenshot_b64 = ""
        if screenshot_bytes:
            if len(screenshot_bytes) <= _MAX_SCREENSHOT_BYTES:
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("ascii")
            else:
                logger.info("Screenshot too large for upload — omitted from report")

        # Encode additional images
        extra_b64: list[str] = []
        for img_path in (additional_images or []):
            try:
                img_data = Path(img_path).read_bytes()
                if len(img_data) <= _MAX_SCREENSHOT_BYTES:
                    extra_b64.append(base64.b64encode(img_data).decode("ascii"))
            except Exception:
                pass

        payload = {
            "device_serial": account["device_serial"],
            "instrument_model": account.get("instrument_model", ""),
            "app_version": _app_version(),
            "user_name": user_name,
            "description": description,
            "report_type": report_type,
            "system_info": _system_info(),
            "screenshot_b64": screenshot_b64,
            "additional_images_b64": extra_b64,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            resp = requests.post(
                f"{_BASE_URL}/sparq/bug",
                headers=_auth_headers(account),
                json=payload,
                timeout=_TIMEOUT_BUG,
            )
        except requests.exceptions.ConnectionError:
            return False, "offline"
        except requests.exceptions.Timeout:
            return False, "timeout"
        except Exception as e:
            logger.warning(f"Bug submit network error: {e}")
            return False, str(e)

        if resp.status_code == 200:
            data = resp.json()
            ticket_id = data.get("ticket_id", "unknown")
            _append_bug_history({
                "ticket_id": ticket_id,
                "submitted_at": payload["submitted_at"],
                "description": description[:200],
                "auto_submitted": True,
                "screenshot_included": bool(screenshot_b64),
                "status": "received",
            })
            return True, ticket_id

        if resp.status_code == 429:
            _append_bug_history({
                "ticket_id": None,
                "submitted_at": payload["submitted_at"],
                "description": description[:200],
                "auto_submitted": False,
                "screenshot_included": False,
                "status": "rate_limited",
            })
            return False, "report_limit_reached"

        if resp.status_code == 401:
            return False, "auth_failed"

        return False, f"server_error_{resp.status_code}"

    # ------------------------------------------------------------------
    # Coach Beta chat
    # ------------------------------------------------------------------

    def ask_coach(
        self,
        question: str,
        local_answer: str = "",
        context: dict | None = None,
    ) -> tuple[bool, str, int]:
        """Send a question to Sparq Coach Beta (Claude Haiku via Worker).

        Returns:
            (True, answer_text, remaining_quota)   on success.
            (False, error_message, 0)              on failure.
        """
        account = _load_account()
        if account is None:
            return False, "no_account", 0

        payload = {
            "device_serial": account["device_serial"],
            "instrument_model": account.get("instrument_model", ""),
            "app_version": _app_version(),
            "question": question,
            "local_answer": local_answer,
            "context": context or {},
        }

        try:
            resp = requests.post(
                f"{_BASE_URL}/sparq/coach/beta/chat",
                headers=_auth_headers(account),
                json=payload,
                timeout=_TIMEOUT_CHAT,
            )
        except requests.exceptions.ConnectionError:
            return False, "offline", 0
        except requests.exceptions.Timeout:
            return False, "Sparq Coach took too long — please try again.", 0
        except Exception as e:
            logger.warning(f"Coach chat network error: {e}")
            return False, str(e), 0

        if resp.status_code == 200:
            data = resp.json()
            return True, data.get("answer", ""), data.get("remaining", 0)

        if resp.status_code == 429:
            return False, "daily_quota_exhausted", 0

        if resp.status_code == 503:
            return False, "Sparq Coach is temporarily busy — try again in a moment.", 0

        if resp.status_code == 401:
            return False, "auth_failed", 0

        return False, f"server_error_{resp.status_code}", 0

    # ------------------------------------------------------------------
    # Quota
    # ------------------------------------------------------------------

    def get_quota(self) -> dict:
        """Fetch today's remaining quota for this device.

        Returns a dict with keys: chat_remaining, bug_remaining, resets_at.
        Returns safe defaults on any failure — never raises.
        """
        _defaults = {"chat_remaining": 20, "bug_remaining": 10, "resets_at": "00:00 UTC"}

        account = _load_account()
        if account is None:
            return _defaults

        try:
            resp = requests.get(
                f"{_BASE_URL}/sparq/coach/beta/quota",
                headers=_auth_headers(account),
                timeout=_TIMEOUT_QUOTA,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.debug(f"Quota fetch failed (non-critical): {e}")

        return _defaults
