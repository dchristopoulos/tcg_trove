# MCP UI/UX Setup (VS Code)

This guide sets up MCP-driven UI/UX checks for TCG Trove.

## What You Get

- Repeatable browser flow checks
- Accessibility checks (WCAG issues)
- Lighthouse performance/best-practice reports
- Visual regression snapshots

## Prerequisites

- VS Code (latest)
- GitHub Copilot Chat extension
- Node.js 20+ (for many MCP servers)
- Python environment already configured for the app

## 1. Choose MCP Servers

Recommended stack:

1. Playwright MCP server: browser automation and journey checks
2. Accessibility MCP server (axe-based): a11y scanning
3. Lighthouse MCP server: performance and quality budgets

## 2. Add MCP Server Config in VS Code

Open Command Palette and configure MCP servers for your workspace.

Typical values you will need:

- Server command (for each MCP server)
- Working directory (this repository)
- Environment variables (base URL, auth/test flags)

Use base URL:

- `http://127.0.0.1:8000`

## 3. Define Critical Journeys

Start with these checks:

1. Register -> auto-login -> dashboard visible
2. Listings page -> apply filters -> results update
3. Listing detail renders required metadata
4. Admin dashboard loads alerts/performance sections

## 4. Add Quality Budgets

Set initial soft thresholds, then tighten:

- Accessibility: zero critical violations on critical pages
- Lighthouse performance: >= 75 initially
- CLS/LCP targets based on staging baseline

## 5. CI Integration Plan

1. Run MCP checks in report-only mode for 1 week
2. Track flaky checks and stabilize selectors
3. Switch critical checks to fail build on regressions

## Suggested First Command Set

- Run Playwright MCP flow tests on:
  - `/users/register`
  - `/dashboard`
  - `/listings`
  - `/admin`
- Run accessibility scan on:
  - `/login`
  - `/listings`
  - `/dashboard`
- Run Lighthouse on:
  - `/`
  - `/listings`

## Notes

- Keep test data deterministic (fixed accounts/listings for MCP flows).
- Prefer robust selectors (`data-*` hooks) for stable UI automation.
- Use screenshots for visual baseline after each major UI change.
