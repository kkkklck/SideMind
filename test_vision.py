import unittest
from unittest.mock import patch
import json
from vision import endpoint,build_payload,parse_answer,ask,split_result
class TestVision(unittest.TestCase):
    def test_endpoint(self):
        self.assertEqual(endpoint("https://example.com/v1/"),"https://example.com/v1/chat/completions")
        self.assertEqual(endpoint("http://127.0.0.1:11434/v1"),"http://127.0.0.1:11434/v1/chat/completions")
        with self.assertRaises(ValueError):endpoint("http://example.com/v1")
    def test_payload(self):
        p=build_payload(b"abc","model")
        self.assertEqual(p["messages"][1]["content"][1]["image_url"]["url"],"data:image/png;base64,YWJj")
    def test_reason_prompt(self):
        self.assertIn("｜",build_payload(b"abc","model",True)["messages"][0]["content"])
        self.assertNotIn("｜",build_payload(b"abc","model")["messages"][0]["content"])
    def test_detail_prompt(self):
        p=build_payload(b"abc","model",detail=True)["messages"][0]["content"]
        self.assertIn("三段",p)
        self.assertIn("100到200",p)
        long="A｜理由｜"+"步"*400
        self.assertEqual(len(parse_answer({"choices":[{"message":{"content":long}}]},900)),len(long))
        self.assertEqual(len(parse_answer({"choices":[{"message":{"content":long}}]})),180)
    def test_split_result(self):
        cases={
            "B｜叶绿体特有｜①看条件②判断":("B","叶绿体特有","①看条件②判断"),
            "答案｜B｜详解：①关键条件是动物细胞不具有":("B","","①关键条件是动物细胞不具有"),
            "答案：B｜理由：叶绿体｜详解：①甲②乙":("B","叶绿体","①甲②乙"),
            "答案｜理由｜详解 B｜叶绿体｜①甲":("B","叶绿体","①甲"),
            # seen on the real device (photo, 2026-11-25)
            "答案｜C；理由｜生物圈包含所有生态系统；详解：①关键条件是“地球上最大”；②知识点：生物圈是最高级单位":
                ("C","生物圈包含所有生态系统","①关键条件是“地球上最大”；②知识点：生物圈是最高级单位"),
            "B｜①③正确｜①题干要求选正确组合②逐项判断":("B","①③正确","①题干要求选正确组合②逐项判断"),
            "①③｜两项都对":("①③","两项都对",""),
            "C":("C","",""),
            "A、C｜双层膜":("A、C","双层膜",""),
            "1.C；2.错误；3.A、D":("1.C；2.错误；3.A、D","",""),
            "B｜理由是叶绿体特有":("B","理由是叶绿体特有",""),
        }
        for raw,want in cases.items():
            self.assertEqual(split_result(raw),want,raw)
    def test_prompt_has_no_labels_to_echo(self):
        for p in (build_payload(b"x","m",detail=True),build_payload(b"x","m",reason=True)):
            self.assertNotIn("答案｜理由",p["messages"][0]["content"])
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
