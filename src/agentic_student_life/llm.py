"""LLM wrapper around aisuite with Gemini 3 thought_signature preservation,
retries/backoff, Pydantic JSON parsing + repair, and per-call trace logging."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Type, TypeVar
import uuid

import aisuite as ai
from aisuite.framework import ChatCompletionResponse
from aisuite.framework.message import ChatCompletionMessageToolCall, Function, Message
from aisuite.providers import gemini_provider
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_LOCK = threading.Lock()
_THOUGHT_SIGS: dict[str, Any] = {}
_PATCHED = False


def _patch_aisuite_gemini() -> None:
    """Patch aisuite's GeminiMessageConverter so that:
    1. `response_mime_type` and `thinking_config` are allowed in CONFIG_KEYS.
    2. `thought` parts (internal thinking) are not concatenated into visible message text.
    3. `thought_signature` on `function_call` parts is preserved across multi-turn tool loops
       (required by Gemini 3.x models when sending tool results back).
    """
    global _PATCHED
    with _LOCK:
        if _PATCHED:
            return
        gemini_provider.CONFIG_KEYS.update({"response_mime_type", "thinking_config", "response_schema"})
        converter_cls = gemini_provider.GeminiMessageConverter

        @staticmethod
        def parse_candidate(response):
            texts, calls, finish = [], [], None
            candidates = getattr(response, "candidates", None) or []
            if not candidates:
                return texts, calls, finish
            candidate = candidates[0]
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                is_thought = bool(getattr(part, "thought", False))
                text = getattr(part, "text", None)
                if text and not is_thought:
                    texts.append(text)
                function_call = getattr(part, "function_call", None)
                if function_call is not None:
                    sig = getattr(part, "thought_signature", None)
                    calls.append(
                        {
                            "name": getattr(function_call, "name", "") or "",
                            "args": dict(getattr(function_call, "args", None) or {}),
                            "thought_signature": sig,
                        }
                    )
            raw_finish = getattr(candidate, "finish_reason", None)
            if raw_finish is not None:
                finish = getattr(raw_finish, "name", None) or str(raw_finish)
            return texts, calls, finish

        def convert_response(self, response):
            texts, calls, finish = self.parse_candidate(response)
            tool_calls = []
            for call in calls:
                cid = f"call_{uuid.uuid4().hex[:12]}"
                args_str = json.dumps(call["args"], sort_keys=True)
                if call.get("thought_signature") is not None:
                    with _LOCK:
                        _THOUGHT_SIGS[cid] = call["thought_signature"]
                        _THOUGHT_SIGS[f"{call['name']}:{args_str}"] = call["thought_signature"]
                tool_calls.append(
                    ChatCompletionMessageToolCall(
                        id=cid,
                        type="function",
                        function=Function(name=call["name"], arguments=args_str),
                    )
                )
            normalized_response = ChatCompletionResponse()
            normalized_response.choices[0].message = Message(
                content="".join(texts) or None,
                tool_calls=tool_calls or None,
                role="assistant",
                refusal=None,
            )
            normalized_response.choices[0].finish_reason = self.map_finish_reason(
                finish, bool(tool_calls)
            )
            normalized_response.usage = self.get_completion_usage(
                getattr(response, "usage_metadata", None)
            )
            return normalized_response

        orig_convert_request = converter_cls.convert_request

        def convert_request(self, messages):
            system, folded = orig_convert_request(self, messages)
            # Attach preserved thought_signature to model function_call parts
            # by matching the call id or (name, args) from input messages.
            msg_dicts = [self._as_dict(m) for m in messages]
            call_sig_queue: list[Any] = []
            for m in msg_dicts:
                if m.get("role") == "assistant":
                    for call in m.get("tool_calls") or []:
                        cid = call.get("id") or ""
                        fn = call.get("function") or {}
                        name = fn.get("name") or ""
                        parsed_args = self._parse_args(fn.get("arguments"))
                        key2 = f"{name}:{json.dumps(parsed_args, sort_keys=True)}"
                        with _LOCK:
                            sig = _THOUGHT_SIGS.get(cid) or _THOUGHT_SIGS.get(key2)
                        call_sig_queue.append(sig)
            idx = 0
            for item in folded:
                if item.get("role") == "model":
                    for p in item.get("parts") or []:
                        if "function_call" in p:
                            sig = call_sig_queue[idx] if idx < len(call_sig_queue) else None
                            idx += 1
                            if sig is not None:
                                p["thought_signature"] = sig
            return system, folded

        converter_cls.parse_candidate = parse_candidate
        converter_cls.convert_response = convert_response
        converter_cls.convert_request = convert_request
        _PATCHED = True


JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def extract_json_str(text: str) -> str:
    """Extract a JSON object or array string from raw LLM output."""
    if not text:
        raise ValueError("Empty model output")
    text = text.strip()
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        return text
    m = JSON_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    raise ValueError(f"Could not locate JSON object in output: {text[:200]!r}")


class CallTracker:
    """Tracks LLM and tool calls for a single case and writes to `calls.jsonl`."""

    def __init__(self, case_id: str, config_id: str, calls_log_path: Path | None = None):
        self.case_id = case_id
        self.config_id = config_id
        self.calls_log_path = calls_log_path
        self.llm_calls = 0
        self.tool_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.per_agent: dict[str, dict[str, int]] = {}
        self.models_used: set[str] = set()
        self.tool_records: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def record_llm(
        self,
        agent: str,
        model: str,
        turns: int,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        latency_s: float,
        prompt_preview: str,
        response_preview: str,
        tool_calls_made: int = 0,
    ) -> None:
        with self._lock:
            self.llm_calls += turns
            self.models_used.add(model)
            self.tool_calls += tool_calls_made
            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens
            self.total_tokens += total_tokens
            ag = self.per_agent.setdefault(agent, {"calls": 0, "tokens": 0})
            ag["calls"] += turns
            ag["tokens"] += total_tokens
            if self.calls_log_path is not None:
                rec = {
                    "case_id": self.case_id,
                    "config_id": self.config_id,
                    "agent": agent,
                    "model": model,
                    "llm_turns": turns,
                    "tool_calls": tool_calls_made,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "latency_s": round(latency_s, 3),
                    "prompt_preview": prompt_preview[:400],
                    "response_preview": response_preview[:500],
                }
                with self.calls_log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec) + "\n")

    def wrap_tools(self, tools: list[Callable]) -> list[Callable]:
        """Wrap tools so every invocation is recorded in `self.tool_records` with its output."""
        wrapped = []
        for fn in tools:
            def _make_wrapper(orig_fn: Callable) -> Callable:
                def wrapper(*args, **kwargs):
                    res = orig_fn(*args, **kwargs)
                    with self._lock:
                        self.tool_records.append(
                            {
                                "tool": orig_fn.__name__,
                                "args": kwargs if kwargs else list(args),
                                "result": res,
                            }
                        )
                    return res

                wrapper.__name__ = orig_fn.__name__
                wrapper.__doc__ = orig_fn.__doc__
                wrapper.__annotations__ = getattr(orig_fn, "__annotations__", {})
                import inspect
                wrapper.__signature__ = inspect.signature(orig_fn)  # type: ignore[attr-defined]
                return wrapper

            wrapped.append(_make_wrapper(fn))
        return wrapped

    def summary(self, latency_s: float) -> dict[str, Any]:
        return {
            "llm_calls": self.llm_calls,
            "tool_calls": max(self.tool_calls, len(self.tool_records)),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_s": round(latency_s, 2),
            "per_agent": self.per_agent,
            "models_used": sorted(self.models_used),
        }


class LLMClient:
    """Thread-safe wrapper around aisuite.Client with retries, tool tracking, and Pydantic JSON parsing."""

    def __init__(self, env_path: str = ".env", *, max_output_tokens: int = 8192,
                 thinking_level: str | None = None, usage_budget=None):
        load_dotenv(env_path)
        _patch_aisuite_gemini()
        self._local = threading.local()
        self.max_output_tokens = max_output_tokens
        self.thinking_level = thinking_level
        self.usage_budget = usage_budget
        self._gemini_credentials = []
        for name in ("GEMINI_API_KEY", "GEMINI_API_KEY_FREE"):
            value = os.getenv(name)
            if value and value not in [key for _, key in self._gemini_credentials]:
                self._gemini_credentials.append((name, value))

    @property
    def client(self) -> ai.Client:
        slot = getattr(self._local, "credential_slot", 0)
        if not hasattr(self._local, "clients"):
            self._local.clients = {}
        if slot not in self._local.clients:
            client = ai.Client()
            if self._gemini_credentials:
                name, key = self._gemini_credentials[slot]
                provider = gemini_provider.GeminiProvider(
                    api_key=key, http_options={"timeout": 90_000})
                if self.usage_budget:
                    provider.client.models.generate_content = self.usage_budget.wrap(
                        provider.client.models.generate_content, name)
                client.providers["gemini"] = provider
            self._local.clients[slot] = client
        return self._local.clients[slot]

    def _rotate_credential(self):
        credentials = getattr(self, "_gemini_credentials", [])
        if len(credentials) < 2:
            return False
        slot = getattr(self._local, "credential_slot", 0)
        self._local.credential_slot = (slot + 1) % len(credentials)
        return True

    def _redact(self, message):
        for _, key in getattr(self, "_gemini_credentials", []):
            message = message.replace(key, "[REDACTED]")
        return message

    def _call_with_retry(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.3,
        tools: list[Callable] | None = None,
        max_turns: int | None = None,
        json_mode: bool = False,
        max_retries: int = 18,
    ) -> tuple[Any, str, float]:
        kwargs: dict[str, Any] = {"temperature": temperature}
        kwargs["max_output_tokens"] = getattr(self, "max_output_tokens", 8192)
        if model.startswith("gemini:") and getattr(self, "thinking_level", None):
            kwargs["thinking_config"] = {"thinking_level": self.thinking_level}
        if tools:
            kwargs["tools"] = tools
            if max_turns is not None:
                kwargs["max_turns"] = max_turns
        elif json_mode and model.startswith("gemini:"):
            kwargs["response_mime_type"] = "application/json"

        last_err: Exception | None = None
        rejected_slots = set()
        for attempt in range(max_retries):
            # A model switch changes the experimental treatment. Retry this model only.
            cur_model = model
            t0 = time.perf_counter()
            try:
                resp = self.client.chat.completions.create(
                    model=cur_model,
                    messages=messages,
                    **kwargs,
                )
                return resp, cur_model, time.perf_counter() - t0
            except Exception as e:
                last_err = e
                err_str = str(e)
                status = getattr(e, "code", None)
                if status is None:
                    match = re.match(r"\s*(401|403|429|500|503)\b", err_str)
                    status = int(match.group(1)) if match else None
                if "thinking_budget" in err_str or "thinking_config" in err_str or "Thinking" in err_str:
                    kwargs.pop("thinking_config", None)
                    continue
                if "PerDay" in err_str or "per day" in err_str.lower():
                    slot = getattr(getattr(self, "_local", None), "credential_slot", 0)
                    rejected_slots.add(slot)
                    if (model.startswith("gemini:") and
                            len(rejected_slots) < len(getattr(self, "_gemini_credentials", [])) and
                            self._rotate_credential()):
                        continue
                    raise RuntimeError(self._redact(err_str)) from None
                if model.startswith("gemini:") and (
                    status in (401, 403, 429) or "API_KEY_INVALID" in err_str
                ):
                    slot = getattr(getattr(self, "_local", None), "credential_slot", 0)
                    rejected_slots.add(slot)
                    rotated = self._rotate_credential()
                    if status in (401, 403) or "API_KEY_INVALID" in err_str:
                        if rotated and len(rejected_slots) < len(self._gemini_credentials):
                            continue
                        raise RuntimeError(self._redact(err_str)) from None
                if any(
                    code in err_str
                    for code in (
                        "429",
                        "503",
                        "500",
                        "RESOURCE_EXHAUSTED",
                        "UNAVAILABLE",
                        "Connection reset",
                        "ReadError",
                        "ConnectError",
                        "ServerDisconnected",
                    )
                ):
                    sleep_s = min(30.0, 6.0 * (attempt + 1))
                    time.sleep(sleep_s)
                    continue
                raise RuntimeError(self._redact(err_str)) from None
        assert last_err is not None
        raise RuntimeError(self._redact(str(last_err))) from None

    @staticmethod
    def _extract_usage(resp: Any) -> tuple[int, int, int, int, int]:
        """Return (turns, tool_calls, prompt_tokens, completion_tokens, total_tokens)."""
        all_resps = list(getattr(resp, "intermediate_responses", None) or []) + [resp]
        turns = len(all_resps)
        p_tok = c_tok = t_tok = 0
        tool_calls = 0
        for r in all_resps:
            u = getattr(r, "usage", None)
            if u is not None:
                p = getattr(u, "prompt_tokens", 0) or 0
                c = getattr(u, "completion_tokens", 0) or 0
                tot = getattr(u, "total_tokens", None) or (p + c)
                p_tok += p
                c_tok += c
                t_tok += tot
            try:
                tcs = r.choices[0].message.tool_calls
                if tcs:
                    tool_calls += len(tcs)
            except Exception:
                pass
        return turns, tool_calls, p_tok, c_tok, t_tok

    def complete_text(
        self,
        *,
        agent: str,
        model: str,
        system: str,
        user: str,
        tracker: CallTracker | None = None,
        temperature: float = 0.3,
        tools: list[Callable] | None = None,
        max_turns: int | None = None,
    ) -> str:
        wrapped_tools = tracker.wrap_tools(tools) if (tools and tracker) else tools
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        resp, used_model, elapsed = self._call_with_retry(
            model=model,
            messages=messages,
            temperature=temperature,
            tools=wrapped_tools,
            max_turns=max_turns,
            json_mode=False,
        )
        text = (resp.choices[0].message.content or "").strip()
        turns, t_calls, p_tok, c_tok, tot_tok = self._extract_usage(resp)
        if tracker is not None:
            tracker.record_llm(
                agent=agent,
                model=used_model,
                turns=turns,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                total_tokens=tot_tok,
                latency_s=elapsed,
                prompt_preview=user,
                response_preview=text,
                tool_calls_made=t_calls,
            )
        return text

    def complete_json(
        self,
        *,
        agent: str,
        model: str,
        system: str,
        user: str,
        schema: Type[T],
        tracker: CallTracker | None = None,
        temperature: float = 0.3,
        tools: list[Callable] | None = None,
        max_turns: int | None = None,
    ) -> T:
        """Run an LLM call (optionally with tools) and validate the final output against `schema`.
        Retries once with a repair prompt if JSON parsing or Pydantic validation fails."""
        wrapped_tools = tracker.wrap_tools(tools) if (tools and tracker) else tools
        schema_str = json.dumps(schema.model_json_schema())
        system_with_schema = (
            f"{system}\n\n"
            f"IMPORTANT: Your final response MUST be a valid JSON object matching this exact JSON Schema "
            f"(no extra commentary outside JSON):\n{schema_str}"
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_with_schema},
            {"role": "user", "content": user},
        ]
        resp, used_model, elapsed = self._call_with_retry(
            model=model,
            messages=messages,
            temperature=temperature,
            tools=wrapped_tools,
            max_turns=max_turns,
            json_mode=(tools is None),
        )
        text = (resp.choices[0].message.content or "").strip()
        turns, t_calls, p_tok, c_tok, tot_tok = self._extract_usage(resp)
        if tracker is not None:
            tracker.record_llm(
                agent=agent,
                model=used_model,
                turns=turns,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                total_tokens=tot_tok,
                latency_s=elapsed,
                prompt_preview=user,
                response_preview=text,
                tool_calls_made=t_calls,
            )
        try:
            raw_json = extract_json_str(text)
            return schema.model_validate_json(raw_json)
        except (ValueError, ValidationError, json.JSONDecodeError) as err:
            repair_user = (
                f"Your previous response could not be parsed as valid JSON matching the schema.\n"
                f"Validation error: {err}\n\n"
                f"Previous response:\n{text}\n\n"
                f"Expected JSON schema:\n{json.dumps(schema.model_json_schema(), indent=2)}\n\n"
                f"Return ONLY a valid JSON object matching the schema."
            )
            resp2, used_model2, elapsed2 = self._call_with_retry(
                model=model,
                messages=[
                    {"role": "system", "content": "You repair malformed JSON into valid schema-compliant JSON."},
                    {"role": "user", "content": repair_user},
                ],
                temperature=0.0,
                tools=None,
                max_turns=None,
                json_mode=True,
            )
            text2 = (resp2.choices[0].message.content or "").strip()
            turns2, t_calls2, p_tok2, c_tok2, tot_tok2 = self._extract_usage(resp2)
            if tracker is not None:
                tracker.record_llm(
                    agent=f"{agent}_repair",
                    model=used_model2,
                    turns=turns2,
                    prompt_tokens=p_tok2,
                    completion_tokens=c_tok2,
                    total_tokens=tot_tok2,
                    latency_s=elapsed2,
                    prompt_preview=repair_user,
                    response_preview=text2,
                    tool_calls_made=t_calls2,
                )
            raw_json2 = extract_json_str(text2)
            return schema.model_validate_json(raw_json2)
