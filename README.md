# Menu Q&A Chatbot

A hybrid LLM + deterministic architecture chatbot that answers questions about restaurant menu items, pricing, nutrition, categories, and discounts.

## Colab demo

Open the notebook in Colab (replace placeholders with your repo details):

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
- Never hallucinates prices — all prices come from structured data

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

## License

No license. Provided for evaluation purposes only.
