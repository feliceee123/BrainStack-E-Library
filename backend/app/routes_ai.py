"""
Embedded Agentic AI Assistant (Phase 3).

- Understands natural language
- Calls real tools against the live PostgreSQL catalog
- Supports multi-turn context
- Asks for confirmation before saving to My Library
- Works for both web and Android clients via the same /api/ai/chat endpoint
"""
import json
import os
import re
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .ai_tools import TOOL_DEFINITIONS, execute_tool
from .db import get_db
from .deps import current_principal

router = APIRouter(prefix="/api/ai", tags=["ai"])

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_items=1)
    # Optional: client can send a conversation_id later if we persist history


class ChatResponse(BaseModel):
    reply: str
    tool_calls_made: list[dict] = []
    books: list[dict] = []          # any books returned by tools (for rich UI)
    requires_confirmation: bool = False
    pending_save_book_id: Optional[int] = None


def _load_conversation(db, p: dict) -> list[dict]:
    with db.cursor() as cur:
        if p["user_id"]:
            cur.execute(
                "SELECT messages FROM ai_conversations WHERE user_id = %s ORDER BY updated_at DESC LIMIT 1",
                (p["user_id"],),
            )
        else:
            cur.execute(
                "SELECT messages FROM ai_conversations WHERE guest_id = %s ORDER BY updated_at DESC LIMIT 1",
                (p["guest_id"],),
            )
        row = cur.fetchone()
    if not row:
        return []
    messages = row["messages"]
    return messages if isinstance(messages, list) else []


def _save_conversation(db, p: dict, messages: list[dict]) -> None:
    messages = messages[-100:]
    with db.cursor() as cur:
        if p["user_id"]:
            cur.execute(
                """
                INSERT INTO ai_conversations (user_id, guest_id, messages)
                VALUES (%s, NULL, CAST(%s AS jsonb))
                ON CONFLICT (user_id) WHERE user_id IS NOT NULL DO UPDATE SET
                    messages = EXCLUDED.messages,
                    updated_at = NOW()
                """,
                (p["user_id"], json.dumps(messages)),
            )
        else:
            cur.execute(
                """
                INSERT INTO ai_conversations (user_id, guest_id, messages)
                VALUES (NULL, %s, CAST(%s AS jsonb))
                ON CONFLICT (guest_id) WHERE guest_id IS NOT NULL DO UPDATE SET
                    messages = EXCLUDED.messages,
                    updated_at = NOW()
                """,
                (p["guest_id"], json.dumps(messages)),
            )


SYSTEM_PROMPT = """You are BrainStack's friendly AI library assistant, embedded in both the website and Android app.

Accuracy and user experience rules:
1. Use real catalog tools for any book search, details, comparisons, or recommendations. Never invent book titles, IDs, availability, licenses, or catalog facts.
2. Search/retrieve first, then explain in clear, friendly language. If no matches, be honest and offer alternate keywords or one focused clarification.
3. Recommend only books returned by catalog tools. Briefly explain fit using retrieved catalog fields.
4. Resolve follow-up references only when conversation context supports them (e.g. "the second one", "that book").
5. Before saving, identify the exact book and request explicit confirmation. Never save from ambiguous consent; only execute save after clear confirmation tied to that book.
6. Guests cannot save to My Library; explain gently and offer registration.
7. Keep responses concise, accessible, and jargon-free. Ask one question at a time.
8. Compare only retrieved catalog fields; don't claim facts absent from catalog descriptions.
9. For unrelated general questions, answer briefly when useful and guide back to library tasks.
"""


# ---------------------------------------------------------------------------
# LLM path (when OPENAI_API_KEY is set)
# ---------------------------------------------------------------------------

async def _call_llm(messages: list[dict], tools: list[dict]) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.3,
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Rule-based fallback (works even without an LLM key – good for demos)
# ---------------------------------------------------------------------------

def _fallback_agent(
    user_text: str,
    db,
    user_id: Optional[int],
    conversation_messages: list[dict] | None = None,
) -> tuple[str, list[dict], list[dict], bool, Optional[int]]:
    """Simple but real tool-calling agent for when no LLM key is available."""
    text = user_text.lower().strip()
    context_text = "\n".join(
        m.get("content", "")
        for m in (conversation_messages or [])
        if m.get("role") in ("user", "assistant")
    )
    context_ids = [int(x) for x in re.findall(r"\b(\d+)\b", context_text)]
    tool_calls: list[dict] = []
    books: list[dict] = []
    requires_confirmation = False
    pending_id = None

    # Detect confirmation to save
    if re.search(r"\b(yes|yeah|yep|sure|confirm|save it|save this|ok save|please save)\b", text):
        m = re.search(r"(?:save|book)\s*#?(\d+)", text)
        if not m:
            recent_ids = list(dict.fromkeys(context_ids))
            if len(recent_ids) == 1:
                m = re.search(r"#?(\d+)", str(recent_ids[0]))
        if m and user_id:
            book_id = int(m.group(1))
            result = execute_tool("save_to_my_library", {"book_id": book_id}, db, user_id)
            tool_calls.append({"tool": "save_to_my_library", "arguments": {"book_id": book_id}, "result": result})
            return result.get("message", "Saved."), tool_calls, books, False, None
        if not user_id:
            return "Only registered users can use My Library. Please create a free account first.", tool_calls, books, False, None
        return (
            "Please confirm by saying something like: **yes, save book 42** (replace 42 with the book id).",
            tool_calls, books, True, None,
        )

    # Search
    if any(k in text for k in ("search", "find", "look for", "show me books", "books about")):
        # Extract query roughly
        query = re.sub(
            r".*?(?:search|find|look for|show me books?|books about)\s+(?:for\s+)?",
            "", text, flags=re.I,
        ).strip(" ?.!")
        if not query:
            query = text
        results = execute_tool("search_books", {"query": query, "limit": 6}, db, user_id)
        tool_calls.append({"tool": "search_books", "arguments": {"query": query}, "result": results})
        books = results
        if not results:
            return f"I couldn't find any books matching '{query}'. Try different keywords.", tool_calls, books, False, None
        lines = [f"**Search results for '{query}':**\n"]
        for b in results:
            lines.append(f"- **{b['title']}** by {b['author']} ({b['category']}) — id: {b['id']}")
        lines.append("\nYou can ask me to compare some of them or recommend similar books.")
        return "\n".join(lines), tool_calls, books, False, None

    # Recommend
    if any(k in text for k in ("recommend", "suggest", "what should i read", "good books")):
        cat = None
        for c in ("classics", "mystery", "science", "adventure", "philosophy", "drama", "romance", "horror"):
            if c in text:
                cat = c
                break
        results = execute_tool(
            "recommend_books",
            {"preferences": text, "category": cat, "limit": 5},
            db, user_id,
        )
        tool_calls.append({"tool": "recommend_books", "arguments": {"preferences": text, "category": cat}, "result": results})
        books = results
        if not results:
            return "I don't have recommendations for that right now.", tool_calls, books, False, None
        lines = ["**Here are some recommendations:**\n"]
        for b in results:
            lines.append(f"- **{b['title']}** by {b['author']} ({b['category']}) — id: {b['id']}")
        lines.append("\nWould you like more details on any of these, or shall I save one to your My Library?")
        return "\n".join(lines), tool_calls, books, False, None

    # Compare
    if "compare" in text:
        ids = [int(x) for x in re.findall(r"\b(\d+)\b", text)]
        if len(ids) < 2:
            ids = list(dict.fromkeys(context_ids))
        if len(ids) >= 2:
            results = execute_tool("compare_books", {"book_ids": ids[:5]}, db, user_id)
            tool_calls.append({"tool": "compare_books", "arguments": {"book_ids": ids[:5]}, "result": results})
            books = results
            if not results:
                return "I couldn't find those books.", tool_calls, books, False, None
            lines = ["**Comparison:**\n"]
            for b in results:
                lines.append(
                    f"### {b['title']} (id {b['id']})\n"
                    f"- Author: {b['author']}\n"
                    f"- Category: {b['category']}\n"
                    f"- {b['description'][:180]}...\n"
                )
            return "\n".join(lines), tool_calls, books, False, None
        return "Please tell me the book ids you want to compare, e.g. 'compare 12 and 45'.", tool_calls, books, False, None

    # Details
    m = re.search(r"(?:details?|info|about)\s+(?:book\s+)?#?(\d+)", text)
    if m:
        book_id = int(m.group(1))
        result = execute_tool("get_book_details", {"book_id": book_id}, db, user_id)
        tool_calls.append({"tool": "get_book_details", "arguments": {"book_id": book_id}, "result": result})
        if not result:
            return f"Book id {book_id} was not found.", tool_calls, books, False, None
        books = [result]
        return (
            f"**{result['title']}** by {result['author']}\n"
            f"- Category: {result['category']}\n"
            f"- License: {result['license']}\n"
            f"- {result['description']}\n\n"
            f"Would you like me to save this book to your My Library? (say: yes, save book {book_id})",
            tool_calls, books, True, book_id,
        )

    # Save intent
    if any(k in text for k in ("save", "add to library", "my library", "favorite")):
        m = re.search(r"\b(\d+)\b", text)
        if m and user_id:
            book_id = int(m.group(1))
            return (
                f"Just to confirm: do you want me to save book **{book_id}** to your My Library? "
                f"Reply with **yes, save book {book_id}**.",
                tool_calls, books, True, book_id,
            )
        if not user_id:
            return "Only registered users can use My Library. Please create a free account first.", tool_calls, books, False, None
        return "Which book would you like to save? Please give me the book id (e.g. 'save book 17').", tool_calls, books, False, None

    # Default help
    return (
        "Hi! I'm the E-Library AI assistant. I can:\n"
        "- **Search** books – e.g. “search for Sherlock Holmes”\n"
        "- **Recommend** books – e.g. “recommend mystery books”\n"
        "- **Compare** books – e.g. “compare 12 and 45”\n"
        "- **Show details** – e.g. “details of book 17”\n"
        "- **Save to My Library** – after you confirm\n\n"
        "What would you like to do?",
        tool_calls, books, False, None,
    )


# ---------------------------------------------------------------------------
# Main chat endpoint
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, p=Depends(current_principal), db=Depends(get_db)):
    user_id = p.get("user_id")
    last_user = next((m for m in reversed(req.messages) if m.role == "user"), None)
    if not last_user:
        raise HTTPException(400, "At least one user message is required")

    conversation = _load_conversation(db, p)
    for incoming in req.messages:
        if incoming.role == "system":
            continue
        message = {"role": incoming.role, "content": incoming.content}
        if conversation and conversation[-1] == message:
            continue
        conversation.append(message)

    def finish(response: ChatResponse) -> ChatResponse:
        conversation.append({"role": "assistant", "content": response.reply})
        _save_conversation(db, p, conversation)
        return response

    # ------------------------------------------------------------------
    # Path A – real LLM with tool calling
    # ------------------------------------------------------------------
    if OPENAI_API_KEY:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in conversation[-24:]:
            messages.append(m)

        tool_calls_made: list[dict] = []
        collected_books: list[dict] = []
        requires_confirmation = False
        pending_save_book_id = None

        # Allow up to 3 tool rounds
        for _ in range(3):
            try:
                data = await _call_llm(messages, TOOL_DEFINITIONS)
            except Exception as e:
                # Fall back if LLM fails
                reply, tool_calls_made, collected_books, requires_confirmation, pending_save_book_id = \
                    _fallback_agent(last_user.content, db, user_id, conversation)
                return finish(ChatResponse(
                    reply=reply,
                    tool_calls_made=tool_calls_made,
                    books=collected_books,
                    requires_confirmation=requires_confirmation,
                    pending_save_book_id=pending_save_book_id,
                ))

            choice = data["choices"][0]["message"]
            messages.append(choice)

            tool_calls = choice.get("tool_calls") or []
            if not tool_calls:
                # Final natural-language answer
                return finish(ChatResponse(
                    reply=choice.get("content") or "Done.",
                    tool_calls_made=tool_calls_made,
                    books=collected_books,
                    requires_confirmation=requires_confirmation,
                    pending_save_book_id=pending_save_book_id,
                ))

            # Execute each tool
            for tc in tool_calls:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = execute_tool(name, args, db, user_id)
                tool_calls_made.append({"tool": name, "arguments": args, "result": result})

                if isinstance(result, list):
                    collected_books.extend(result)
                elif isinstance(result, dict) and "title" in result:
                    collected_books.append(result)

                if name == "save_to_my_library":
                    requires_confirmation = False
                if name in ("get_book_details", "recommend_books", "search_books") and not requires_confirmation:
                    # Heuristic: after showing a book we may want confirmation later
                    pass

                # Feed tool result back to the model
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result, default=str),
                    }
                )

        # If we exit the loop without a final answer
        return finish(ChatResponse(
            reply="I gathered the information above. Let me know if you need anything else!",
            tool_calls_made=tool_calls_made,
            books=collected_books,
        ))

    # ------------------------------------------------------------------
    # Path B – rule-based fallback (no API key needed – perfect for exam demo)
    # ------------------------------------------------------------------
    history = conversation[-24:]
    reply, tool_calls_made, collected_books, requires_confirmation, pending_save_book_id = \
        _fallback_agent(last_user.content, db, user_id, history)

    return finish(ChatResponse(
        reply=reply,
        tool_calls_made=tool_calls_made,
        books=collected_books,
        requires_confirmation=requires_confirmation,
        pending_save_book_id=pending_save_book_id,
    ))


@router.get("/history")
def ai_history(p=Depends(current_principal), db=Depends(get_db)):
    return {"messages": _load_conversation(db, p)}


@router.get("/tools")
def list_tools(p=Depends(current_principal)):
    """Return the tool definitions (useful for documentation / debugging)."""
    return {"tools": [t["function"]["name"] for t in TOOL_DEFINITIONS]}
