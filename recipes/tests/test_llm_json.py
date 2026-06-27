"""Unit tests for recipes.llm_json.extract_json_payload."""
import json

from django.test import SimpleTestCase

from recipes.llm_json import extract_json_payload


class ExtractJsonPayloadTests(SimpleTestCase):
    """Lint the helper against brittle-shape LLM responses."""

    def test_pure_json_dict_parses(self):
        payload = extract_json_payload('{"a": 1, "b": 2}', expected_type=dict)
        self.assertEqual(payload, {"a": 1, "b": 2})

    def test_pure_json_array_parses(self):
        payload = extract_json_payload('[{"a": 1}, {"b": 2}]', expected_type=list)
        self.assertEqual(payload, [{"a": 1}, {"b": 2}])

    def test_markdown_fenced_json_array(self):
        text = "```json\n[{\"a\": 1}]\n```"
        payload = extract_json_payload(text, expected_type=list)
        self.assertEqual(payload, [{"a": 1}])

    def test_markdown_fenced_json_object(self):
        text = "```\n{\"a\": 1}\n```"
        payload = extract_json_payload(text, expected_type=dict)
        self.assertEqual(payload, {"a": 1})

    def test_object_with_prose_preamble(self):
        text = (
            "Sure! Here's what I extracted:\n\n"
            '{"title": "Beans", "ingredients": [{"name": "black beans"}]}\n'
        )
        payload = extract_json_payload(text, expected_type=dict)
        self.assertEqual(payload["title"], "Beans")

    def test_array_with_prose_preamble(self):
        text = (
            "Here is the recipe you requested.\n\n"
            '[{"title": "Beans"}, {"title": "Rice"}]\n'
        )
        payload = extract_json_payload(text, expected_type=list)
        self.assertEqual(len(payload), 2)

    def test_json_followed_by_extra_data_returns_first_object(self):
        text = '{"a": 1}\n\nLet me know if you need anything else!'
        payload = extract_json_payload(text, expected_type=dict)
        self.assertEqual(payload, {"a": 1})

    def test_array_followed_by_chatter_returns_array(self):
        text = '[{"name": "x"}]\nHope this helps!'
        payload = extract_json_payload(text, expected_type=list)
        self.assertEqual(payload, [{"name": "x"}])

    def test_multiple_sequential_blobs_returns_each_when_matched(self):
        text = (
            '{"first": 1}\n'
            'And then this:\n'
            '{"second": 2}\n'
        )
        payload = extract_json_payload(text, expected_type=dict)
        # Both are dicts; the helper returns the one matching the expected
        # type — for a single-object API we always want the first match.
        self.assertIn("first", payload)

    def test_single_object_against_expected_list_wraps_in_one_item_list(self):
        text = '{"a": 1}'
        payload = extract_json_payload(text, expected_type=list)
        self.assertEqual(payload, [{"a": 1}])

    def test_single_array_against_expected_dict_returns_none(self):
        # Caller asked for dict; only an array showed up — fail loudly so
        # the wrong-shape response never reaches downstream code.
        with self.assertRaises(RuntimeError):
            extract_json_payload('[{"a": 1}]', expected_type=dict)

    def test_invalid_json_anywhere_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            extract_json_payload("not json at all", expected_type=dict)

    def test_empty_input_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            extract_json_payload("", expected_type=dict)

    def test_nested_arrays_inside_object_does_not_misclassify_object(self):
        """Regression for the prior bug: greedy regex matched the inner
        ``[ingredients]`` array, returning a list of partial objects
        when the model actually sent a single recipe object."""
        text = (
            '{"title": "Soup",'
            ' "ingredients": [{"name": "carrot"}, {"name": "celery"}],'
            ' "instructions": [{"step": 1, "text": "chop"}]}'
        )
        payload = extract_json_payload(text, expected_type=dict)
        self.assertEqual(payload["title"], "Soup")
        # The single object is NOT mistakenly flattened to just the
        # ingredients list, and the helper returns the full object.
        self.assertEqual(len(payload["ingredients"]), 2)
        self.assertEqual(len(payload["instructions"]), 1)

    def test_unexpected_type_raises_value_error(self):
        with self.assertRaises(ValueError):
            extract_json_payload("{}", expected_type=int)

    def test_fenced_object_with_prose_around_fence(self):
        text = (
            "Here you go!\n"
            "```json\n"
            '{"a": 1}\n'
            "```\n"
            "Cheers!\n"
        )
        payload = extract_json_payload(text, expected_type=dict)
        self.assertEqual(payload, {"a": 1})

    def test_array_with_inner_object_does_not_serve_object(self):
        """When expected_type=dict and the model returns an array, the
        helper must not quietly return the first inner object of that
        array — it should fail loud so the caller knows the response
        shape is wrong."""
        with self.assertRaises(RuntimeError):
            extract_json_payload(
                '[{"a": 1}, {"b": 2}]',
                expected_type=dict,
            )

    def test_object_followed_by_comment_then_another_object(self):
        text = '{"a": 1}\n# note: also tried this:\n{"b": 2}'
        payload = extract_json_payload(text, expected_type=dict)
        # First parse wins when both shapes match the expected type.
        self.assertEqual(payload, {"a": 1})

    def test_array_with_prose_around_outer_brackets(self):
        # A model that wraps the array in prose before *and* after the
        # brackets should still yield the array, not just the first
        # inner object.
        text = (
            "Here is the array you requested:\n"
            "[\n"
            '{"a": 1},\n'
            '{"b": 2}\n'
            "]\n"
            "Hope it helps!"
        )
        payload = extract_json_payload(text, expected_type=list)
        self.assertEqual(payload, [{"a": 1}, {"b": 2}])

    def test_prose_only_response_raises_runtime_error(self):
        text = (
            "I'm sorry, but I can't help with that request. "
            "Please ask a different question."
        )
        with self.assertRaises(RuntimeError):
            extract_json_payload(text, expected_type=dict)

    def test_null_response_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            extract_json_payload("null", expected_type=dict)

    def test_string_scalar_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            extract_json_payload('"just a string"', expected_type=dict)
