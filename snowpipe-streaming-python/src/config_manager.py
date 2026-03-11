"""Configuration manager for Snowpipe Streaming.

Loads a Java-style .properties file and a JSON profile, then merges them
into a unified config dict used by the streaming manager.
"""

import json
import os


def load_properties(filepath: str) -> dict:
    """Load a Java-style .properties file into a dict."""
    props = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                props[key.strip()] = value.strip()
    return props


def load_profile(filepath: str) -> dict:
    """Load a JSON profile with Snowflake connection details."""
    with open(filepath) as f:
        profile = json.load(f)

    # Resolve private_key_file to the full PEM string if present
    key_file = profile.get("private_key_file")
    if key_file and not profile.get("private_key"):
        # Resolve relative to profile file location
        if not os.path.isabs(key_file):
            key_file = os.path.join(os.path.dirname(os.path.abspath(filepath)), key_file)
        with open(key_file) as kf:
            profile["private_key"] = kf.read()

    return profile


def build_config(config_file: str = "config.properties", profile_file: str = "profile.json") -> dict:
    """Build a merged configuration dict from properties + profile.

    Returns a dict with keys:
        - All properties from the .properties file
        - 'profile': the full profile dict (including resolved private_key)
        - 'sdk_properties': dict suitable for StreamingIngestClient constructor
    """
    props = load_properties(config_file)
    profile = load_profile(profile_file)

    sdk_properties = {
        "account": profile["account"],
        "user": profile["user"],
        "private_key": profile["private_key"],
        "role": profile["role"],
        "url": profile["url"],
    }

    return {
        **props,
        "profile": profile,
        "sdk_properties": sdk_properties,
    }
