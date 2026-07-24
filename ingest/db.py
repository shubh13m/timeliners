"""Supabase client factory (service role)."""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from .config import load_settings


@lru_cache(maxsize=1)
def get_client() -> Client:
    s = load_settings()
    return create_client(s.supabase_url, s.supabase_service_key)
