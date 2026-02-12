# Menu Q&A Chatbot

A hybrid LLM + deterministic architecture chatbot that answers questions about restaurant menu items, pricing, nutrition, categories, and discounts.

## Overview

This chatbot uses a hybrid approach where:
- **LLM handles routing**: Extracts intent and entities (item names, portions, discounts)
- **Deterministic tools handle facts**: All pricing, nutrition, and discount logic is computed from structured data

This ensures factual correctness and prevents hallucinations while leveraging LLM capabilities for natural language understanding.

## Supported Queries

The chatbot supports the following question types:

### 1️⃣ Price Lookup

Ask about item prices, optionally specifying portion size:

- "What is the price of a small NUTTY BOWL?"
- "How much is the ACAI ELIXIR?"
- "How much is the GREEN BOWL Large?"

**Behavior:**
- Correctly resolves item names
- Resolves portion when specified (Small, Medium, Large, etc.)
- If portion not specified but multiple exist → chooses default or asks for clarification
- Never hallucinates prices — all prices come from structured data

### 2️⃣ Nutrition Lookup (Calories)

Query calorie information for menu items:

- "How many calories does the GO GREEN smoothie have?"
- "Calories for Dragon Smoothie"

**Behavior:**
- Prefers structured calorie fields from the dataset
- Falls back to extracting from description if needed
- Returns explicit "Calories not available" if none found

### 3️⃣ Category Listing

List all items in a specific category:

- "Which salads do you have?"
- "What bowls are available?"
- "Show me smoothies"

**Behavior:**
- Returns all items whose category matches
- Excludes modifier groups
- Preserves canonical item names

### 4️⃣ Discount Listing

Get information about available discounts:

- "What discounts are available?"
- "Which discounts include coupons?"

**Behavior:**
- Lists discount definitions from the dataset
- If coupon information not present → states that explicitly

### 5️⃣ Discount Trigger Query

Find which items trigger specific discounts:

- "What items trigger BOGO Any Smoothie discount?"

**Behavior:**
- Attempts to join discount → item groups → items
- If dataset does not allow full mapping → explains limitation clearly

### 6️⃣ Cross-Channel Price Comparison

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

### 1️⃣ No Hallucinated Prices

All prices must come directly from structured data. If an item is not found, the system will respond:
> "I couldn't find that item. Did you mean one of these: …?"

### 2️⃣ Deterministic Factual Logic

The LLM **never computes**:
- Prices
- Discount rules
- Nutrition totals

The LLM is limited to:
- Intent detection
- Entity extraction

### 3️⃣ Safe Failure

If:
- Item resolution confidence is low
- Multiple matches found
- Discount mapping incomplete

The system will:
- Ask clarifying questions
- Or explain dataset limitations

### 4️⃣ Runnable Without OpenAI Key

If `OPENAI_API_KEY` is not present:
- System still runs
- Rule-based router is used automatically

## Architecture

See `specs/SPEC.md` for detailed architectural documentation.

## Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)

### Setup

```bash
uv venv
uv sync
```

### Running Tests

```bash
uv run pytest -v
```

### Running the Smoke Test

```bash
uv run python src/ingest.py
```

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
│   ├── chat.py
│   └── bootstrap.py
│
├── tests/
│   ├── golden_questions.json
│   ├── test_ingest.py
│   ├── test_normalize.py
│   ├── test_tools_price.py
│   ├── test_tools_nutrition.py
│   ├── test_tools_category.py
│   └── test_router.py
│
└── notebooks/
    └── demo.ipynb
```

## Development Status

- ✅ Stage 0: Acceptance Criteria & Golden Questions
- ⏳ Stage 1+: Implementation in progress

## Testing

Golden test cases are defined in `tests/golden_questions.json`. These validate:
- Intent detection
- Entity resolution
- Structured answer generation
- No crashes

## License

[To be determined]
