"""A Meta Model API stand-in that records calls and refuses wrong models."""
import json
from types import SimpleNamespace


class FakeMeta:
    def __init__(self, chat_replies=(), sam_text=""):
        self.chat_replies = list(chat_replies)
        self.sam_text = sam_text
        self.calls = []
        self.files = SimpleNamespace(create=self._file_create)
        self.responses = SimpleNamespace(create=self._responses_create)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat_create))

    def _file_create(self, file, purpose):
        assert purpose == "user_data"
        self.calls.append(("file", file.name))
        return SimpleNamespace(id=f"file-{len(self.calls)}")

    def _responses_create(self, model, input):
        assert model == "sam-3.1", model
        self.calls.append(("sam", input))
        return SimpleNamespace(output_text=self.sam_text)

    def _chat_create(self, model, messages, response_format):
        assert model == "muse-spark-1.3", model
        assert response_format["type"] == "json_schema"
        self.calls.append(("chat", messages, response_format))
        reply = self.chat_replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(reply)))])
