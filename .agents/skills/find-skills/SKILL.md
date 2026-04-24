---
name: find-skills
description: Helps discover and install agent skills when the user asks "find a skill for X", "is there a skill that can...", or wants to extend agent capabilities. Use when looking for functionality that might exist as an installable skill from the open agent skills ecosystem.
---

# Find Skills

Discover and install skills from the open agent skills ecosystem at skills.sh.

## When to Use

- User asks "how do I do X" where X might be a common task with an existing skill
- User says "find a skill for X" or "is there a skill for X"
- User wants to extend agent capabilities for a specific domain
- No existing project skill covers the need

## Key Commands

```bash
npx skills find [query]                      # search interactively or by keyword
npx skills add <owner/repo@skill>            # install to current project
npx skills add <owner/repo@skill> -g -y      # install globally, skip confirmation
npx skills check                             # check for skill updates
npx skills update                            # update all installed skills
npx skills init my-skill-name               # create a new skill from scratch
```

## How to Find Skills

### Step 1: Check the leaderboard first
Browse https://skills.sh/ for top-ranked skills by install count before running a search.

### Step 2: Search by keyword
```bash
npx skills find [query]
```
Examples:
- `npx skills find python scraping`
- `npx skills find playwright testing`
- `npx skills find data pipeline`

### Step 3: Verify before recommending
Do NOT recommend a skill based solely on search results. Always verify:
- **Install count** — prefer 1K+. Be cautious under 100.
- **Source reputation** — official sources (`vercel-labs`, `anthropics`, `microsoft`) are more trustworthy.
- **GitHub stars** — check source repo. Under 100 stars = treat with skepticism.

### Step 4: Present options to the user

```
I found a skill that might help! The "playwright-best-practices" skill provides
Playwright automation patterns from Vercel Engineering.
(12K installs)

To install it:
npx skills add vercel-labs/agent-skills@playwright-best-practices

Learn more: https://skills.sh/vercel-labs/agent-skills/playwright-best-practices
```

### Step 5: Offer to install

```bash
npx skills add <owner/repo@skill> -g -y
```

## When No Skills Are Found

1. Acknowledge that no existing skill was found.
2. Offer to help with the task directly.
3. Suggest creating a custom skill:
```bash
npx skills init my-skill-name
```

## Common Categories for This Project

| Category | Example Queries |
|----------|----------------|
| Scraping | python scraping, playwright, selenium, html parsing |
| Data | pandas, data pipeline, csv, json transformation |
| Testing | pytest, mocking, integration testing |
| DevOps | docker, ci-cd, github actions |
| Code Quality | python review, pep8, type checking |
