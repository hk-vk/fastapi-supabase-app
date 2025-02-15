# Remove the init_db function since we're using Supabase
from .dependencies import supabase

__all__ = ['supabase']
