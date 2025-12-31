"""
OryggiAI Gateway Agent - Setup Script
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="oryggi-gateway-agent",
    version="1.0.0",
    author="OryggiAI",
    author_email="support@oryggi.ai",
    description="On-premises agent for connecting local databases to OryggiAI SaaS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/oryggi/gateway-agent",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: Other/Proprietary License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Database",
        "Topic :: System :: Networking",
    ],
    python_requires=">=3.9",
    install_requires=[
        "websockets>=12.0",
        "pyodbc>=5.0.0",
        "PyYAML>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "gateway-agent=gateway_agent.main:main",
        ],
        "gui_scripts": [
            "gateway-agent-gui=gateway_agent.gui:main_gui",
        ],
    },
)
