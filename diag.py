#!/usr/bin/env python3
"""
diagnostic.py

A diagnostic script to collect environment details and attempt to load your bot’s cogs,
database settings, and necessary modules. Run this in the root of your bot project
(e.g., alongside bot.py, cogs/, utils/). The output will help identify missing imports,
configuration issues, or version mismatches that prevent cogs from loading.

Usage:
    python diagnostic.py
"""

import sys
import os
import traceback
import importlib
import pkgutil
import subprocess
from pathlib import Path

def print_separator(title: str):
    print("\n" + "=" * 60)
    print(f"{title}")
    print("=" * 60 + "\n")

def python_version():
    print_separator("Python Version")
    print(sys.version)

def env_variables():
    print_separator("Relevant Environment Variables")
    keys = ["PYTHONPATH", "MONGO_URI", "MONGO_DB_NAME", "DISCORD_TOKEN", "BOT_PREFIX"]
    for k in keys:
        print(f"{k} = {os.getenv(k)}")

def installed_packages():
    print_separator("Installed Packages and Versions")
    try:
        # For Python ≥3.8
        from importlib.metadata import distributions
        for dist in distributions():
            name = dist.metadata["Name"]
            version = dist.version
            if name.lower() in ("discord", "discord.py", "motor", "pymongo", "dnspython"):
                print(f"{name}: {version}")
    except ImportError:
        # Fallback to pkg_resources
        try:
            import pkg_resources
            for dist in pkg_resources.working_set:
                if dist.project_name.lower() in ("discord", "discord.py", "motor", "pymongo", "dnspython"):
                    print(f"{dist.project_name}: {dist.version}")
        except ImportError:
            print("Could not determine package versions (no importlib.metadata or pkg_resources).")

def list_cogs():
    print_separator("Listing Cogs Directory (cogs/)")
    cogs_path = Path("cogs")
    if not cogs_path.exists():
        print("No 'cogs/' directory found.")
        return

    py_files = sorted([f.name for f in cogs_path.glob("*.py")])
    if not py_files:
        print("'cogs/' directory exists, but no .py files found.")
    else:
        for f in py_files:
            print(f"- {f}")

def try_import_cog(module_name: str):
    try:
        importlib.import_module(module_name)
        print(f"[OK]   Imported '{module_name}'")
    except Exception as e:
        print(f"[FAIL] Importing '{module_name}' raised {type(e).__name__}:")
        tb = traceback.format_exc().strip().splitlines()
        for line in tb:
            print("    " + line)

def test_cog_imports():
    print_separator("Attempting to Import Each Cog")
    cogs_dir = Path("cogs")
    if not cogs_dir.exists():
        print("No 'cogs/' directory to import from.")
        return

    for py_file in sorted(cogs_dir.glob("*.py")):
        module_stem = py_file.stem  # e.g., 'core', 'tournament'
        full_module = f"cogs.{module_stem}"
        try_import_cog(full_module)

def check_utils_db():
    print_separator("Checking utils/db.py and 'db' Availability")
    try:
        from utils.db import db
        print("[OK]   'db' was successfully imported from utils.db")
    except Exception as e:
        print(f"[FAIL] Importing 'db' from utils.db raised {type(e).__name__}:")
        tb = traceback.format_exc().strip().splitlines()
        for line in tb:
            print("    " + line)

def list_utils_files():
    print_separator("Listing utils/ Directory")
    utils_path = Path("utils")
    if not utils_path.exists():
        print("No 'utils/' directory found.")
        return

    py_files = sorted([f.name for f in utils_path.glob("*.py")])
    if not py_files:
        print("'utils/' directory exists, but no .py files found.")
    else:
        for f in py_files:
            print(f"- {f}")

def show_database_uri():
    print_separator("MongoDB Connection Test")
    mongo_uri = os.getenv("MONGO_URI", "Not set")
    print(f"MONGO_URI = {mongo_uri}")
    if "mongodb://" in mongo_uri or "mongodb+srv://" in mongo_uri:
        try:
            import motor.motor_asyncio
            client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
            # Ping the server (async cannot be called here, but we can check sync attribute)
            client.admin.command("ping")
            print("[OK]   Successfully pinged MongoDB")
        except Exception as e:
            print(f"[FAIL] Could not connect to MongoDB: {type(e).__name__}: {e}")
    else:
        print("No valid MongoDB URI provided, skipping ping.")

def check_discord_intents():
    print_separator("Discord.py and Bot Intent Check")
    try:
        import discord
        version = discord.__version__
        print(f"discord.py version: {version}")
        # Check if Intents are accessible
        intents = discord.Intents.default()
        print("discord.Intents.default() accessible")
    except Exception as e:
        print(f"[FAIL] Discord.py import or Intents creation failed: {type(e).__name__}: {e}")

def main():
    python_version()
    env_variables()
    installed_packages()
    list_utils_files()
    check_utils_db()
    list_cogs()
    test_cog_imports()
    show_database_uri()
    check_discord_intents()
    print("\nDiagnostics complete. Please review the above output for errors or missing components.\n")

if __name__ == "__main__":
    main()
