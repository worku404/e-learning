from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.conf import settings
import requests
import markdown

@require_POST
@login_required
def llm_generate(request):
    prompt = (request.POST.get("prompt") or "").strip()
    
    if not prompt:
        return JsonResponse({"error": "Prompt is required."}, status=400)
    
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"
    history = request.session.get("llm_history", [])
    
    max_turns = 3
    history = history[-max_turns:]
    
    contents = []
    for item in history:
        if item.get("prompt"):
            contents.append({"role": "user", "parts": [
                {"text": item["prompt"]}
            ]})
        if item.get("response"):
            contents.append({
                "role": "model", 
                "parts": [
                {"text": item["response"]}
            ]})
    contents.append({
        "role": "user",
        "parts": [
            {"text": prompt}
        ]
    })
    data = {"contents": contents}
    
    # Call Gemini api
    api_keys = [
        settings.API1_KEY,
        settings.API2_KEY,
        settings.API3_KEY,
        settings.API4_KEY,
    ]
    api_keys = [key.strip() for key in api_keys if isinstance(key, str) and key.strip()]

    if not api_keys:
        return JsonResponse(
            {
                "error": "No Gemini API keys are configured. Add API1_KEY..API4_KEY in your .env file.",
            },
            status=500,
        )
    
    last_error = None
    for key_index, api_key in enumerate(api_keys, start=1):
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=20)
            if response.status_code == 200:
                payload = response.json()
                generated = payload["candidates"][0]["content"]["parts"][0]["text"]

                # Save new turn to session
                history.append({"prompt": prompt, "response": generated})
                request.session["llm_history"] = history
                request.session.modified = True
                return JsonResponse({"generated": markdown.markdown(generated)})
            error_payload = {}
            try:
                error_payload = response.json()
            except ValueError:
                error_payload = {"message": response.text[:300]}

            api_error = error_payload.get("error", {}) if isinstance(error_payload, dict) else {}
            if isinstance(api_error, dict):
                message = api_error.get("message") or error_payload.get("message")
            else:
                message = error_payload.get("message") if isinstance(error_payload, dict) else None

            last_error = {
                "key_index": key_index,
                "status": response.status_code,
                "message": message,
            }
        except requests.RequestException as exc:
            last_error = {"key_index": key_index, "error": str(exc)}
            continue

    error_message = "All API keys failed."
    if last_error and last_error.get("status") == 429:
        error_message = "All API keys are over quota right now."
    elif last_error and last_error.get("status") in (401, 403):
        error_message = "All API keys were rejected (invalid key, API disabled, or key restriction mismatch)."

    return JsonResponse(
        {
            "error": error_message,
            "details": last_error,
        },
        status=500,
    )

@login_required
def llm_page(request):
    return render(request, "assistant/page.html")
