import os


class CatalogueUnavailable(RuntimeError):
    """Catalogue storage could not fulfill a read."""


def demo_fallback_enabled() -> bool:
    return os.getenv("ASTROCOMPLY_DEMO_FALLBACK", "").lower() == "true"


def get_mock_satellites():
    if not demo_fallback_enabled():
        raise CatalogueUnavailable("Satellite catalogue is unavailable.")
    from knowledge_layer.db_service import MOCK_SATELLITES
    return MOCK_SATELLITES
