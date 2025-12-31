"""
OryggiAI Gateway Agent

Lightweight on-premises agent that connects your local SQL Server
database to the OryggiAI SaaS platform through a secure WebSocket tunnel.

This agent:
1. Initiates OUTBOUND connection to SaaS (bypasses firewall)
2. Receives SQL queries from SaaS through the connection
3. Executes queries on local SQL Server
4. Returns results through the same connection
"""

__version__ = "1.0.0"
__author__ = "OryggiAI"
