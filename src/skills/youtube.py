from src.skills.rutube import search_rutube


def search_youtube(*args, **kwargs):
    """Совместимость со старыми командами: поиск открывается на Rutube."""
    return search_rutube(*args, **kwargs)
