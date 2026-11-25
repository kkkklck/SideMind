"""SideMind UI kit — small, quiet controls for the settings flyout (no dependency on main)."""
import winreg
from PySide6.QtCore import Qt,Signal,Property,QPropertyAnimation,QEasingCurve,QRectF,QPointF,QSize,QTimer,QRect
from PySide6.QtGui import QPainter,QColor,QFont,QPainterPath,QPen,QFontMetrics
from PySide6.QtWidgets import QAbstractButton,QWidget,QComboBox,QListView

FAMILIES=["Segoe UI Variable Text","Segoe UI","Microsoft YaHei UI"]

def apps_dark():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return not bool(winreg.QueryValueEx(k,"AppsUseLightTheme")[0])
    except OSError:return False

LIGHT=dict(dark=False,bg="#FAFAFA",text="#1D1D1F",sub="#6E6E73",line="#E8E8EA",field="#FFFFFF",border="#D8D8DC",
           accent="#007AFF",off="#D4D4D8",red="#D70015",hover="#EFEFF1",shadow=QColor(0,0,0,38))
DARK=dict(dark=True,bg="#262628",text="#EDEDEF",sub="#98989D",line="#38383A",field="#1E1E20",border="#46464A",
          accent="#0A84FF",off="#4A4A4E",red="#FF6961",hover="#323235",shadow=QColor(0,0,0,120))

def theme(dark=None):
    return DARK if (apps_dark() if dark is None else dark) else LIGHT

def font(px,weight=QFont.Weight.Normal):
    f=QFont();f.setFamilies(FAMILIES);f.setPixelSize(px);f.setWeight(weight)
    return f

class Switch(QAbstractButton):
    """Small toggle; QCheckBox-compatible API."""
    def __init__(self,t,parent=None):
        super().__init__(parent)
        self.t=t;self._p=0.0
        self.setCheckable(True);self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus);self.setFixedSize(32,18)
        self.anim=QPropertyAnimation(self,b"progress",self)
        self.anim.setDuration(140);self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._move)
    def _get(self):return self._p
    def _set(self,v):self._p=v;self.update()
    progress=Property(float,_get,_set)
    def _move(self,on):
        if not self.isVisible():self._set(1.0 if on else 0.0);return
        self.anim.stop();self.anim.setStartValue(self._p);self.anim.setEndValue(1.0 if on else 0.0);self.anim.start()
    def sizeHint(self):return QSize(32,18)
    def paintEvent(self,_):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        a,b=QColor(self.t["off"]),QColor(self.t["accent"])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(*(round(x+(y-x)*self._p) for x,y in zip(a.getRgb(),b.getRgb()))))
        p.drawRoundedRect(r,r.height()/2,r.height()/2)
        d=r.height()-4;x=r.left()+2+(r.width()-4-d)*self._p
        p.setBrush(QColor("#FFFFFF"));p.drawEllipse(QRectF(x,r.top()+2,d,d))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(b,1.5));p.drawRoundedRect(r,r.height()/2,r.height()/2)

class Check(QAbstractButton):
    """Compact checkbox: 13px rounded box + label."""
    def __init__(self,text,t,parent=None):
        super().__init__(parent)
        self.t=t;self.setText(text);self.setCheckable(True);self.setFont(font(12))
        self.setCursor(Qt.CursorShape.PointingHandCursor);self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    def sizeHint(self):
        return QSize(14+6+QFontMetrics(self.font()).horizontalAdvance(self.text())+2,20)
    def paintEvent(self,_):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        box=QRectF(.5,(self.height()-14)/2+.5,13,13)
        acc=QColor(self.t["accent"])
        if self.isChecked():
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(acc);p.drawRoundedRect(box,3.5,3.5)
            path=QPainterPath();path.moveTo(box.left()+3.2,box.center().y()+.2)
            path.lineTo(box.left()+5.6,box.center().y()+2.6);path.lineTo(box.right()-3,box.top()+3.8)
            p.setPen(QPen(QColor("#FFFFFF"),1.6,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path)
        else:
            p.setPen(QPen(QColor(self.t["border"]),1));p.setBrush(QColor(self.t["field"]));p.drawRoundedRect(box,3.5,3.5)
        if self.hasFocus():
            p.setPen(QPen(acc,1.2));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRoundedRect(box.adjusted(-1.5,-1.5,1.5,1.5),4.5,4.5)
        p.setPen(QColor(self.t["text"]));p.setFont(self.font())
        p.drawText(QRectF(20,0,self.width()-20,self.height()),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,self.text())

class Stepper(QWidget):
    """[ − value + ] with QSpinBox-like API (value / setValue / setRange / valueChanged)."""
    valueChanged=Signal(int)
    def __init__(self,t,step=1,parent=None):
        super().__init__(parent)
        self.t=t;self.lo,self.hi,self.v,self.step=0,99,0,step
        self.setFixedSize(84,24);self.setFont(font(12));self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.repeat=QTimer(self);self.repeat.timeout.connect(self._tick);self.dir=0
    def setRange(self,lo,hi):self.lo,self.hi=lo,hi;self.setValue(self.v)
    def setSingleStep(self,s):self.step=s
    def value(self):return self.v
    def setValue(self,v):
        v=max(self.lo,min(self.hi,int(v)))
        if v!=self.v:self.v=v;self.update();self.valueChanged.emit(v)
    def _tick(self):
        self.repeat.setInterval(60);self.setValue(self.v+self.dir*self.step)
    def mousePressEvent(self,e):
        x=e.position().x()
        self.dir=-1 if x<24 else 1 if x>self.width()-24 else 0
        if self.dir:self._tick();self.repeat.start(380)
    def mouseReleaseEvent(self,_):self.repeat.stop();self.dir=0
    def wheelEvent(self,e):self.setValue(self.v+(self.step if e.angleDelta().y()>0 else -self.step))
    def keyPressEvent(self,e):
        k=e.key()
        if k in (Qt.Key.Key_Up,Qt.Key.Key_Right):self.setValue(self.v+self.step)
        elif k in (Qt.Key.Key_Down,Qt.Key.Key_Left):self.setValue(self.v-self.step)
        else:super().keyPressEvent(e)
    def paintEvent(self,_):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        p.setPen(QPen(QColor(self.t["accent"] if self.hasFocus() else self.t["border"]),1));p.setBrush(QColor(self.t["field"]))
        p.drawRoundedRect(r,6,6)
        p.setPen(QPen(QColor(self.t["line"]),1))
        for x in (24.5,self.width()-24.5):p.drawLine(QPointF(x,5),QPointF(x,self.height()-5))
        cy=self.height()/2
        for x,plus,enabled in ((12,False,self.v>self.lo),(self.width()-12,True,self.v<self.hi)):
            p.setPen(QPen(QColor(self.t["text"] if enabled else self.t["off"]),1.3,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(x-3.5,cy),QPointF(x+3.5,cy))
            if plus:p.drawLine(QPointF(x,cy-3.5),QPointF(x,cy+3.5))
        p.setPen(QColor(self.t["text"]));p.setFont(self.font())
        p.drawText(QRectF(24,0,self.width()-48,self.height()),Qt.AlignmentFlag.AlignCenter,str(self.v))

class Combo(QComboBox):
    """QComboBox with a flat field and a drawn chevron."""
    def __init__(self,t,parent=None):
        super().__init__(parent)
        self.t=t;self.setView(QListView());self.setFont(font(12))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def paintEvent(self,e):
        super().paintEvent(e)
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(self.t["sub"]),1.3,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        x,y=self.width()-13,self.height()/2
        p.drawPolyline([QPointF(x-3.5,y-1.5),QPointF(x,y+2),QPointF(x+3.5,y-1.5)])

def qss(t):
    return f"""
    QLabel {{ background:transparent; color:{t['text']}; }}
    QLabel#sub {{ color:{t['sub']}; }}
    QLabel#err {{ color:{t['red']}; }}
    QFrame#line {{ background:{t['line']}; border:none; }}
    QLineEdit, QComboBox {{ background:{t['field']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:6px;
        padding:0 8px; min-height:22px; max-height:22px; font-size:12px; selection-background-color:{t['accent']}; }}
    QLineEdit:focus, QComboBox:focus {{ border:1px solid {t['accent']}; }}
    QComboBox::drop-down {{ border:none; width:22px; }}
    QComboBox::down-arrow {{ image:none; }}
    QComboBox QAbstractItemView {{ background:{t['field']}; color:{t['text']}; border:1px solid {t['border']};
        outline:0; padding:3px; selection-background-color:{t['accent']}; selection-color:white; }}
    QComboBox QAbstractItemView::item {{ min-height:22px; padding:0 6px; border-radius:4px; }}
    QPushButton {{ border-radius:6px; min-height:24px; max-height:24px; padding:0 12px; font-size:12px;
        background:{t['field']}; color:{t['text']}; border:1px solid {t['border']}; }}
    QPushButton:hover {{ background:{t['hover']}; }}
    QPushButton#primary {{ background:{t['accent']}; color:white; border:1px solid {t['accent']}; }}
    QPushButton#primary:hover {{ background:{t['accent']}; border-color:{t['accent']}; }}
    QPushButton#flat {{ background:transparent; border:none; color:{t['sub']}; padding:0 2px; }}
    QPushButton#flat:hover {{ color:{t['red']}; }}
    QPushButton#reveal {{ background:transparent; border:none; color:{t['sub']}; padding:0 2px; }}
    QPushButton#reveal:hover {{ color:{t['accent']}; }}
    """

def steps(text):
    """Put each ①②③… step on its own line."""
    out=text.strip()
    for ch in "②③④⑤⑥⑦⑧⑨⑩":out=out.replace(ch,"\n"+ch)
    return "\n".join(s.strip() for s in out.split("\n") if s.strip())

class DetailCard(QWidget):
    """Quiet card shown above the taskbar bar on hover: answer, short reason, step-by-step explanation."""
    M=10;W=340
    def __init__(self,t):
        from PySide6.QtWidgets import QLabel,QVBoxLayout,QHBoxLayout,QFrame
        super().__init__(None,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.t=t
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(self.W+2*self.M)
        v=QVBoxLayout(self);v.setContentsMargins(self.M+14,self.M+11,self.M+14,self.M+12);v.setSpacing(4)
        top=QHBoxLayout();top.setSpacing(8)
        self.answer=QLabel();self.answer.setFont(font(15,QFont.Weight.DemiBold));self.answer.setWordWrap(True)
        self.meta=QLabel();self.meta.setFont(font(11))
        top.addWidget(self.answer,1);top.addWidget(self.meta,0,Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignRight)
        v.addLayout(top)
        self.reason=QLabel();self.reason.setFont(font(12));self.reason.setWordWrap(True)
        v.addWidget(self.reason)
        self.rule=QFrame();self.rule.setFixedHeight(1)
        v.addSpacing(4);v.addWidget(self.rule);v.addSpacing(4)
        self.detail=QWidget();self.detail_v=QVBoxLayout(self.detail)
        self.detail_v.setContentsMargins(0,0,0,0);self.detail_v.setSpacing(6)
        self.detail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        v.addWidget(self.detail)
        for w in (self.answer,self.meta,self.reason):
            w.setTextFormat(Qt.TextFormat.PlainText)
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.fade=QPropertyAnimation(self,b"windowOpacity",self);self.fade.setDuration(110)
        self.anchor=None  # (left x, bottom y, screen rect): the card grows upward from here
        self.apply_theme(t)
    def text(self):
        return "\n".join(self.detail_v.itemAt(i).widget().text() for i in range(self.detail_v.count()))
    def apply_theme(self,t):
        self.t=t
        self.answer.setStyleSheet(f"color:{t['text']};background:transparent;")
        self.detail.setStyleSheet(f"QLabel{{color:{t['text']};background:transparent;}}")
        for w in (self.meta,self.reason):w.setStyleSheet(f"color:{t['sub']};background:transparent;")
        self.rule.setStyleSheet(f"background:{t['line']};border:none;")
        self.update()
    def set_content(self,answer,reason="",detail="",meta="",error=False):
        from PySide6.QtWidgets import QLabel
        self.answer.setText(answer)
        self.answer.setStyleSheet(f"color:{self.t['red'] if error else self.t['text']};background:transparent;")
        self.meta.setText(meta);self.meta.setVisible(bool(meta))
        self.reason.setText(reason);self.reason.setVisible(bool(reason))
        while self.detail_v.count():
            w=self.detail_v.takeAt(0).widget()
            if w:w.hide();w.deleteLater()
        lines=steps(detail).split("\n") if detail else []
        for s in lines:
            l=QLabel(s,self.detail);l.setFont(font(12));l.setWordWrap(True);l.setTextFormat(Qt.TextFormat.PlainText)
            self.detail_v.addWidget(l);l.show()  # show now so the layout counts it when measuring
        self.detail.setVisible(bool(lines));self.rule.setVisible(bool(lines))
        self.fit();self.reposition()
        QTimer.singleShot(0,lambda:(self.fit(),self.reposition()))  # re-measure once wrapping has settled
    def fit(self):
        """Exact height for the fixed width (word-wrapped labels included)."""
        lay=self.layout();lay.activate()
        h=lay.totalHeightForWidth(self.width()) if lay.hasHeightForWidth() else lay.totalSizeHint().height()
        if self.anchor:h=min(h,self.anchor[1]-self.anchor[2].top()+self.M)
        self.setFixedHeight(max(h,40))
    def reposition(self):
        if not self.anchor:return
        x,bottom,a=self.anchor
        x=max(a.left()+2-self.M,min(x,a.right()-self.width()+self.M))
        self.move(x,max(a.top()-self.M,bottom-self.height()))
    def resizeEvent(self,e):
        super().resizeEvent(e);self.reposition()
    def show_above(self,rect,screen):
        """rect: global geometry of the bar. The card's visible bottom sits 6px above the bar."""
        self.anchor=(rect.left()-self.M,rect.top()-6+self.M,screen.availableGeometry().united(QRect(rect)))
        self.fit();self.reposition()
        if not self.isVisible():
            self.setWindowOpacity(0.0);self.show()
            self.fade.stop();self.fade.setStartValue(0.0);self.fade.setEndValue(1.0);self.fade.start()
            QTimer.singleShot(0,lambda:(self.fit(),self.reposition()))
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
