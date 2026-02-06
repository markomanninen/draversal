import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from draversal_mcp import tools


class TestSchemaValidation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = os.path.join(self.temp_dir.name, "trees.json")
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.store_path
        self.children_field = "sections"

    def tearDown(self):
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def _require_jsonschema(self):
        try:
            import jsonschema  # noqa: F401
        except ImportError:
            self.skipTest("jsonschema not installed")

    def test_invalid_schema_rejected(self):
        self._require_jsonschema()
        schema = {"type": "not-a-type"}
        data = {"title": "Root", self.children_field: []}
        with self.assertRaises(ValueError) as context:
            tools.save_tree(data, self.children_field, schema=schema)
        self.assertIn("Schema is invalid", str(context.exception))

    def test_allow_additional_false_rejects_extra(self):
        self._require_jsonschema()
        schema = {
            "type": "object",
            "required": ["title"],
            "properties": {"title": {"type": "string"}},
            "allow_additional": False,
        }
        data = {
            "title": "Root",
            self.children_field: [],
            "extra": "not-allowed",
        }
        with self.assertRaises(ValueError) as context:
            tools.save_tree(data, self.children_field, schema=schema)
        self.assertIn("additional properties", str(context.exception).lower())

    def test_children_field_defaults_to_self_ref(self):
        self._require_jsonschema()
        schema = {
            "type": "object",
            "required": ["title"],
            "properties": {"title": {"type": "string"}},
        }
        data = {
            "title": "Root",
            self.children_field: [{"kind": "chapter"}],
        }
        with self.assertRaises(ValueError) as context:
            tools.save_tree(data, self.children_field, schema=schema)
        self.assertIn("Schema validation failed", str(context.exception))

    def test_file_ref_resolution_succeeds(self):
        self._require_jsonschema()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            common_path = temp_path / "schema_common.json"
            chapter_path = temp_path / "schema_chapter.json"
            common_id = common_path.resolve().as_uri()
            chapter_id = chapter_path.resolve().as_uri()

            common_schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": common_id,
                "$defs": {
                    "kind_chapter": {
                        "type": "string",
                        "enum": ["book", "part", "chapter", "section"],
                    },
                    "status_chapter": {
                        "type": "string",
                        "enum": ["todo", "draft", "review", "done"],
                    },
                },
            }
            chapter_schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": chapter_id,
                "required": ["title", "kind", "status"],
                "properties": {
                    "title": {"type": "string"},
                    "kind": {"$ref": f"{common_id}#/$defs/kind_chapter"},
                    "status": {"$ref": f"{common_id}#/$defs/status_chapter"},
                },
                "additionalProperties": True,
            }

            common_path.write_text(json.dumps(common_schema))
            chapter_path.write_text(json.dumps(chapter_schema))

            data = {
                "title": "Root",
                "kind": "book",
                "status": "draft",
                self.children_field: [
                    {"title": "Chapter 1", "kind": "chapter", "status": "todo"}
                ],
            }
            tools.save_tree(data, self.children_field, schema=chapter_schema)

    def test_relative_file_ref_resolution_succeeds(self):
        self._require_jsonschema()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            common_path = temp_path / "schema_common.json"
            chapter_path = temp_path / "schema_chapter.json"
            chapter_id = chapter_path.resolve().as_uri()

            common_schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": common_path.resolve().as_uri(),
                "$defs": {
                    "kind_chapter": {
                        "type": "string",
                        "enum": ["book", "part", "chapter", "section"],
                    }
                },
            }
            chapter_schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": chapter_id,
                "required": ["title", "kind"],
                "properties": {
                    "title": {"type": "string"},
                    "kind": {"$ref": "schema_common.json#/$defs/kind_chapter"},
                },
            }

            common_path.write_text(json.dumps(common_schema))
            chapter_path.write_text(json.dumps(chapter_schema))

            data = {
                "title": "Root",
                "kind": "book",
                self.children_field: [],
            }
            tools.save_tree(data, self.children_field, schema=chapter_schema)

    def test_relative_file_ref_missing_fails(self):
        self._require_jsonschema()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            chapter_path = temp_path / "schema_chapter.json"
            chapter_schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": chapter_path.resolve().as_uri(),
                "required": ["title", "kind"],
                "properties": {
                    "title": {"type": "string"},
                    "kind": {"$ref": "missing_common.json#/$defs/kind_chapter"},
                },
            }
            chapter_path.write_text(json.dumps(chapter_schema))

            data = {
                "title": "Root",
                "kind": "book",
                self.children_field: [],
            }
            with self.assertRaises(ValueError) as context:
                tools.save_tree(data, self.children_field, schema=chapter_schema)
            self.assertIn("Schema reference could not be resolved", str(context.exception))

    def test_missing_file_ref_raises(self):
        self._require_jsonschema()
        sample_dir = Path(__file__).resolve().parents[1] / "samples"
        schema_path = sample_dir / "schema_chapter_ref.json"
        schema = json.loads(schema_path.read_text())
        data = {
            "title": "Root",
            "kind": "book",
            "status": "draft",
            self.children_field: [],
        }
        with self.assertRaises(ValueError) as context:
            tools.save_tree(data, self.children_field, schema=schema)
        self.assertIn("Schema reference could not be resolved", str(context.exception))

    @mock.patch("draversal_mcp.tools.urlopen", side_effect=OSError("offline"))
    def test_remote_ref_raises(self, _mock_urlopen):
        self._require_jsonschema()
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://example.com/schemas/schema_chapter_remote_ref.json",
            "required": ["title", "kind", "status"],
            "properties": {
                "title": {"type": "string"},
                "kind": {
                    "$ref": "https://example.com/schemas/schema_common.json#/$defs/kind_chapter"
                },
                "status": {
                    "$ref": "https://example.com/schemas/schema_common.json#/$defs/status_chapter"
                },
            },
            "additionalProperties": True,
        }
        data = {
            "title": "Root",
            "kind": "book",
            "status": "draft",
            self.children_field: [],
        }
        with self.assertRaises(ValueError) as context:
            tools.save_tree(data, self.children_field, schema=schema)
        self.assertIn("Schema reference could not be resolved", str(context.exception))


if __name__ == "__main__":
    unittest.main()
