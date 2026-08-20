"""Platform extractors. Each module implements one platform as an
independent class (spec §3) so that adding X/Twitter later doesn't
require rewriting the downloader — it only means writing a new file
here and registering it in haul.core.registry.build_default_registry.
"""
