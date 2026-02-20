from .forms import LLMForm
from .markdown_utils import render_llm_markdown


def llm_widget(request):
    if not request.user.is_authenticated:
        return {"llm_form": None, "llm_history": []}

    history = request.session.get("llm_history", [])
    if not isinstance(history, list):
        history = []

    history_ui = []
    for entry in history:
        if not isinstance(entry, dict):
            continue

        prompt = (entry.get("prompt") or "").strip()
        response = (entry.get("response") or "").strip()

        if not prompt and not response:
            continue

        history_ui.append(
            {
                "prompt": prompt,
                "response": render_llm_markdown(response) if response else "",
            }
        )

    return {
        "llm_form": LLMForm(),
        "llm_history": history_ui,
    }
