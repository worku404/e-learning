import json  # Standard library JSON utilities for request parsing.

from django.contrib.auth.mixins import LoginRequiredMixin  # Require authenticated users.
from django.http import JsonResponse  # Return JSON responses for the notes API.
from django.shortcuts import get_object_or_404  # Fetch objects or return 404.
from django.utils.text import slugify  # Normalize tag names for filtering.
from django.views import View  # Base class for simple class-based views.

from .models import Note, Tag  # Import note and tag models for CRUD operations.


# Serialize a Note instance into a JSON-safe dict.
def _serialize_note(note):
    # Build the tag payload if the note has a tag.
    tag_payload = None
    # Only include tag data when the relation exists.
    if note.tag:
        # Shape the tag payload for list/detail responses.
        tag_payload = {
            "id": note.tag.id,  # Tag primary key for client use.
            "name": note.tag.name,  # Tag display name for the sidebar.
            "slug": note.tag.slug,  # Tag slug used for filtering.
        }
    # Return the serialized note payload.
    return {
        "id": note.id,  # Note primary key for future updates.
        "title": note.title,  # Note title shown in the list.
        "content_html": note.content_html,  # Note HTML content for the editor.
        "tag": tag_payload,  # Optional tag object for UI badges.
        "created_at": note.created_at.isoformat(),  # Timestamp for ordering.
        "updated_at": note.updated_at.isoformat(),  # Timestamp for autosave display.
    }


# Parse JSON or form-encoded payloads into a dict.
def _parse_payload(request):
    # Prefer JSON when the request advertises it.
    if request.content_type and request.content_type.startswith("application/json"):
        # Attempt to decode JSON payload.
        try:
            # Decode bytes to text and parse JSON into a dict.
            return json.loads(request.body.decode("utf-8") or "{}")
        # Handle malformed JSON payloads.
        except (ValueError, UnicodeDecodeError):
            # Signal invalid payload with None so the caller can respond.
            return None
    # Fallback to standard form payloads (POST).
    return request.POST.dict()


# Resolve a tag string into a Tag instance or None.
def _normalize_tag(user, tag_text):
    # Normalize and trim user input.
    cleaned = (tag_text or "").strip()
    # Return None when no tag was provided.
    if not cleaned:
        return None
    # Build a safe slug for filtering.
    slug = slugify(cleaned)[:70]
    # Ensure we still have a slug (fallback to "tag").
    if not slug:
        slug = "tag"
    # Create or fetch the tag for this user.
    tag, created = Tag.objects.get_or_create(
        user=user,  # Scope tags to the current user.
        slug=slug,  # Use slug for uniqueness per user.
        defaults={"name": cleaned},  # Store the human label on first creation.
    )
    # Update name if it changed for an existing tag.
    if not created and tag.name != cleaned:
        # Update the stored name for display purposes.
        tag.name = cleaned
        # Persist the updated name and timestamp.
        tag.save(update_fields=["name", "updated_at"])
    # Return the resolved tag instance.
    return tag


# List and create notes for the current user.
class NoteListCreateView(LoginRequiredMixin, View):
    # Handle GET requests to list notes, optionally filtered by tag.
    def get(self, request):
        # Read the optional tag filter from query params.
        tag_slug = (request.GET.get("tag") or "").strip()
        # Base queryset: only the current user's notes.
        notes_qs = (
            Note.objects.filter(user=request.user)
            .select_related("tag")
            .order_by("-created_at")
        )
        # Apply tag filter when provided.
        if tag_slug:
            notes_qs = notes_qs.filter(tag__slug=tag_slug)
        # Serialize notes into a list for JSON output.
        items = [_serialize_note(note) for note in notes_qs]
        # Return the list payload.
        return JsonResponse({"notes": items})

    # Handle POST requests to create a new note.
    def post(self, request):
        # Parse the incoming payload.
        payload = _parse_payload(request)
        # Reject invalid JSON bodies.
        if payload is None:
            return JsonResponse({"error": "Invalid JSON payload."}, status=400)
        # Extract and normalize the title.
        title = (payload.get("title") or "").strip()
        # Extract the HTML content (default to empty).
        content_html = payload.get("content_html") or ""
        # Extract tag text for normalization.
        tag_text = payload.get("tag") or ""
        # Require a title for new notes.
        if not title:
            return JsonResponse({"error": "Title is required."}, status=400)
        # Resolve tag relation if provided.
        tag_obj = _normalize_tag(request.user, tag_text)
        # Create the new note record.
        note = Note.objects.create(
            user=request.user,  # Associate note to the current user.
            title=title,  # Store the required title.
            content_html=content_html,  # Store the HTML body.
            tag=tag_obj,  # Store the optional tag relation.
        )
        # Return the created note payload.
        return JsonResponse({"note": _serialize_note(note)}, status=201)


# Retrieve, update, and delete a specific note.
class NoteDetailView(LoginRequiredMixin, View):
    # Handle GET requests to fetch a single note.
    def get(self, request, note_id):
        # Load the note or return 404 when missing.
        note = get_object_or_404(Note, id=note_id, user=request.user)
        # Return the note payload.
        return JsonResponse({"note": _serialize_note(note)})

    # Handle POST requests to update a note (autosave).
    def post(self, request, note_id):
        # Load the note or return 404 when missing.
        note = get_object_or_404(Note, id=note_id, user=request.user)
        # Parse the incoming payload.
        payload = _parse_payload(request)
        # Reject invalid JSON bodies.
        if payload is None:
            return JsonResponse({"error": "Invalid JSON payload."}, status=400)
        # Extract optional title (autosave may omit).
        title = payload.get("title")
        # Extract optional HTML content.
        content_html = payload.get("content_html")
        # Extract optional tag text.
        tag_text = payload.get("tag")
        # Update title only when provided.
        if title is not None:
            # Normalize title spacing.
            normalized_title = str(title).strip()
            # Guard against empty titles on update.
            if not normalized_title:
                return JsonResponse({"error": "Title cannot be empty."}, status=400)
            # Apply the updated title.
            note.title = normalized_title
        # Update content only when provided.
        if content_html is not None:
            # Apply the updated HTML body.
            note.content_html = str(content_html)
        # Update tag only when provided (empty string clears).
        if tag_text is not None:
            # Resolve the tag relation (or None if blank).
            note.tag = _normalize_tag(request.user, tag_text)
        # Persist changes to the database.
        note.save()
        # Return the updated note payload.
        return JsonResponse({"note": _serialize_note(note)})

    # Handle DELETE requests to remove a note.
    def delete(self, request, note_id):
        # Load the note or return 404 when missing.
        note = get_object_or_404(Note, id=note_id, user=request.user)
        # Delete the note record.
        note.delete()
        # Return a simple confirmation payload.
        return JsonResponse({"status": "deleted"})
