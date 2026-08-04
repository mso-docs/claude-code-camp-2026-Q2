from __future__ import annotations

import sys
import unittest
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
BOUKENSHA_DIR = REPO_ROOT / "week1_baseline" / "python" / "12_context"
sys.path.insert(0, str(EVALS_DIR))
sys.path.insert(0, str(BOUKENSHA_DIR))

import ollama_catalog  # noqa: E402
import run_bakery  # noqa: E402
from boukensha.backends.ollama import Ollama  # noqa: E402


class CatalogTests(unittest.TestCase):
    def test_discovers_capabilities_and_deduplicates_aliases(self):
        tags = {
            "models": [
                {"name": "agent:9b", "digest": "same", "size": 9, "details": {"parameter_size": "9B"}},
                {"name": "agent:latest", "digest": "same", "size": 9},
                {"name": "embed:latest", "digest": "embed", "size": 1},
            ]
        }
        shows = {
            "agent:9b": {"capabilities": ["completion", "tools"]},
            "agent:latest": {"capabilities": ["completion", "tools"]},
            "embed:latest": {"capabilities": ["embedding"]},
        }

        def request(path, payload, timeout):
            return tags if path == "/api/tags" else shows[payload["model"]]

        models = ollama_catalog.discover_models("unused", request_json=request)
        selected = ollama_catalog.select_models(models, tools_only=True)
        aliases = ollama_catalog.select_models(models, tools_only=True, include_aliases=True)

        self.assertEqual([model.name for model in selected], ["agent:9b"])
        self.assertEqual([model.name for model in aliases], ["agent:9b", "agent:latest"])
        self.assertEqual(models[0].parameter_size, "9B")

    def test_probe_requires_tool_call_and_post_result_completion(self):
        calls = []

        def request(path, payload, timeout):
            calls.append(payload)
            if len(calls) == 1:
                return {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "boukensha_probe",
                                    "arguments": {"value": "boukensha-probe"},
                                }
                            }
                        ],
                    }
                }
            return {"message": {"role": "assistant", "content": "probe-complete"}}

        result = ollama_catalog.probe_tool_loop("unused", "agent:9b", request_json=request)

        self.assertTrue(result.passed)
        self.assertEqual(result.status, "passed")
        self.assertEqual(calls[1]["messages"][-2]["tool_name"], "boukensha_probe")

    def test_probe_detects_model_stuck_calling_tools(self):
        def request(path, payload, timeout):
            call = {
                "function": {
                    "name": "boukensha_probe",
                    "arguments": {"value": "boukensha-probe"},
                }
            }
            return {"message": {"role": "assistant", "content": "", "tool_calls": [call]}}

        result = ollama_catalog.probe_tool_loop("unused", "looping:latest", request_json=request)

        self.assertFalse(result.passed)
        self.assertEqual(result.status, "tool_loop")

    def test_unlisted_ollama_model_uses_conservative_metadata(self):
        backend = Ollama(host="http://unused.invalid", model="new-agent:latest")

        self.assertEqual(backend.model, "new-agent:latest")
        self.assertEqual(backend.context_window, 32_000)
        self.assertEqual(backend.usage_unit, "local_compute")

    def test_model_directory_sanitizes_namespaces_and_tags(self):
        self.assertEqual(
            run_bakery.model_dir_name("ollama", "cmdmbox/skill-expert:latest"),
            "ollama_cmdmbox-skill-expert-latest",
        )


if __name__ == "__main__":
    unittest.main()
