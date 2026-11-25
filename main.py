"""SideMind v0.3.1 — minimal, visible taskbar assistant with opt-in clipboard images."""
import ctypes
from ctypes import wintypes
import hashlib
import os
import sys
import time
import winreg
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import Qt,QTimer,QPoint,QRectF,QPropertyAnimation,QParallelAnimationGroup,QEasingCurve,QSettings,QBuffer,QIODevice,Signal,QObject,QAbstractNativeEventFilter,QLockFile,QStandardPaths
from PySide6.QtGui import QImage,QFont,QFontMetrics,QPainter,QColor,QPen
from PySide6.QtWidgets import (QApplication,QWidget,QLabel,QHBoxLayout,QDialog,QLineEdit,QMessageBox,QPushButton,QVBoxLayout,QGridLayout,QLayout,QFrame)
from vision import ask,endpoint
import ui_kit as ui
from secrets_win import protect,unprotect

PROVIDERS={
    "deepseek":("DeepSeek","https://api.deepseek.com","deepseek-flash","DEEPSEEK_API_KEY"),
    "qwen":("千问 · 北京","https://dashscope.aliyuncs.com/compatible-mode/v1","qwen3-vl-plus","DASHSCOPE_API_KEY"),
    "qwen-intl":("千问 · 新加坡","https://dashscope-intl.aliyuncs.com/compatible-mode/v1","qwen3-vl-plus","DASHSCOPE_API_KEY"),
    "custom":("自定义","https://api.openai.com/v1","gpt-4o-mini","SIDEMIND_API_KEY"),
}
FLAGS=Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus

class Hotkey(QAbstractNativeEventFilter):
    def __init__(self,settings,toggle):
        super().__init__()
        self.callbacks={0x534D:settings,0x534E:toggle}
        self.user32=ctypes.windll.user32
        self.registered={i for i,k in [(0x534D,"1"),(0x534E,"2")] if self.user32.RegisterHotKey(None,i,0x4006,ord(k))}
    def nativeEventFilter(self,eventType,message):
        if bytes(eventType) in (b"windows_generic_MSG",b"windows_dispatcher_MSG"):
            msg=wintypes.MSG.from_address(int(message))
            if msg.message==0x0312 and msg.wParam in self.registered:
                QTimer.singleShot(0,self.callbacks[msg.wParam])
                return True,0
        return False,0
    def close(self):
        for i in self.registered:self.user32.UnregisterHotKey(None,i)
        self.registered.clear()

def encode_image(image):
    if image.isNull():return None
    if max(image.width(),image.height())>2200:
        image=image.scaled(2200,2200,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
    buf=QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    return bytes(buf.data()) if image.save(buf,"PNG") else None

DISPLAY_DEFAULTS={"show_status":True,"show_time":True,"show_reason":False,"font_px":12,"width":350}

def taskbar_dark():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return not bool(winreg.QueryValueEx(k,"SystemUsesLightTheme")[0])
    except OSError:return True

def bar_size(screen,style):
    g=screen.geometry();a=screen.availableGeometry()
    h=g.bottom()-a.bottom()
    return min(style["width"],max(140,int(g.width()*.27))), min(44,h) if h>=20 else 32

def fit_text(text,metrics,width):
    return metrics.elidedText(text,Qt.TextElideMode.ElideRight,max(1,width))

class Settings(QDialog):
    """Small flyout that opens right above the taskbar bar. Display changes preview live on the real bar."""
    M=12  # transparent margin for the shadow
    W=292
    SAMPLE=("B、D","线粒体具有双层膜，参与细胞呼吸",0.8)
    def __init__(self,c):
        super().__init__(None,Qt.WindowType.Dialog|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint)
        self.c=c
        self.t=t=ui.theme()
        self.bar=getattr(c,"bar",None)
        self._shown=False
        self.setWindowTitle("SideMind")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(ui.qss(t))
        self.setFont(ui.font(12))

        self.active=ui.Switch(t);self.active.setChecked(c.active)
        self.provider=ui.Combo(t)
        for p,(name,*_) in PROVIDERS.items():self.provider.addItem(name,p)
        self.provider.setCurrentIndex(max(0,self.provider.findData(c.provider)))
        self.base=QLineEdit()
        self.model=QLineEdit()
        self.key=QLineEdit();self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.demo=ui.Check("演示模式（不联网）",t);self.demo.setChecked(c.demo)
        self.show_status=ui.Check("状态",t);self.show_time=ui.Check("耗时",t);self.show_reason=ui.Check("原因",t)
        for k in ("show_status","show_time","show_reason"):getattr(self,k).setChecked(c.display[k])
        self.font_px=ui.Stepper(t);self.font_px.setRange(1,18);self.font_px.setValue(c.display["font_px"])
        self.width=ui.Stepper(t,10);self.width.setRange(180,440);self.width.setValue(c.display["width"])

        def name(text):
            l=QLabel(text);l.setObjectName("sub");l.setFixedWidth(48);return l
        def line():
            f=QFrame();f.setObjectName("line");f.setFixedHeight(1);return f

        v=QVBoxLayout(self)
        v.setContentsMargins(self.M+14,self.M+12,self.M+14,self.M+12)
        v.setSpacing(8)

        head=QHBoxLayout();head.setSpacing(8)
        title=QLabel("剪贴板图片自动问答");title.setFont(ui.font(13,QFont.Weight.DemiBold))
        head.addWidget(title,1);head.addWidget(self.active)
        v.addLayout(head)
        hint=QLabel("开启后，新复制的任何图片都会发给服务商");hint.setObjectName("sub");hint.setFont(ui.font(11))
        v.addWidget(hint)
        v.addSpacing(2);v.addWidget(line());v.addSpacing(2)

        g=QGridLayout();g.setHorizontalSpacing(8);g.setVerticalSpacing(6)
        self.reveal=QPushButton("显示");self.reveal.setObjectName("reveal");self.reveal.setAutoDefault(False)
        self.reveal.setCursor(Qt.CursorShape.PointingHandCursor);self.reveal.clicked.connect(self.toggle_key)
        keybox=QHBoxLayout();keybox.setSpacing(4);keybox.addWidget(self.key,1);keybox.addWidget(self.reveal)
        self.base_label=name("地址")
        rows=[(name("服务商"),self.provider),(self.base_label,self.base),(name("模型"),self.model),(name("Key"),keybox)]
        for i,(l,w) in enumerate(rows):
            g.addWidget(l,i,0)
            (g.addLayout if isinstance(w,QHBoxLayout) else g.addWidget)(w,i,1)
        g.addWidget(self.demo,len(rows),1)
        v.addLayout(g)
        v.addSpacing(2);v.addWidget(line());v.addSpacing(2)

        d=QGridLayout();d.setHorizontalSpacing(8);d.setVerticalSpacing(8)
        checks=QHBoxLayout();checks.setSpacing(14)
        for k in ("show_status","show_time","show_reason"):checks.addWidget(getattr(self,k))
        checks.addStretch()
        d.addWidget(name("显示"),0,0);d.addLayout(checks,0,1,1,3)
        d.addWidget(name("字号"),1,0);d.addWidget(self.font_px,1,1)
        wl=QLabel("宽度");wl.setObjectName("sub")
        d.addWidget(wl,1,2,Qt.AlignmentFlag.AlignRight);d.addWidget(self.width,1,3)
        d.setColumnStretch(1,1)
        v.addLayout(d)

        self.error=QLabel();self.error.setObjectName("err");self.error.setWordWrap(True);self.error.hide()
        v.addWidget(self.error)
        v.addSpacing(4)

        ft=QHBoxLayout();ft.setSpacing(6)
        quit_button=QPushButton("退出");quit_button.setObjectName("flat");quit_button.setAutoDefault(False)
        quit_button.setCursor(Qt.CursorShape.PointingHandCursor);quit_button.clicked.connect(self.quit_app)
        cancel=QPushButton("取消");cancel.setAutoDefault(False);cancel.clicked.connect(self.reject)
        save=QPushButton("保存");save.setObjectName("primary");save.setDefault(True);save.clicked.connect(self.validate)
        ft.addWidget(quit_button);ft.addStretch();ft.addWidget(cancel);ft.addWidget(save)
        v.addLayout(ft)

        for k in ("show_status","show_time","show_reason"):getattr(self,k).toggled.connect(self.update_preview)
        self.font_px.valueChanged.connect(self.update_preview)
        self.width.valueChanged.connect(self.update_preview)
        self.provider.currentIndexChanged.connect(self.load)
        for e in (self.base,self.model,self.key):e.textEdited.connect(lambda *_:self.show_error(""))
        self.setFixedWidth(self.W+2*self.M)
        self.load()
        self.update_preview()

    def display_values(self):
        return {k:getattr(self,k).isChecked() for k in ("show_status","show_time","show_reason")} | {"font_px":self.font_px.value(),"width":self.width.value()}
    def update_preview(self,*_):
        """Preview on the real taskbar bar; restored on cancel."""
        if self.bar is None:return
        self.bar.apply_style(self.display_values())
        if hasattr(self.c,"place"):self.c.place()
        self.bar.set_state(True,self.demo.isChecked())
        self.bar.set_result(*self.SAMPLE)
    def toggle_key(self):
        hidden=self.key.echoMode()==QLineEdit.EchoMode.Password
        self.key.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self.reveal.setText("隐藏" if hidden else "显示")
    def load(self,*_):
        provider=self.provider.currentData()
        base,model,key=self.c.profile(provider)
        self.base.setText(base);self.model.setText(model);self.key.setText(key)
        self.base.setCursorPosition(0)
        custom=provider=="custom"
        self.base.setVisible(custom);self.base_label.setVisible(custom)
        self.show_error("")
    def show_error(self,text):
        if self.error.text()==text:return
        self.error.setText(text);self.error.setVisible(bool(text));self.anchor()
    def validate(self):
        try:
            if not self.demo.isChecked():
                endpoint(self.base.text())
                if not self.model.text().strip():raise ValueError("请输入支持图片的模型")
                if self.active.isChecked() and not self.key.text().strip():raise ValueError("请输入 API Key")
            self.encrypted=protect(self.key.text().strip())
        except (ValueError,OSError) as e:
            if not self.base.isVisible() and "API 地址" in str(e):
                self.base.show();self.base_label.show()
            self.show_error(str(e));return
        self.accept()
    def reject(self):
        if self.bar is not None:
            self.bar.apply_style(self.c.display)
            if hasattr(self.c,"place"):self.c.place()
        super().reject()
    def quit_app(self):
        self.reject()
        self.c.app.quit()

    def anchor(self):
        """Sit just above the bottom-left of the work area, i.e. right above the taskbar bar."""
        if not self._shown:return
        self.adjustSize()
        a=self.c.app.primaryScreen().availableGeometry()
        self.move(a.left()+8-self.M,a.bottom()-7-self.size().height()+self.M)
    def showEvent(self,e):
        super().showEvent(e)
        if self._shown:return
        self._shown=True
        self.anchor()
        end=self.pos()
        self.move(end+QPoint(0,6));self.setWindowOpacity(0.0)
        self.intro=QParallelAnimationGroup(self)
        for prop,a,b in ((b"pos",end+QPoint(0,6),end),(b"windowOpacity",0.0,1.0)):
            an=QPropertyAnimation(self,prop,self);an.setStartValue(a);an.setEndValue(b)
            an.setDuration(140);an.setEasingCurve(QEasingCurve.Type.OutCubic);self.intro.addAnimation(an)
        self.intro.start()
        self.activateWindow();self.raise_()
    def paintEvent(self,_):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(self.rect()).adjusted(self.M,self.M,-self.M,-self.M)
        s=self.t["shadow"];p.setPen(Qt.PenStyle.NoPen)
        for i in range(self.M,0,-1):
            c=QColor(s);c.setAlpha(int(s.alpha()*(1-i/self.M)**2/4));p.setBrush(c)
            p.drawRoundedRect(r.adjusted(-i,-i+3,i,i+3),10+i,10+i)
        p.setBrush(QColor(self.t["bg"]))
        p.setPen(QPen(QColor(0,0,0,30) if not self.t["dark"] else QColor(255,255,255,26),1))
        p.drawRoundedRect(r.adjusted(.5,.5,-.5,-.5),10,10)


class Bar(QWidget):
    def __init__(self,preview=False):
        super().__init__(None,Qt.WindowType.Widget if preview else FLAGS)
        self.preview=preview
        if not preview:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("SideMind")
        self.style=DISPLAY_DEFAULTS.copy()
        self.active=False
        self.demo=False
        self.text="Ctrl+Shift+1 设置"
        self.is_notice=True
        self.reason_text=""
        self.elapsed=None
        self.error=False
        self.truncated=False
        self.layout_=QVBoxLayout(self)
        self.layout_.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.layout_.setContentsMargins(7,0,7,0)
        self.layout_.setSpacing(0)
        self.layout_.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        row=QHBoxLayout()
        row.setContentsMargins(0,0,0,0)
        row.setSpacing(7)
        self.indicator=QLabel()
        self.answer=QLabel()
        self.timer=QLabel()
        self.reason=QLabel()
        for label in (self.indicator,self.answer,self.timer,self.reason):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setMinimumWidth(0)
        row.addWidget(self.indicator)
        row.addWidget(self.answer)
        row.addWidget(self.timer)
        row.addStretch()
        self.layout_.addLayout(row)
        self.layout_.addWidget(self.reason)
        self.resize(350,40)
        self.apply_style(self.style)
    def apply_style(self,style):
        self.style=style.copy()
        self.render()
    def set_state(self,active,demo=False):
        self.active,self.demo=active,demo
        self.render()
    def set_notice(self,text):
        self.set_answer(text,notice=True)
    def set_answer(self,text,error=False,notice=False):
        self.is_notice=notice
        self.text,self.error=text,error
        self.reason_text=""
        self.elapsed=None
        self.render()
    def set_result(self,text,reason="",elapsed=None):
        self.is_notice=False
        self.text,self.reason_text,self.elapsed=text,reason,elapsed
        self.error=False
        self.render()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,"answer"):self.render()
    def render(self):
        dark=taskbar_dark()
        fg="#e7e7e7" if dark else "#171717"
        muted="#b8b8b8" if dark else "#505050"
        green="#a7f3d0" if dark else "#166534"
        warn="#fbbf24" if dark else "#9a3412"
        font=QFont("Microsoft YaHei UI")
        font.setPixelSize(self.style["font_px"])
        fm=QFontMetrics(font)
        for label in (self.indicator,self.answer,self.timer,self.reason):label.setFont(font)
        self.setStyleSheet("QWidget {background:"+("#1c1c1c" if dark else "#ececec")+";}" if self.preview else "QWidget {background:transparent;}")
        self.indicator.setStyleSheet("background:transparent;color:"+(green if self.active else muted))
        self.answer.setStyleSheet("background:transparent;color:"+(warn if self.error else fg))
        self.timer.setStyleSheet("background:transparent;color:"+muted)
        self.reason.setStyleSheet("background:transparent;color:"+muted)
        status="AI · 演示" if self.active and self.demo else "AI · 开启" if self.active else "AI · 暂停"
        status_visible=self.style["show_status"]
        shown_text="" if self.is_notice and not status_visible else self.text
        self.indicator.setText(status)
        self.indicator.setVisible(status_visible)
        elapsed=f"{self.elapsed:.1f}s" if self.elapsed is not None and self.style["show_time"] else ""
        self.timer.setText(elapsed)
        self.timer.setVisible(bool(elapsed))
        available=max(20,self.width()-14)
        answer_space=available-(fm.horizontalAdvance(status)+7 if status_visible else 0)-(fm.horizontalAdvance(elapsed)+7 if elapsed else 0)
        answer=fit_text(shown_text,fm,answer_space)
        self.answer.setText(answer)
        self.truncated=answer!=shown_text
        reason=self.reason_text if self.style["show_reason"] else ""
        two_lines=reason and 2*fm.height()<=self.height()
        self.reason.setVisible(bool(two_lines))
        if two_lines:
            short=fit_text(reason,fm,available)
            self.reason.setText(short)
            self.truncated|=short!=reason
        elif reason:
            combined=shown_text+" · "+reason
            self.answer.setText(fit_text(combined,fm,answer_space))
            self.truncated|=self.answer.text()!=combined
        full=" · ".join(x for x in (shown_text,reason,elapsed) if x)
        self.setToolTip(full)
    def place(self,screen):
        g=screen.geometry();a=screen.availableGeometry()
        taskbar_height=g.bottom()-a.bottom()
        width,height=bar_size(screen,self.style)
        self.setFixedSize(width,height)
        y=a.bottom()+1+(taskbar_height-height)//2 if taskbar_height>=20 else a.bottom()-height+1
        self.move(g.left()+7,y)
        if not self.isVisible():self.show()
        self.render()
        if QApplication.platformName() == 'windows':
            u=ctypes.windll.user32
            u.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
            u.SetWindowPos.restype=wintypes.BOOL
            u.SetWindowPos(int(self.winId()),wintypes.HWND(-1),0,0,0,0,0x0013)

class Bridge(QObject):
    result=Signal(int,str,bool,str,object)

class Controller:
    def __init__(self,app):
        self.app=app
        self.store=QSettings("SideMind","SideMind")
        self.display={k:self.store.value("v3/display/"+k,v,type=type(v)) for k,v in DISPLAY_DEFAULTS.items()}
        self.display["font_px"]=max(1,min(18,self.display["font_px"]))
        self.display["width"]=max(180,min(440,self.display["width"]))
        self.provider=self.store.value("v2/provider","deepseek")
        if self.provider not in PROVIDERS:self.provider="deepseek"
        self.demo=self.store.value("v2/demo",False,type=bool)
        self.active=self.store.value("v2/active",False,type=bool)
        self.base,self.model,self.key=self.profile(self.provider)
        if not self.key and not self.demo:self.active=False
        self.seq=0
        self.busy=False
        self.pending=None
        self.dialog=None
        self.last_digest=None
        self.last_time=0
        self.pool=ThreadPoolExecutor(max_workers=1)
        self.bridge=Bridge()
        self.bridge.result.connect(self.receive)
        self.bar=Bar()
        self.bar.apply_style(self.display)
        self.place()
        self.bar.set_state(self.active,self.demo)
        self.bar.set_notice("等待截图" if self.active else "Ctrl+Shift+1 设置")
        self.hotkey=Hotkey(self.settings,self.toggle)
        app.installNativeEventFilter(self.hotkey)
        app.aboutToQuit.connect(self.shutdown)
        self.clip=app.clipboard()
        self.debounce=QTimer()
        self.debounce.setSingleShot(True)
        self.debounce.timeout.connect(self.read_new_image)
        self.clip.dataChanged.connect(self.clip_changed)
        self.layout_timer=QTimer()
        self.layout_timer.timeout.connect(self.place)
        self.layout_timer.start(2000)
        if 0x534D not in self.hotkey.registered:
            QMessageBox.warning(None,"SideMind","Ctrl+Shift+1 被占用，设置将直接打开。")
            QTimer.singleShot(0,self.settings)
    def profile(self,provider):
        _,base,model,env=PROVIDERS[provider]
        pre="v2/profiles/"+provider+"/"
        base=self.store.value(pre+"base",base)
        model=self.store.value(pre+"model",model)
        try:key=unprotect(self.store.value(pre+"key",""))
        except Exception:key=""
        return base,model,key or os.environ.get(env,"")
    def place(self):
        self.bar.place(self.app.primaryScreen())
    def settings(self):
        if self.dialog is not None:return
        self.debounce.stop()
        self.pending=None
        self.seq+=1
        self.dialog=Settings(self)
        if self.dialog.exec()==QDialog.DialogCode.Accepted:
            d=self.dialog
            self.provider=d.provider.currentData()
            self.base,self.model,self.key=d.base.text().strip(),d.model.text().strip(),d.key.text().strip()
            self.demo=d.demo.isChecked()
            self.active=d.active.isChecked()
            pre="v2/profiles/"+self.provider+"/"
            for k,v in [(pre+"base",self.base),(pre+"model",self.model),(pre+"key",d.encrypted),("v2/provider",self.provider),("v2/demo",self.demo),("v2/active",self.active)]:self.store.setValue(k,v)
            self.display=d.display_values()
            for k,v in self.display.items():self.store.setValue("v3/display/"+k,v)
            self.store.sync()
            self.bar.apply_style(self.display)
            self.place()
        self.dialog=None
        self.bar.set_state(self.active,self.demo)
        self.bar.set_notice("等待截图" if self.active else "已暂停")
    def toggle(self):
        if self.dialog is not None:return
        if not self.active and not (self.key or self.demo):
            self.settings();return
        self.active=not self.active
        self.store.setValue("v2/active",self.active)
        self.store.sync()
        self.debounce.stop()
        self.pending=None
        self.seq+=1
        self.bar.set_state(self.active,self.demo)
        self.bar.set_notice("等待截图" if self.active else "已暂停")
    def clip_changed(self):
        if self.active and self.dialog is None:
            self.debounce.start(180)
    def read_new_image(self):
        if not self.active or self.dialog is not None:return
        mime=self.clip.mimeData()
        if mime is None or not mime.hasImage():return
        png=encode_image(self.clip.image())
        if not png:return
        digest=hashlib.sha256(png).digest()
        now=time.monotonic()
        if digest==self.last_digest and now-self.last_time<2:return
        self.last_digest,self.last_time=digest,now
        self.seq+=1
        if self.busy:
            self.pending=(self.seq,png)
            self.bar.set_notice("等待上一请求…")
        else:self.submit(self.seq,png)
    def submit(self,seq,png):
        self.busy=True
        self.bar.set_notice("演示中…" if self.demo else "AI 核对中…")
        if self.demo:
            QTimer.singleShot(350,lambda:self.receive(seq,"演示：C",False,"线粒体具有双层膜",0.35));return
        base,model,key=self.base,self.model,self.key
        reason_mode=self.display['show_reason']
        def worker():
            t=time.monotonic()
            try:
                result=ask(png,base,model,key,reason=reason_mode)
                answer,_,reason=result.partition("｜")
                self.bridge.result.emit(seq,answer.strip(),False,reason.strip(),time.monotonic()-t)
            except Exception as e:
                self.bridge.result.emit(seq,str(e) if isinstance(e,(ValueError,RuntimeError)) else "请求失败，请检查配置",True,"",None)
        self.pool.submit(worker)
    def receive(self,seq,text,error,reason="",elapsed=None):
        self.busy=False
        if seq==self.seq and self.active and self.dialog is None:
            if error:self.bar.set_answer(text,True)
            else:self.bar.set_result(text,reason,elapsed)
        pending=self.pending
        self.pending=None
        if pending and self.active and self.dialog is None:self.submit(*pending)
    def shutdown(self):
        self.active=False
        self.debounce.stop()
        self.pending=None
        self.hotkey.close()
        self.pool.shutdown(wait=False,cancel_futures=True)

def main():
    app=QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    lock=QLockFile(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)+"/SideMind-v2.lock")
    if not lock.tryLock(0):
        QMessageBox.information(None,"SideMind","SideMind 已运行，Ctrl+Shift+1 打开设置。")
        return 0
    c=Controller(app)
    return app.exec()
if __name__=="__main__":sys.exit(main())
