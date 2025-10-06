import importlib.util
import os
import json
import streamlit as st
from pathlib import Path

def load_plugins(plugins_dir="plugins"):
    """Discover and load all plugins from the plugins directory"""
    plugins = []
    print(f"🔍 Looking for plugins in: {plugins_dir}") # DEBUG

    for plugin_name in os.listdir(plugins_dir):
        plugin_path = Path(plugins_dir) / plugin_name
        plugin_json_path = plugin_path / "plugin.json"
        print(f"   Checking: {plugin_path}") # DEBUG

        if plugin_path.is_dir() and plugin_json_path.exists():
            try:
                with open(plugin_json_path, 'r', encoding='utf-8') as f:
                    plugin_info = json.load(f)
                    plugin_info['path'] = str(plugin_path)
                    plugins.append(plugin_info)
                    print(f"✅ Loaded plugin: {plugin_info['name']}") # DEBUG
            except Exception as e:
                st.error(f"❌ Failed to load plugin {plugin_name}: {e}")
                print(f"❌ Error loading {plugin_name}: {e}") # DEBUG
    print(f"Total plugins found: {len(plugins)}") # DEBUG
    return plugins

def get_plugin_pages(plugins):
    """Gets all pages from all plugins for navigation."""
    pages = []
    for plugin in plugins:
        for page in plugin.get("pages", []):
            # Add the plugin name to the page info for identification
            page_info = page.copy()
            page_info["plugin_name"] = plugin["name"]
            page_info["plugin_slug"] = plugin.get("slug", plugin["name"].lower().replace(' ', '_'))
            pages.append(page_info)
    return pages