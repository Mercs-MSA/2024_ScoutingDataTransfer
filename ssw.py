from PySide6.QtWidgets import QStackedWidget
from PySide6.QtCore import QPoint, QEasingCurve, Qt, QParallelAnimationGroup, QPropertyAnimation, QAbstractAnimation

CURRENT_DIRECTION = 0


class SlidingStackedWidget(QStackedWidget):
    def __init__(self, parent=None, anim=QEasingCurve.Type.OutSine, speed=300):
        super(SlidingStackedWidget, self).__init__(parent)

        self.m_animation_type = anim
        self.m_direction = 0
        self.m_speed = speed
        self.m_now = 0
        self.m_next = 0
        self.m_wrap = False
        self.m_pnow = QPoint(0, 0)
        self.m_active = False

    def getDirection(self):
        return self.m_direction

    def setDirection(self, direction):
        self.m_direction = direction

    def setSpeed(self, speed):
        self.m_speed = speed

    def getAnimation(self):
        return self.m_animation_type

    def setAnimation(self, animationtype):
        self.m_animation_type = animationtype

    def setWrap(self, wrap):
        self.m_wrap = wrap

    def slideInPrev(self):
        now = self.currentIndex()
        if self.m_wrap or now > 0:
            self.slideInIdx(now - 1)

    def slideInNext(self):
        now = self.currentIndex()
        if self.m_wrap or now < (self.count() - 1):
            self.slideInIdx(now + 1)

    def slideInIdx(self, idx):
        if idx > (self.count() - 1):
            idx = idx % self.count()
        elif idx < 0:
            idx = (idx + self.count()) % self.count()
        self.slideInWgt(self.widget(idx))

    def slideInWgt(self, newwidget):
        if self.m_active:
            return

        self.m_active = True

        _now = self.currentIndex()
        _next = self.indexOf(newwidget)

        if _now == _next:
            self.m_active = False
            return

        offset_x, offsety_y = self.frameRect().width(), self.frameRect().height()
        self.widget(_next).setGeometry(self.frameRect())

        # noinspection PyUnresolvedReferences
        if not self.m_direction == Qt.Axis.XAxis:
            if _now < _next:
                offset_x, offsety_y = 0, -offsety_y
            else:
                offset_x = 0
        else:
            if _now < _next:
                offset_x, offsety_y = -offset_x, 0
            else:
                offsety_y = 0

        pnext = self.widget(_next).pos()
        pnow = self.widget(_now).pos()
        self.m_pnow = pnow

        offset = QPoint(offset_x, offsety_y)
        self.widget(_next).move(pnext - offset)
        self.widget(_next).show()
        self.widget(_next).raise_()

        # noinspection PyArgumentList
        anim_group = QParallelAnimationGroup(self, finished=self.animationDoneSlot)

        for index, start, end in zip(
            (_now, _next), (pnow, pnext - offset), (pnow + offset, pnext)
        ):
            # noinspection PyArgumentList
            animation = QPropertyAnimation(
                self.widget(index),
                b"pos",
                duration=self.m_speed,
                easingCurve=self.m_animation_type,
                startValue=start,
                endValue=end,
            )
            anim_group.addAnimation(animation)

        self.m_next = _next
        self.m_now = _now
        self.m_active = True
        anim_group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def animationDoneSlot(self):
        self.setCurrentIndex(self.m_next)
        self.widget(self.m_now).hide()
        self.widget(self.m_now).move(self.m_pnow)
        self.m_active = False