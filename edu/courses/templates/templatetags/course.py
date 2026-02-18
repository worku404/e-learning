from django import template

register = template.Library()

@register.filter
def model_name(obj):
    try:
        return obj._meta.model_name
    except AttributeError:
        return None



@register.filter(name='duration_format')
def duration_format(seconds):
    """
    Converts seconds to a human-readable duration string.
    Example: 3665 -> '1h 1m 5s'
    """
    if not seconds:
        return "0s"
    
    seconds = int(seconds)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts: # Show seconds if it's the only unit or > 0
        parts.append(f"{seconds}s")
    
    return " ".join(parts)