from django.conf import settings  # Django setting access for AUTH_USER_MODEL.
from django.db import models  # Django ORM base classes and field types.
from django.utils.text import slugify  # Utility to normalize tag names into slugs.


# Tag model to group notes by a single optional label.
class Tag(models.Model):
    # Associate tags to the owning user (global per user notes).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Link to the configured user model.
        on_delete=models.CASCADE,  # Delete tags when the user is deleted.
        related_name="note_tags",  # Reverse accessor for a user's tags.
    )
    # Store the human-readable tag label.
    name = models.CharField(max_length=60)
    # Store the URL-friendly slug used for filtering.
    slug = models.SlugField(max_length=70)
    # Track when the tag was created.
    created_at = models.DateTimeField(auto_now_add=True)
    # Track when the tag was last updated.
    updated_at = models.DateTimeField(auto_now=True)

    # Django model metadata configuration.
    class Meta:
        # Prevent duplicate tags per user by slug.
        unique_together = ("user", "slug")
        # Keep tags ordered alphabetically in queries.
        ordering = ["name"]

    # Override save to ensure slug is always populated.
    def save(self, *args, **kwargs):
        # Auto-generate slug if missing to keep filters consistent.
        # Only generate a slug when missing to preserve edits.
        if not self.slug:
            # Limit slug length to field max length.
            self.slug = slugify(self.name)[:70]
        # Continue with the normal save flow.
        # Call the base save implementation.
        return super().save(*args, **kwargs)

    # Return a readable string representation.
    def __str__(self):
        # Return the human-readable tag label.
        # Provide the tag name for display.
        return self.name


# Note model storing title, HTML content, and optional tag.
class Note(models.Model):
    # Associate each note with its owning user.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Link to the configured user model.
        on_delete=models.CASCADE,  # Delete notes when the user is deleted.
        related_name="notes",  # Reverse accessor for a user's notes.
    )
    # Store the note title requested at save time.
    title = models.CharField(max_length=200)
    # Store the note content as HTML (Quill output).
    content_html = models.TextField(blank=True, default="")
    # Store the optional single tag relation for filtering.
    tag = models.ForeignKey(
        Tag,  # Link to the Tag model for optional categorization.
        on_delete=models.SET_NULL,  # Keep notes if a tag is deleted.
        null=True,  # Allow notes to have no tag.
        blank=True,  # Allow empty tag in forms/validation.
        related_name="notes",  # Reverse accessor for tag -> notes.
    )
    # Track when the note was created.
    created_at = models.DateTimeField(auto_now_add=True)
    # Track when the note was last updated.
    updated_at = models.DateTimeField(auto_now=True)

    # Django model metadata configuration.
    class Meta:
        # Sort notes newest first for the sidebar list.
        ordering = ["-created_at"]

    # Return a readable string representation.
    def __str__(self):
        # Return the note title for admin/debugging.
        # Provide the note title for display.
        return self.title
