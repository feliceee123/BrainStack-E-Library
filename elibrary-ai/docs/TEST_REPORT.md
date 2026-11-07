# Test Report - Phase 2 (initial testing evidence)

## 1. Automated API tests (`python -m pytest -v`) - 13 passed
| Test | What it proves |
|---|---|
| test_all | health, validation, register/login, protected routes, search/filter, SQL-injection attempt, server-side logout, guest mode, tampered token |
| test_login_throttle | 6th failed login returns 429 |
| test_catalog_has_200_unique_books_with_legal_sources | 215 unique books, each with license + https source |
| test_book_detail_and_404 | details endpoint; download link hidden until download |
| test_guest_download_limit_is_5_and_repeat_is_free | 6th book refused (403); repeat is free; separate guest sessions independent |
| test_registered_limit_is_10_and_shared_across_logins | limit 10; counter follows the account across logins (web/Android sync) |
| test_admin_access_control_and_crud | users/guests get 403; admin create/update/delete; duplicate 409; unsafe URL 422; stats |
| test_ai_requires_auth | AI endpoint needs a session |
| test_ai_offline_search_details_compare_recommend_with_context | search, details, compare, recommend, context follow-ups, 2 connected tool calls, no invented books |
| test_ai_tool_calls_are_logged_for_admin | tool executions logged and visible to admin |
| test_ai_llm_mode_runs_real_tools_in_a_loop | LLM tool-calling loop (mock provider): search_books -> get_book_details -> final answer |
| test_ai_falls_back_to_offline_when_provider_fails | provider failure does not break the assistant |
| test_ai_input_validation_and_rate_limit | empty/oversized messages rejected; 429 after 20/min |

## 2. Browser end-to-end test (`python tests/e2e_web.py`) - 14/14 checks passed
Guest dashboard 0/5 - catalog 200+ - category filter - download + remaining counter - AI search tool - AI follow-up compare - logout protects pages -
weak password rejected - registered dashboard 0/10 - normal user blocked from admin - admin stats - admin adds a book - admin deletes a book - no console errors.
Screenshots: `backend/screenshots/`.

## 3. Android manual checklist (fill in on your emulator/phone)
| # | Step | Expected | Result |
|---|---|---|---|
| 1 | Welcome > Continue as Guest | Home shows "0 / 5" | |
| 2 | Books > search "python" | 2 Technology books | |
| 3 | Category chip "Mystery" | 8 books | |
| 4 | Open a book > Download | "Ready! 4 of 5 ..." + Open in browser | |
| 5 | Download 6 different books as guest | 6th shows limit message | |
| 6 | AI tab > "recommend a mystery" | list + tool trace + tappable titles | |
| 7 | AI tab > "tell me about the first one" | details of the first listed book | |
| 8 | Register, then log in on the website | same account; downloads count matches | |
| 9 | Profile > Log out; reopen app | back to Welcome | |

## 4. Issues found and fixed during Phase 2
1. "compare the first two" resolved only one book -> reference parser fixed, regression test added.
2. Several books were mis-categorized (e.g. Frankenstein as poetry) -> exact author/title rules.
3. Description cut after "Dr." -> truncate at word boundary.
4. (Phase 1) SQLite connection used across threads on protected routes -> `check_same_thread=False` with one connection per request.
