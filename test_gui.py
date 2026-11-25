import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import unittest
import uuid
from PySide6.QtCore import Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from main import Bar,encode_image,PROVIDERS,DISPLAY_DEFAULTS,Settings,create_restart_server
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
        self.assertIn("参与细胞呼吸",bar.full)
        im=bar.grab().toImage()
        self.assertLessEqual(im.pixelColor(im.width()-1,im.height()-1).alpha(),1)
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
        self.assertEqual(bar.full,"")
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
    def test_detail_card(self):
        import ui_kit
        self.assertEqual(ui_kit.steps("①甲。②乙。③丙"),"①甲。\n②乙。\n③丙")
        bar=Bar()
        bar.place(self.app.primaryScreen())
        bar.set_state(True)
        bar.set_result("B",elapsed=1.2)
        self.assertFalse(bar.has_card())
        bar.apply_style(DISPLAY_DEFAULTS | {"show_detail":True})
        bar.set_result("B、D","双层膜",1.2,"①看条件。②用知识点。③得结论")
        self.assertTrue(bar.has_card())
        bar.show_card()
        self.assertTrue(bar.card.isVisible())
        self.assertIn("②用知识点",bar.card.text())
        self.assertLess(bar.card.geometry().bottom(),bar.geometry().top()+bar.card.M)
        long="①"+"很长的解析文字"*12+"②"+"继续"*30+"③"+"结论"*20
        bar.set_result("B","叶绿体",1.0,long)
        self.app.processEvents()
        screen=self.app.primaryScreen().availableGeometry().united(bar.geometry())
        self.assertLessEqual(bar.card.geometry().bottom()-bar.card.M,bar.geometry().top())
        self.assertGreaterEqual(bar.card.geometry().top()+bar.card.M,screen.top())
        self.assertGreater(bar.card.height(),150)
        bar.pinned=True
        bar.hide_card()
        self.assertTrue(bar.card.isVisible())
        bar.set_notice("等待截图")
        self.assertFalse(bar.card.isVisible())
        self.assertFalse(bar.pinned)
        bar.apply_style(DISPLAY_DEFAULTS|{"show_detail":False})
        bar.set_result("B","",None,"①详解")
        self.assertFalse(bar.has_card())
        bar.close()
    def test_detail_default_and_plain_text(self):
        import ui_kit
        self.assertFalse(DISPLAY_DEFAULTS["show_detail"])
        bar=Bar()
        bar.set_result("B",detail="①说明")
        self.assertFalse(bar.has_card())
        bar.apply_style(DISPLAY_DEFAULTS | {"show_detail":True})
        self.assertTrue(bar.has_card())
        card=ui_kit.DetailCard(ui_kit.theme())
        card.set_content("<b>B</b>","<img src='https://example.invalid/image.png'>","①<em>text</em>","0.8s")
        for label in (card.answer,card.reason,card.meta,card.detail_v.itemAt(0).widget()):
            self.assertEqual(label.textFormat(),Qt.TextFormat.PlainText)
        self.assertEqual(card.answer.text(),"<b>B</b>")
        card.close()
        bar.close()

    def test_restart_server_user_access(self):
        name="SideMind-test-"+uuid.uuid4().hex
        server=create_restart_server(name)
        self.assertIsNotNone(server)
        client=QLocalSocket()
        try:
            self.assertTrue(server.isListening())
            self.assertEqual(server.socketOptions(),QLocalServer.SocketOption.UserAccessOption)
            client.connectToServer(name)
            self.assertTrue(client.waitForConnected(1000))
        finally:
            client.abort()
            server.close()
            QLocalServer.removeServer(name)

    def test_dpapi(self):
        token="fake-test-token"
        encrypted=protect(token)
        self.assertNotEqual(encrypted,token)
        self.assertEqual(unprotect(encrypted),token)
    def test_presets(self):
        self.assertEqual(PROVIDERS["deepseek"][2],"deepseek-flash")
        self.assertEqual(PROVIDERS["qwen"][2],"qwen3-vl-plus")
