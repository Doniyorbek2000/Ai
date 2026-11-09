"""AI xatolari."""


class AIError(Exception):
    """AI javob bera olmadi (tarmoq, limit, noto'g'ri format)."""


class AIRefused(AIError):
    """Model xavfsizlik sababli javob bermadi."""
