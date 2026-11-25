import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from main import Bar,encode_image,PROVIDERS,DISPLAY_DEFAULTS,Settings
from secrets_win import protect,unprotect

class TestGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def test_image(self):
        img=QImage(2500,1000,QImage.Format.Format_RGB32)
        img.fill(QColor("white"))
        out=QImage.fromData(encode_image(img))
        self.assertEqual((out.width(),out.height()),(2200,880))
        self.assertIsNone(encode_image(QImage()))
    def test_bar(self):
        bar=Bar()
        bar.place(self.app.primaryScreen())
        bar.set_state(True)
        bar.set_answer("A、C")
        self.assertEqual(bar.answer.text(),"A、C")
        self.assertEqual(bar.indicator.text(),"AI · 开启")
        bar.close()
    def test_display_options(self):
        bar=Bar()
        bar.resize(350,44)
        bar.show()
        bar.set_state(True)
        bar.apply_style(DISPLAY_DEFAULTS | {"show_status":False,"show_time":False,"show_reason":True})
        bar.set_result("B、D","线粒体具有双层膜",0.8)
        self.assertTrue(bar.indicator.isHidden())
        self.assertTrue(bar.timer.isHidden())
        self.assertFalse(bar.reason.isHidden())
        self.assertEqual(bar.answer.text(),"B、D")
        self.assertEqual(bar.reason.text(),"线粒体具有双层膜")
        self.assertTrue(bar.testAttribute(__import__("PySide6.QtCore",fromlist=["Qt"]).Qt.WidgetAttribute.WA_TranslucentBackground))
        bar.close()
    def test_narrow_and_transparent(self):
        bar=Bar()
        bar.setFixedSize(180,28)
        bar.show()
        bar.apply_style(DISPLAY_DEFAULTS | {"show_status":False,"show_time":False,"show_reason":True,"font_px":18})
        bar.set_result("B、D","线粒体具有双层膜，参与细胞呼吸",0.8)
        self.app.processEvents()
        self.assertEqual(bar.width(),180)
        self.assertTrue(bar.answer.text().startswith("B、D"))
        self.assertTrue(bar.truncated)
        self.assertIn("参与细胞呼吸",bar.toolTip())
        im=bar.grab().toImage()
        self.assertEqual(im.pixelColor(im.width()-1,im.height()-1).alpha(),0)
        bar.close()
    def test_preview(self):
        bar=Bar()
        class Fake:
            app=self.app
            provider="qwen"
            demo=False
            active=False
            display=DISPLAY_DEFAULTS.copy()
            def profile(self,p):return PROVIDERS[p][1],PROVIDERS[p][2],""
        f=Fake();f.bar=bar
        d=Settings(f)
        d.show()
        self.assertTrue(d.base.isHidden())
        d.show_reason.setChecked(True)
        d.show_status.setChecked(False)
        d.show_time.setChecked(False)
        self.assertEqual(bar.answer.text(),"B、D")
        self.assertTrue(bar.indicator.isHidden())
        self.assertFalse(bar.reason.isHidden() and "线粒体" not in bar.answer.text())
        d.font_px.setValue(30)
        self.assertEqual(d.display_values()["font_px"],18)
        d.provider.setCurrentIndex(d.provider.findData("custom"))
        self.assertFalse(d.base.isHidden())
        d.reject()
        self.assertEqual(bar.style,DISPLAY_DEFAULTS)
        bar.close()
    def test_idle_and_min_font(self):
        bar=Bar()
        bar.apply_style(DISPLAY_DEFAULTS | {"show_status":False,"show_time":False,"font_px":1})
        bar.set_state(True)
        bar.set_notice("等待截图")
        self.assertEqual(bar.answer.text(),"")
        self.assertEqual(bar.toolTip(),"")
        bar.set_notice("AI 核对中…")
        self.assertEqual(bar.answer.text(),"")
        bar.set_result("B")
        self.assertEqual(bar.answer.text(),"B")
        self.assertEqual(bar.answer.font().pixelSize(),1)
        bar.set_answer("API Key 无效",True)
        self.assertEqual(bar.answer.text(),"API Key 无效")
        bar.set_notice("已暂停")
        self.assertEqual(bar.answer.text(),"")
        bar.close()
    def test_dpapi(self):
        token="fake-test-token"
        encrypted=protect(token)
        self.assertNotEqual(encrypted,token)
        self.assertEqual(unprotect(encrypted),token)
    def test_presets(self):
        self.assertEqual(PROVIDERS["deepseek"][2],"deepseek-flash")
        self.assertEqual(PROVIDERS["qwen"][2],"qwen3-vl-plus")
