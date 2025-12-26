# Midori AI: Where Creativity and Innovation Blossom

[![Midori AI photo](https://tea-cup.midori-ai.xyz/download/logo_color1.png)](https://io.midori-ai.xyz/)

Midori AI is a cutting-edge initiative dedicated to advancing the field of artificial intelligence through research, development, and community engagement. We focus on creating innovative AI solutions, exploring novel approaches, and empowering users to harness the power of AI.

---

## Mono Repo Structure Overview

This repository contains the following major projects and modules:

- **Pixel OS**  
  Collection of containerized OS environments for distributed AI workloads:
  - **PixelArch**: Arch-based OS leveraging Arch Linux with `yay` and `pacman` package managers, optimized for AI training and inference in containerized environments.
  - **PixelGen**: Gentoo-based OS that uses `yay` via a wrapper enabling yay commands on Gentoo for package management.

- **DiscordLLMBot**  
  Discord bot with LLM integration featuring RAG (Retrieval-Augmented Generation) capabilities. Built with interactions.py, ChromaDB for vector storage, LangChain for text processing, and OpenAI-compatible API support. Automatically upserts documents from data folder into vector database for context-aware responses with hotword activation.

- **Endless-Autofighter**  
  Web-based auto-battler game with strategic party management and elemental combat system. Built with Svelte/SvelteKit frontend and Python Quart async backend. Features turn-based combat, character progression, equipment management, plugin-based character/enemy systems, and optional LLM-powered interactions. Supports Docker deployment with CPU, NVIDIA GPU (CUDA), and AMD GPU configurations.

- **Website**  
  Midori AI's main website ([https://io.midori-ai.xyz/](https://io.midori-ai.xyz/)) built with Hugo static site generator. Serves as the central hub for project information, documentation, and community resources.

- **Obsidian-Notes**  
  Collaborative knowledge base using Obsidian for internal documentation, planning, and team coordination. Shared workspace for partners and contributors.

- **Experimentation**  
  Experimental AI projects and proof-of-concept implementations:
  - **Swarm-o-codex**: Persona-driven orchestration layer for large reasoning models (LRMs).
    - Multi-backend execution system with specialized agents (Task Master, Manager, Coder, Reviewer, Auditor, Storyteller)
    - Supports collaborative coding, auditing, storytelling, and automation tasks
    - Enables local LRM execution (`gpt-oss:20b`) and cloud API integration
    - Features tool-augmented reasoning via Model Context Protocol servers
  - **lrm-testing**: Tools and utilities for Large Reasoning Model chat interfaces and Q&A data pipeline development.
  - **rpg-note-taker**: Utilities for RPG campaign note-taking and management.

- **Python**  
  Python package monorepo for AI agent systems:
  - **agents-packages**: Collection of Python packages for building LRM agent systems including core agent implementations (OpenAI, HuggingFace, LangChain), context management, vector storage, media lifecycle management, mood engine, reranker, and logging utilities.

- **Codex-Template**  
  Standardized repository template defining `.codex/` directory structure, contributor documentation patterns, and development workflows used across all Midori AI projects.

---

For more info stop by our site! - [https://io.midori-ai.xyz/](https://io.midori-ai.xyz/)


## Get Involved:

* **Join our Discord community:** https://discord.gg/xdgCx3VyHU
* **Connect with us on Facebook:** https://www.facebook.com/TWLunagreen
* **Follow us on Twitter:** https://twitter.com/lunamidori5
* **Explore our Pinterest boards:** https://www.pinterest.com/luna_midori5/
* **Follow us on Twitch:** https://www.twitch.tv/luna_midori5
* **Subscribe to our YouTube channel:** https://www.youtube.com/channel/UCVQo4TxFJEoE5kccScY-xow
* **Support us on PayPal:** https://paypal.me/midoricookieclub?country.x=US&locale.x=en_US

## Star History

<a href="https://star-history.com/#Midori-AI-OSS/Midori-AI&Timeline">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Midori-AI-OSS/Midori-AI&type=Timeline&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Midori-AI-OSS/Midori-AI&type=Timeline" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Midori-AI-OSS/Midori-AI&type=Timeline" />
 </picture>
</a>

**Unleashing the Future of AI, Together.**
