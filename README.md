# lifeOS

Personal Claude Code infrastructure. Manages global configuration, hooks, commands, rules, and skills as a single versioned system deployed to `~/.claude/`.

## Architecture

```
~/.claude/                          # This repo (Tokyofloripa/lifeOS)
├── CLAUDE.md                       # Global conventions (3-role system, GSD + Superpowers treaty)
├── settings.json                   # Hooks (8 entries across 7 events), model config, status line
├── commands/                       # Slash commands (/commit, /pr, /branch, /push, /fix-pr-feedback)
├── rules/                          # Prompt-level rules (skill routing, CI environment, treaty)
├── hooks/                          # Hook scripts (GSD status line, update checker)
├── agents/                         # GSD agent definitions (11 specialized agents)
├── shell/                          # Shell integration (aliases.zsh)
├── get-shit-done/                  # GSD framework (workflows, templates, references)
└── skills/                         # AI skills (each is a git submodule)
    ├── last60days/                 # Multi-source research engine (8+ sources, engagement-ranked)
    ├── ai-image/                   # AI image generation (GPT, Grok, Nanobanana)
    ├── temperature/                # Topic temperature measurement (5 dimensions, 0-100 score)
    └── gpt-researcher/             # GPT Researcher fork (multi-agent deep research)
```

## Skills as Submodules

Each skill is an independent git repo mounted as a submodule. This keeps skill development isolated from lifeOS config changes.

| Skill | Repo | What It Does |
|-------|------|-------------|
| last60days | [Tokyofloripa/last60days](https://github.com/Tokyofloripa/last60days) | Searches Reddit, X, HN, GitHub, Bluesky, YouTube, SO, web. Engagement-ranked. |
| ai-image | [Tokyofloripa/ai-image-skill](https://github.com/Tokyofloripa/ai-image-skill) | Generate images via GPT, Grok Imagine, or Nanobanana (Gemini). |
| temperature | [Tokyofloripa/trends](https://github.com/Tokyofloripa/trends) | Measure topic temperature across 5 dimensions with real API data. |
| gpt-researcher | [Tokyofloripa/gpt-researcher](https://github.com/Tokyofloripa/gpt-researcher) | Fork of assafelovic/gpt-researcher with multi-agent stderr capture. |

### Developing a Skill

Work happens inside the skill's own repo. lifeOS just tracks which commit to use.

```bash
# Enter the submodule
cd ~/.claude/skills/gpt-researcher

# Make changes, commit, push (to the skill's repo)
git checkout -b feat/my-feature
# ... edit files ...
git commit -m "feat: my improvement"
git push origin feat/my-feature

# After merging, update lifeOS to track the new commit
cd ~/.claude
git add skills/gpt-researcher
git commit -m "chore: update gpt-researcher submodule"
git push
```

### gpt-researcher: Fork Sync Workflow

The gpt-researcher skill is a fork of [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher). Custom skill files (SKILL.md, scripts/, references/) live at the repo root alongside upstream code.

**Syncing with upstream:**

```bash
cd ~/.claude/skills/gpt-researcher
git fetch upstream                    # Get latest upstream changes
git checkout main
git merge upstream/main --ff-only     # Fast-forward to latest release
git push origin main                  # Update fork on GitHub

# Then update lifeOS
cd ~/.claude
git add skills/gpt-researcher
git commit -m "chore: sync gpt-researcher to upstream vX.Y.Z"
git push
```

**Adding a remote (first time only):**

```bash
cd ~/.claude/skills/gpt-researcher
git remote add upstream https://github.com/assafelovic/gpt-researcher.git
```

## Setup

```bash
git clone --recursive https://github.com/Tokyofloripa/lifeOS.git ~/.claude
cd ~/.claude && bash install.sh
```

The `--recursive` flag initializes all skill submodules. Run `install.sh` to set up Superpowers, GitHub MCP, and shell integration.

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Global conventions, framework treaty, mode auto-detection |
| `settings.json` | Hook definitions, model selection, status line config |
| `MANIFEST.md` | Complete file inventory (USER / SYSTEM / GENERATED) |
| `CHANGELOG.md` | All changes with dates and context |
| `verify.sh` | 40+ integrity checks for the full configuration |
| `install.sh` | Bootstrap: submodules, plugins, MCP, shell integration |

## Dual-Model Adversarial Architecture

Claude (Anthropic) writes code locally. GitHub Copilot (OpenAI/GPT) reviews remotely. Two different AI families checking each other. Human is the final gate.

```
Claude writes code → push → Copilot auto-reviews → /fix-pr-feedback → push → human merges
```
