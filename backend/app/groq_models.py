"""Tell the shopkeeper's developer clearly when Groq rejects a configured model.

Groq retires models from time to time (llama-3.3-70b-versatile in 2026). Without a check the
only symptom is "AI ekhon kaj korche na" in the app, so at startup the backend asks Groq
about GROQ_MODEL and GROQ_STT_MODEL and logs an error that says what to change. The same
message is logged if a request later fails because of the model.
"""

import logging
import threading

import groq

from app.config import Settings

logger = logging.getLogger(__name__)

MODELS_URL = "https://console.groq.com/docs/models"
# Error codes Groq uses when the model itself is the problem.
_MODEL_ERROR_CODES = {"model_not_found", "model_decommissioned", "model_terms_required"}


def _error_details(exc: groq.APIError) -> tuple[str | None, str]:
    """(code, message) from Groq's error body: {"error": {"code": ..., "message": ...}}."""
    body = exc.body if isinstance(exc.body, dict) else {}
    error = body.get("error", body)
    if not isinstance(error, dict):
        return None, str(exc)
    return error.get("code"), str(error.get("message") or exc)


def model_rejection(exc: groq.APIError) -> str | None:
    """Groq's reason if `exc` means the model is unknown, retired or not allowed, else None."""
    code, message = _error_details(exc)
    if isinstance(exc, groq.NotFoundError) or code in _MODEL_ERROR_CODES:
        return message
    if isinstance(exc, groq.BadRequestError) and "decommissioned" in message.lower():
        return message
    return None


def rejected_model_message(setting: str, model: str, reason: str) -> str:
    return (
        f"Groq rejected {setting}={model!r}: {reason} "
        f"The model may have been retired or misspelled. Set {setting} in backend/.env to a "
        f"current model from {MODELS_URL} and restart the backend."
    )


def log_if_model_rejected(exc: groq.APIError, setting: str, model: str) -> bool:
    reason = model_rejection(exc)
    if reason is None:
        return False
    logger.error(rejected_model_message(setting, model, reason))
    return True


def check_configured_models(settings: Settings, client: groq.Groq | None = None) -> list[str]:
    """Ask Groq about each configured model. Returns the settings it rejected (and logs why).

    Does nothing without GROQ_API_KEY. Network problems are only a warning: the check must
    never stop the backend from starting.
    """
    if settings.groq_api_key is None:
        return []
    if client is None:
        client = groq.Groq(
            api_key=settings.groq_api_key.get_secret_value(), timeout=10.0, max_retries=0
        )
    models = {"GROQ_STT_MODEL": settings.groq_stt_model}
    # The chat model only matters when /parse uses Groq (not with LLM_PROVIDER=fake).
    if settings.llm_provider != "fake":
        models = {"GROQ_MODEL": settings.groq_model, **models}

    rejected = []
    for setting, model in models.items():
        try:
            client.models.retrieve(model)
        except groq.AuthenticationError:
            logger.error("Groq rejected GROQ_API_KEY. Check the key in backend/.env.")
            return rejected
        except groq.APIStatusError as exc:
            if log_if_model_rejected(exc, setting, model):
                rejected.append(setting)
            else:
                logger.warning("Could not check %s=%r with Groq: %s", setting, model, exc)
        except groq.APIError as exc:
            logger.warning("Could not reach Groq to check the configured models: %s", exc)
            return rejected
    return rejected


def start_model_check(settings: Settings) -> None:
    """Run the check in the background so a slow network doesn't delay startup."""
    if settings.groq_api_key is None:
        return
    threading.Thread(
        target=check_configured_models, args=(settings,), name="groq-model-check", daemon=True
    ).start()
