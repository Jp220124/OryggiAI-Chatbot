"""
Allow running as: python -m gateway_agent
"""

try:
    from .main import main
except ImportError:
    try:
        # Frozen exe (PyInstaller)
        from gateway_agent.main import main
    except ImportError:
        # Standalone script
        from main import main

if __name__ == "__main__":
    main()
