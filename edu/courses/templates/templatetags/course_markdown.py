from django import template
from django.utils.safestring import mark_safe
import markdown as md
import bleach

register = template.Library()
ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union({
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "br", "hr"
})
ALLOWED_ATTRIBUTES = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "target", "rel"],
}
@register.filter(name="markdown")
def markdown_filter(value):
    html = md.markdown(value or "", extensions=["extra", "nl2br"])
    clean = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)  # you can customize allowed tags/attrs later
    return mark_safe(clean)
