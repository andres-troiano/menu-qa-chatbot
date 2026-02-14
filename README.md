# Menu Q&A Chatbot

A hybrid LLM + deterministic architecture chatbot that answers questions about restaurant menu items, pricing, nutrition, categories, and discounts.

## Colab demo

Open the notebook in Colab:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/andres-troiano/menu-qa-chatbot/blob/main/notebooks/demo.ipynb)

## Overview

This chatbot uses a hybrid approach where:
- **LLM handles routing**: Extracts intent and entities (item names, portions, discounts)
- **Deterministic tools handle facts**: All pricing, nutrition, and discount logic is computed from structured data

This ensures factual correctness and prevents hallucinations while leveraging LLM capabilities for natural language understanding.

## Supported Queries

The chatbot supports the following question types:

### 1. Price Lookup

Ask about item prices, optionally specifying portion size:

- "What is the price of a small NUTTY BOWL?"
- "How much is the ACAI ELIXIR?"
- "How much is the GREEN BOWL Large?"

**Behavior:**
- Correctly resolves item names
- Resolves portion when specified (Small, Medium, Large, etc.)
- If portion not specified but multiple exist → chooses default or asks for clarification
- Never hallucinates prices, all prices come from structured data

### 2. Nutrition Lookup (Calories)

Query calorie information for menu items:

- "How many calories does the GO GREEN smoothie have?"
- "Calories for Dragon Smoothie"

**Behavior:**
- Prefers structured calorie fields from the dataset
- Falls back to extracting from description if needed
- Returns explicit "Calories not available" if none found

### 3. Category Listing

List all items in a specific category:

- "Which salads do you have?"
- "What bowls are available?"
- "Show me smoothies"

**Behavior:**
- Returns all items whose category matches
- Excludes modifier groups
- Preserves canonical item names

### 4. Discount Listing

Get information about available discounts:

- "What discounts are available?"
- "Which discounts include coupons?"

**Behavior:**
- Lists discount definitions from the dataset
- If coupon information not present → states that explicitly

### 5. Discount Trigger Query

Find which items trigger specific discounts:

- "What items trigger BOGO Any Smoothie discount?"

**Behavior:**
- Attempts to join discount → item groups → items
- If dataset does not allow full mapping → explains limitation clearly

### 6. Cross-Channel Price Comparison

Compare prices across different channels:

- "Is the price for Smoothie - ACAI ELIXIR the same in all channels?"

**Behavior:**
- If dataset contains channel-specific pricing → compares across channels
- If dataset does not include channel dimension → explains limitation

## Non-Goals

The following are explicitly **out of scope**:

- Order placement
- Modifier customization
- Real-time discount eligibility evaluation
- Tax calculation
- Inventory availability
- Persistent user sessions
- Multi-language support
- Voice input

The chatbot is a **read-only informational assistant** over the provided dataset.

## Behavioral Guarantees

### 1. No Hallucinated Prices

All prices must come directly from structured data. If an item is not found, the system will respond:
> "I couldn't find that item. Did you mean one of these: …?"

### 2. Deterministic Factual Logic

The LLM **never computes**:
- Prices
- Discount rules
- Nutrition totals

The LLM is limited to:
- Intent detection
- Entity extraction

### 3. Safe Failure

If:
- Item resolution confidence is low
- Multiple matches found
- Discount mapping incomplete

The system will:
- Ask clarifying questions
- Or explain dataset limitations

### 4. Runnable Without OpenAI Key

If `OPENAI_API_KEY` is not present:
- System still runs
- Rule-based router is used automatically

## Architecture

High-level flow:

- `src.bootstrap.load_index()` loads and normalizes `data/dataset.json`, then builds a `MenuIndex`
- `src.chat.answer()` routes the question (LLM if available, otherwise rule-based fallback) and calls deterministic tools for facts

## Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)

### Setup

```bash
uv venv
uv sync
```

### Environment variables

- `OPENAI_API_KEY`: if set, routing will use the LLM first; otherwise it automatically falls back to the rule-based router.
- `OPENAI_MODEL` (optional): overrides the router model (default is `gpt-4o-mini`).
- `DEBUG_ROUTER=1` (optional): prints which router path was chosen (never logs API keys).

### Running Tests

```bash
uv run pytest -v
```

### Quickstart (bootstrap + chat)

```bash
uv run python -c "from src.bootstrap import load_index; from src.chat import answer; idx=load_index('data/dataset.json'); print(answer('What is the price of a small NUTTY BOWL?', idx))"
```

### Running the Smoke Test

```bash
uv run python src/ingest.py
```

## Example questions

- “What is the price of a small NUTTY BOWL?”
- “How many calories does the GO GREEN smoothie have?”
- “Which salads do you have?”
- “What discounts are available?”
- “What items trigger BOGO Any Smoothie discount?”
- “Is the price for Smoothie - ACAI ELIXIR the same in all channels?”

## Project Structure

```
menu-chatbot/
│
├── README.md
├── pyproject.toml
│
├── data/
│   └── dataset.json
│
├── src/
│   ├── models.py
│   ├── ingest.py
│   ├── normalize.py
│   ├── index.py
│   ├── utils.py
│   ├── tools.py
│   ├── router_schema.py
│   ├── llm_router.py
│   ├── fallback_router.py
│   ├── router.py
│
├── tests/
│   ├── golden_questions.json
│   ├── test_ingest.py
│   ├── test_normalize.py
│   ├── test_index.py
│   ├── test_resolution.py
│   ├── test_tools_price.py
│   ├── test_tools_nutrition.py
│   ├── test_tools_category.py
│   ├── test_tools_discounts.py
│   ├── test_llm_router.py
│   ├── test_fallback_router.py
│   └── test_router_orchestrator.py
```

## Testing

Golden test cases are defined in `tests/golden_questions.json`. These validate:
- Intent detection
- Entity resolution
- Structured answer generation
- No crashes

## Issues Faced & Solutions Taken

### 1. Heterogeneous Nested Menu Structure

The dataset is a deeply nested tree containing categories, sellable items, modifier groups, discounts, taxes, and other entities at different levels.

**Challenge:**
There is no single flat schema suitable for direct question answering.

**Solution:**
Implemented a generic traversal layer to walk the tree deterministically, followed by a normalization pass that extracts structured `MenuItem`, `Category`, and `Discount` entities.
Root detection required heuristic scanning since the top-level JSON contains multiple entity types.

---

### 2. Inconsistent Pricing Structures

Some items have a single price, while others use portion-based pricing (Small / Medium / Large).

**Challenge:**
Without normalization, price logic becomes brittle and ambiguous.

**Solution:**
Normalized all pricing into a unified `List[Price]` schema with optional portion labels.
Portion resolution is handled explicitly and never inferred implicitly.

---

### 3. Partial or Mixed Nutrition Data

Calories are sometimes structured and sometimes embedded in descriptive text.

**Solution:**
Preferred structured nutrition fields when available and implemented safe fallback parsing from text when necessary.

---

### 4. Relational Discount Logic

Discount definitions live outside the main menu tree and must be joined to items.

**Challenge:**
Mappings are sometimes incomplete.

**Solution:**
Extracted discount definitions separately and performed deterministic joins where possible.
If mappings are incomplete, the system returns a partial answer with an explicit explanation rather than guessing.

---

### 5. Entity Resolution & Ambiguity

User queries rarely match dataset titles exactly (e.g., “nutty bowl” vs canonical title).

**Solution:**
Implemented deterministic normalization and fuzzy matching with strict thresholds.
Ambiguous matches return clarification prompts instead of selecting arbitrarily.

This prevents incorrect menu responses, critical for pricing data.

---

### 6. LLM Integration Strategy

Natural language queries require intent parsing and entity extraction.

**Design Choice:**
The LLM is used only for routing (intent + entity extraction).
All pricing, calorie, and discount logic remains deterministic.

This hybrid approach ensures:

* Correctness (no hallucinated prices)
* Transparency
* Safe fallback if the LLM is unavailable

---

### 7. Reliability & Evaluator Experience

Evaluators may not provide API keys.

**Solution:**
Implemented a rule-based fallback router so the system runs without any external dependencies.
LLM routing enhances interpretation when available but is never required for correctness.

## License

No license. Provided for evaluation purposes only.
