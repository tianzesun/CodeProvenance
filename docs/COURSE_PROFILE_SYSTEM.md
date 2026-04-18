# Course Profile System

This document explains the new course-profile layer for the plagiarism engine.

## What Exists Now

The backend now includes a formal profile system for course-specific detection presets.

It ships with 10 built-in profiles:

- Balanced General CS
- Intro Programming Python
- Data Structures and Algorithms
- Object-Oriented Design
- Database Systems SQL
- Web Development
- Systems Programming
- AI and LLM Sensitive
- Competitive Programming
- Research Project Semantic

Each profile contains two views of the weights:

- `friendly_weights`
  - The human-facing 8-engine view for dashboard and faculty discussion.
  - Engines: AST, Winnowing, Token, Embedding, Graph, SQL, Web, Execution.
- `backend_weights`
  - The current backend fusion-engine view that can be applied immediately.
  - Engines: `ast`, `token`, `winnowing`, `graph`, `execution`, `embedding`, `ngram`, `codebert`.

## Why There Are Two Weight Views

The product direction is wider than the currently active fusion engine.

The friendly 8-engine view matches the roadmap:

- AST structure
- Winnowing fingerprint
- Token sequence
- Embedding semantic
- Graph flow
- SQL pattern
- HTML/CSS/JS web analysis
- Behavior execution

The backend view is what the current fusion engine can apply today without breaking
existing scoring code.

That means this profile layer is already usable now, while still leaving clean slots for:

- SQL-specific analysis
- web-page analysis
- richer behavior tracing
- future Optuna-generated profile exports

## API Endpoints

The settings API now supports:

- `GET /api/settings/profiles`
  - list available profiles and the active one
- `GET /api/settings/profiles/{profile_id}`
  - get full details for one profile
- `POST /api/settings/profiles/{profile_id}/apply`
  - apply that profile to the active engine configuration
- `POST /api/settings/profiles/{profile_id}/export`
  - export that profile as a standalone YAML file

## Current Storage

Profile definitions live in:

- [course_profiles.yaml](/home/tsun/CodeProvenance/src/backend/engines/course_profiles.yaml)

Profile loading and apply logic live in:

- [profile_manager.py](/home/tsun/CodeProvenance/src/backend/engines/scoring/profile_manager.py)

Applying a profile updates the active engine config and stores profile metadata under
the `course_profile` section of the engine configuration.

## Intended Next Step

When the labeled pairs are ready, the next extension should be:

1. run Optuna on a selected course dataset
2. write the tuned weights back as a new YAML profile
3. keep the best profile history for comparison

This profile layer was added specifically so that future tuning outputs can be stored
cleanly instead of overwriting the base configuration with no context.
