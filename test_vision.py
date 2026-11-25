import unittest
from unittest.mock import patch
import json
from vision import endpoint,build_payload,parse_answer,ask
class TestVision(unittest.TestCase):
    def test_endpoint(self):
        self.assertEqual(endpoint("https://example.com/v1/"),"https://example.com/v1/chat/completions")
        self.assertEqual(endpoint("http://127.0.0.1:11434/v1"),"http://127.0.0.1:11434/v1/chat/completions")
        with self.assertRaises(ValueError):endpoint("http://example.com/v1")
    def test_payload(self):
        p=build_payload(b"abc","model")
        self.assertEqual(p["messages"][1]["content"][1]["image_url"]["url"],"data:image/png;base64,YWJj")
    def test_reason_prompt(self):
        self.assertIn("答案｜理由",build_payload(b"abc","model",True)["messages"][0]["content"])
        self.assertNotIn("答案｜理由",build_payload(b"abc","model")["messages"][0]["content"])
    def test_parse(self):
        self.assertEqual(parse_answer({"choices":[{"message":{"content":" A、C\n"}}]}),"A、C")
        with self.assertRaises(ValueError):parse_answer({"choices":[]})
    @patch("vision.urllib.request.build_opener")
    def test_request(self,opener):
        client=opener.return_value
        client.open.return_value.__enter__.return_value.read.return_value=json.dumps({"choices":[{"message":{"content":"C"}}]}).encode()
        self.assertEqual(ask(b"abc","https://example.com/v1","model","test-key"),"C")
        req=client.open.call_args.args[0]
        self.assertEqual(req.get_header("Authorization"),"Bearer test-key")
if __name__=="__main__":unittest.main()
