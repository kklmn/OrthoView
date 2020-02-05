# -*- coding: utf-8 -*-
"""
OrthoView
=========

OrthoView is a Qt widget for viewing a scene with a camera and converting the
image coordinates to orthogonal coordinates in a selected target plane. These
coordinates can later be used for commanding a shift of the plane by its local
XY movements. The widget is used to visually select a sample in a sample plate.

.. image:: _images/OrthoView_ani.gif
   :scale: 66 %

Dependencies
------------

matplotlib, cv2 (opencv-python), optionally taurus.

How to use
----------

Run it: `python OrthoView.py`. With the Perspective Rectangle button (the 1st
in the right group) define four points that form a rectangle in a plane. A blue
dot on the button shows the currently expected corner to define. Set X and Y
dimensions with the next two buttons. Define the local origin (beam position)
by the right mouse click. Check the resulting image orthogonality in the
expected plane by the last button. Also observe the mouse coordinates in the
target plane, as displayed above the image.

To use the motion functionality, set `isTest = False`, define your motions in
the top part of the module and use them in the method `moveToBeam()`.

"""

__author__ = "Konstantin Klementiev"
__versioninfo__ = (1, 0, 0)
__version__ = '.'.join(map(str, __versioninfo__))
__date__ = "05 Feb 2020"
__license__ = "MIT license"

import os
import sys
import numpy as np
import cv2
from matplotlib.figure import Figure

# =============================================================================
# select a qt source: from Taurus or Pyqt4 or PyQt5:
# =============================================================================

import taurus.external.qt.Qt as qt
import taurus.external.qt as qt0
import taurus.external.qt.QtCore as qtcore
import taurus.external.qt.QtWidgets as qtwidgets
if 'pyqt5' in qt0.API.lower():
    import matplotlib.backends.backend_qt5agg as mpl_qt
    PYQT5 = True
else:
    import matplotlib.backends.backend_qt4agg as mpl_qt
    PYQT5 = False

# from PyQt5 import QtGui as qtcore
# from PyQt5 import QtWidgets as qtwidgets
# from PyQt5 import Qt as qt
# import matplotlib.backends.backend_qt5agg as mpl_qt

# from PyQt4 import QtGui as qtcore
# import PyQt4.QtGui as qtwidgets
# from PyQt4 import Qt as qt
# import matplotlib.backends.backend_qt4agg as mpl_qt

# =============================================================================
# end select a qt source: from Taurus or Pyqt4 or PyQt5:
# =============================================================================

try:
    from ConfigParser import ConfigParser
except ImportError:
    from configparser import ConfigParser

isTest = True

if not isTest:
    from taurus import Device as DeviceProxy
#    from PyTango import DeviceProxy
    motorX = None  # DeviceProxy('mp_x')
    motorY = DeviceProxy('mp_y')

selfDir = os.path.dirname(__file__)
iniApp = (os.path.join(selfDir, 'OrthoView.ini'))
config = ConfigParser(
    dict(pos='[0, 0]', corners='[None]*4', scalex=0, scaley=0))
config.add_section('rectangle')
config.add_section('beam')
config.add_section('colors')
config.read(iniApp)


def write_config():
    with open(iniApp, 'w+') as cf:
        config.write(cf)


class MyToolBar(mpl_qt.NavigationToolbar2QT):
    def set_message(self, s):
        try:
            parent = self.parent()
        except TypeError:  # self.parent is not callable
            parent = self.parent

        try:
            sstr = s.split()
#            print(sstr, len(sstr))
            while len(sstr) > 5:  # when 'zoom rect' is present
                del sstr[0]
#            print(sstr)
            x, y = float(sstr[0][2:]), float(sstr[1][2:])
            if parent.canTransform():
                xC, yC = parent.beamPosRectified
                if not parent.buttonStraightRect.isChecked():
                    xP, yP = parent.transformPoint((x, y))
                    x0, y0 = (xP-xC)/parent.zoom, (yP-yC)/parent.zoom
                    s = u'image: x={0:.1f} px, y={1:.1f} px\nplate: '\
                        'x={2:.2f} mm, y={3:.2f} mm'.format(x, y, x0, y0)
                else:
                    x0, y0 = (x-xC)/parent.zoom, (y-yC)/parent.zoom
                    s = 'plate: x={0:.2f} mm, y={1:.2f} mm'.format(x0, y0)
            else:
                s = u'image: x={0:.1f}, y={1:.1f}'.format(x, y)
        except Exception as e:
            pass
#            print(e)

        if self.coordinates:
            self.locLabel.setText(s)


class MyMplCanvas(mpl_qt.FigureCanvasQTAgg):
    def __init__(self, parent=None):
        self.fig = Figure()
        self.fig.patch.set_facecolor('white')
        super(MyMplCanvas, self).__init__(self.fig)
        self.setParent(parent)
        self.updateGeometry()
        self.setupPlot()
        self.mpl_connect('button_press_event', self.onPress)
        self.img = None
        self.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        self.mouseClickPos = None
        self.beamPos = eval(config.get('beam', 'pos'))

        self.customContextMenuRequested.connect(self.viewMenu)
        self.menu = qt.QMenu()

        self.actionMove = self.menu.addAction(
            'move this point to beam', self.moveToBeam)

        self.actionDefineBeam = self.menu.addAction(
            'define beam position here', self.setBeamPosition)

        self.actionShowBeam = self.menu.addAction(
            'show beam position', self.showBeam)
        self.actionShowBeam.setCheckable(True)
        self.isBeamPositionVisible = True
        self.actionShowBeam.setChecked(self.isBeamPositionVisible)

        self.actionShowRect = self.menu.addAction(
            'show reference rectangle', self.showRect)
        self.actionShowRect.setCheckable(True)
        self.isRectVisible = True
        self.actionShowRect.setChecked(self.isRectVisible)

    def setupPlot(self):
        rect = [0., 0., 1., 1.]
        self.axes = self.fig.add_axes(rect)
        self.axes.xaxis.set_visible(False)
        self.axes.yaxis.set_visible(False)
        for spine in ['left', 'right', 'bottom', 'top']:
            self.axes.spines[spine].set_visible(False)
        self.axes.set_zorder(20)

    def imshow(self, img):
        if self.img is None:
            self.img = self.axes.imshow(img)
        else:
            self.img.set_data(img)
            self.img.set_extent(
                [-0.5, img.shape[1]-0.5, img.shape[0]-0.5, -0.5])
            self.axes.set_xlim((0, img.shape[1]))
            self.axes.set_ylim((img.shape[0], 0))
            self.toolbar.update()
        self.draw()

    def onPress(self, event):
        if (event.xdata is None) or (event.ydata is None):
            self.mouseClickPos = None
            return
        self.mouseClickPos = int(round(event.xdata)), int(round(event.ydata))
        if not self.parent().buttonBaseRect.isChecked():
            return
        self.parent().buttonBaseRect.setCorner(*self.mouseClickPos)

    def viewMenu(self, position):
        if self.mouseClickPos is None:
            return
        self.actionDefineBeam.setEnabled(
            not self.parent().buttonStraightRect.isChecked())
        self.actionMove.setEnabled(self.parent().canTransform())
        self.menu.exec_(self.mapToGlobal(position))
        self.parent().updateFrame()

    def setBeamPosition(self):
        if (self.beamPos[0] > 0) or (self.beamPos[1] > 0):
            msgBox = qt.QMessageBox()
            reply = msgBox.question(
                self, 'Confirm',
                'Do you really want to re-define beam position?',
                qt.QMessageBox.Yes | qt.QMessageBox.No, qt.QMessageBox.Yes)
            if reply == qt.QMessageBox.No:
                return
        self.beamPos[:] = self.mouseClickPos
        config.set('beam', 'pos', str(self.beamPos))
        write_config()
        self.parent().buttonStraightRect.update()

    def showBeam(self):
        self.isBeamPositionVisible = not self.isBeamPositionVisible

    def showRect(self):
        self.isRectVisible = not self.isRectVisible

    def moveToBeam(self):
        x, y = self.mouseClickPos
        parent = self.parent()
        xC, yC = parent.beamPosRectified
        if not parent.buttonStraightRect.isChecked():
            xP, yP = parent.transformPoint((x, y))
            x0, y0 = (xP-xC)/parent.zoom, (yP-yC)/parent.zoom
        else:
            x0, y0 = (x-xC)/parent.zoom, (y-yC)/parent.zoom

        if isTest:
            print(-x0, y0)
        else:
            if motorX is not None:
                try:
                    curX = motorX.read_attribute('position').value
                    motorX.write_attribute('position', curX-x0)
                except Exception as e:
                    lines = str(e).splitlines()
                    for line in reversed(lines):
                        if 'desc =' in line:
                            msgBox = qt.QMessageBox()
                            msgBox.critical(
                                self, 'Motion has failed', line.strip()[7:])
                            return
            if motorY is not None:
                curY = motorY.read_attribute('position').value
                motorY.write_attribute('position', curY+y0)


class PerspectiveRectButton(qt.QPushButton):
    prect = (qt.QPoint(12, 10), qt.QPoint(50, 8), qt.QPoint(47, 30),
             qt.QPoint(11, 26))

    def __init__(self, text='', parent=None):
        super(PerspectiveRectButton, self).__init__(text, parent)
        self.polygon = qt.QPolygonF()
        for pt in self.prect:
            self.polygon.append(pt)
        self.corners = [0] * 4
        self.currentDefCorner = -1
        self.wantVisibleCorners = True
        self.clicked.connect(self.clickedSlot)
        self.setCheckable(True)
        self.installEventFilter(self)
        self.setStyleSheet(
            "QPushButton:checked{background-color: deepskyblue;}"
            "QPushButton:pressed{background-color: deepskyblue;}")

    def clickedSlot(self):
        if self.isChecked():
            pos = qt.QCursor.pos()
            qt.QCursor.setPos(pos.x()-300, pos.y()+200)
            if None not in self.corners:
                self.currentDefCorner = 0
            else:
                self.currentDefCorner = self.corners.index(None)
        else:
            self.currentDefCorner = -1
        self.parent().plotCanvas.isRectVisible = True
        self.parent().plotCanvas.actionShowRect.setChecked(True)
        self.parent().updateFrame()
        self.update()

    def setCorner(self, xdata, ydata):
        self.corners[self.currentDefCorner] = int(xdata), int(ydata)
        self.currentDefCorner += 1
        if self.currentDefCorner > 3:
            self.currentDefCorner = 0
            srtPts = sorted(self.corners, key=lambda ls: ls[1])
            topPts, bottomPts = srtPts[:2], srtPts[2:]
            spt1, spt2 = sorted(topPts, key=lambda lst: lst[0])
            spt4, spt3 = sorted(bottomPts, key=lambda lst: lst[0])
            self.corners = [spt1, spt2, spt3, spt4]
            config.set('rectangle', 'corners', str(self.corners))
            write_config()
            self.setChecked(False)
            self.parent().buttonStraightRect.update()
        self.parent().updateFrame()
        self.update()

    def eventFilter(self, widget, event):
        if event.type() == qt.QEvent.KeyPress:
            key = event.key()
            if key == qt.Qt.Key_Escape:
                self.setChecked(False)
                self.clicked.emit(False)
        return super(PerspectiveRectButton, self).eventFilter(widget, event)

    def paintEvent(self, event):
        super(PerspectiveRectButton, self).paintEvent(event)
        if not self.wantVisibleCorners:
            return
        paint = qt.QPainter()
        paint.begin(self)
        paint.setRenderHint(qt.QPainter.Antialiasing)
#        paint.drawRect(event.rect())
        paint.drawPolygon(self.polygon)
        for ipt, (pt, corner) in enumerate(zip(self.prect, self.corners)):
            color = qt.Qt.darkGreen if corner is not None else qt.Qt.red
            if self.isChecked():
                if ipt == self.currentDefCorner:
                    color = qt.Qt.blue
            paint.setPen(color)
            paint.setBrush(color)
            paint.drawEllipse(pt, 4, 4)
        paint.end()


class StraightRectButton(PerspectiveRectButton):
    prect = (qt.QPoint(9, 10), qt.QPoint(51, 10), qt.QPoint(51, 30),
             qt.QPoint(9, 30))

    def __init__(self, parent=None, buddies=[]):
        super(StraightRectButton, self).__init__('check', parent)
        self.wantVisibleCorners = False
        self.corners = [0] * 4
        self.currentDefCorner = -1
        self.buddies = buddies
        self.setEnabled(False)
        self.setStyleSheet(
            "QPushButton:checked{background-color: lime;}"
            "QPushButton:pressed{background-color: lime;}")

    def update(self):
        super(StraightRectButton, self).update()
        if self.parent() is not None:
            self.wantVisibleCorners = self.parent().canTransform()
            if self.wantVisibleCorners:
                self.parent().getTransform()
        self.setEnabled(self.wantVisibleCorners)

    def clickedSlot(self):
        self.parent().buttonBaseRect.setEnabled(not self.isChecked())
        self.parent().getTransform()
        self.parent().updateFrame()


class ScaleXButton(qt.QPushButton):
    path = (qt.QPoint(8, 30), qt.QPoint(16, 32), qt.QPoint(16, 28),
            qt.QPoint(8, 30),
            qt.QPoint(52, 30), qt.QPoint(44, 32), qt.QPoint(44, 28),
            qt.QPoint(52, 30))

    def __init__(self, text='', parent=None):
        super(ScaleXButton, self).__init__(text, parent)
        self.polygon = qt.QPolygonF()
        for pt in self.path:
            self.polygon.append(pt)
        self.scale = 0
        self.buddyEdit = None
        self.clicked.connect(self.clickedSlot)

    def clickedSlot(self):
        if self.buddyEdit is not None:
            self.setVisible(False)
            self.buddyEdit.setVisible(True)
            self.buddyEdit.setFocus()

    def drawText(self, event, painter):
        p = qt.QPoint(event.rect().center().x()-2, 22)
        painter.drawText(p, "X")

    def paintEvent(self, event):
        super(ScaleXButton, self).paintEvent(event)
        paint = qt.QPainter()
        paint.begin(self)
        paint.setRenderHint(qt.QPainter.Antialiasing)
        color = qt.Qt.darkGreen if self.scale else qt.Qt.red
        paint.setPen(color)
        paint.drawPolygon(self.polygon)
        self.drawText(event, paint)
        paint.end()


class ScaleYButton(ScaleXButton):
    path = (qt.QPoint(20, 6), qt.QPoint(18, 14), qt.QPoint(22, 14),
            qt.QPoint(20, 6),
            qt.QPoint(20, 34), qt.QPoint(18, 26), qt.QPoint(22, 26),
            qt.QPoint(20, 34))

    def drawText(self, event, painter):
        painter.drawText(event.rect(), qt.Qt.AlignCenter, "   Y")


class ScaleEdit(qt.QDoubleSpinBox):
    def __init__(self, name, parent=None, buddyButton=None):
        super(ScaleEdit, self).__init__(parent)
        self.name = name
        self.buddyButton = buddyButton
        self.setVisible(False)
        self.setSuffix(" mm")
        self.setDecimals(1)
        self.setMaximum(1000)
        self.setValue(buddyButton.scale)
        self.installEventFilter(self)
        self.setStyleSheet(
            "QDoubleSpinBox:up-button {width: 0;}"
            "QDoubleSpinBox:down-button {width: 0;}")

    def eventFilter(self, widget, event):
        if event.type() == qt.QEvent.KeyPress:
            key = event.key()
            if key in (qt.Qt.Key_Enter, qt.Qt.Key_Return, qt.Qt.Key_Escape):
                self.buddyButton.setVisible(True)
                self.setVisible(False)
                if key in (qt.Qt.Key_Enter, qt.Qt.Key_Return):
                    self.buddyButton.scale = self.value()
                    config.set('rectangle', 'scale'+self.name,
                               str(self.buddyButton.scale))
                    write_config()

                self.parent().buttonStraightRect.update()

        return super(ScaleEdit, self).eventFilter(widget, event)


class OrthoView(qt.QWidget):
    def __init__(self, parent=None):
        super(OrthoView, self).__init__(parent)

        self.setWindowTitle('OrthoView')
        self.setMinimumSize(800, 600+53)
#        self.setFixedSize(640, 480)
        self.beamPosRectified = [0, 0]

        self.plotCanvas = MyMplCanvas(self)
        self.plotCanvas.setSizePolicy(
            qt.QSizePolicy.Expanding, qt.QSizePolicy.Expanding)
        self.toolbar = MyToolBar(self.plotCanvas, self)
        for action in self.toolbar.findChildren(qtwidgets.QAction):
            if action.text() in ['Customize', 'Subplots']:
                action.setVisible(False)
        self.toolbar.locLabel.setAlignment(qt.Qt.AlignCenter)

        layoutT = qt.QHBoxLayout()
        self.buttonBaseRect = PerspectiveRectButton()
        self.buttonBaseRect.corners = eval(config.get('rectangle', 'corners'))

        self.buttonScaleX = ScaleXButton()
        self.buttonScaleX.scale = float(config.get('rectangle', 'scalex'))
        self.editScaleX = ScaleEdit('x', buddyButton=self.buttonScaleX)
        self.buttonScaleX.buddyEdit = self.editScaleX

        self.buttonScaleY = ScaleYButton()
        self.buttonScaleY.scale = float(config.get('rectangle', 'scaley'))
        self.editScaleY = ScaleEdit('y', buddyButton=self.buttonScaleY)
        self.buttonScaleY.buddyEdit = self.editScaleY

        self.buttonStraightRect = StraightRectButton(buddies=(
            self.buttonBaseRect, self.buttonScaleX, self.buttonScaleY))

        for but in (self.buttonBaseRect,
                    self.buttonScaleX, self.editScaleX,
                    self.buttonScaleY, self.editScaleY,
                    self.buttonStraightRect):
            but.setFixedSize(60, 40)
        layoutT.addWidget(self.toolbar)
        layoutT.addWidget(self.buttonBaseRect)
        layoutT.addWidget(self.buttonScaleX)
        layoutT.addWidget(self.editScaleX)
        layoutT.addWidget(self.buttonScaleY)
        layoutT.addWidget(self.editScaleY)
        layoutT.addWidget(self.buttonStraightRect)
        layout = qt.QVBoxLayout(self)
        layout.addLayout(layoutT)
        layout.addWidget(self.plotCanvas)

        # markers
        self.beamMarkColor = (255, 0, 0)
        self.cornerColor = (0, 192, 0)
        self.currentCornerColor = (64, 64, 255)
        self.gridColor = (192, 192, 192)

        if not isTest:
            self.refreshTimer = qtcore.QTimer()
            self.refreshTimer.timeout.connect(self.updateFrame)
            self.refreshTimer.start(500)  # ms
            try:  # Camera tango device
                self.camera = DeviceProxy('b308a-eh/rpi/cam-01')
            except Exception as e:
                raise Exception("Something is wrong with the tango device {0}".
                                format(e))
        self.updateFrame()
        self.buttonStraightRect.update()

    def getFrame(self):
        if isTest:
            frame = cv2.imread(r"_images/sample-holder-test.png")
            # OpenCV uses BGR as its default colour order for images
            self.img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#            import pickle
#            with open(r"_images/sample-holder-test2.pickle", 'rb') as f:
#                try:
#                    packed = pickle.load(f, encoding='latin1')
#                except TypeError:
#                    packed = pickle.load(f)
#            unpacked = np.empty(list(packed.shape)+[3], dtype=np.uint8)
#            unpacked[:, :, 2] = (packed >> 16) & 0xff
#            unpacked[:, :, 1] = (packed >> 8) & 0xff
#            unpacked[:, :, 0] = packed & 0xff
#            self.img = unpacked

        else:
            frame = self.camera.read_attribute('Image').value

            # for monochrome frames:
#            self.img = cv2.normalize(
#                src=frame, dst=None, alpha=0, beta=255,
#                norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
#            self.img = cv2.cvtColor(self.img, cv2.COLOR_GRAY2BGR)

            # for color frames:
            unpacked = np.empty(list(frame.shape)+[3], dtype=np.uint8)
            unpacked[:, :, 2] = (frame >> 16) & 0xff
            unpacked[:, :, 1] = (frame >> 8) & 0xff
            unpacked[:, :, 0] = frame & 0xff
            self.img = unpacked

    def updateFrame(self):
        self.getFrame()
        try:
            CV_AA = cv2.CV_AA
        except AttributeError:
            CV_AA = cv2.LINE_AA

        if self.canTransform() and self.buttonStraightRect.isChecked():
            # draw rectified
            self.img = cv2.warpPerspective(
                self.img, self.perspectiveTransform2,
                (self.boundingRect[2], self.boundingRect[3]))
            overlay = self.img.copy()
            ps = self.img.shape[0] * 0.02

            # grid:
            grid = np.arange(-10, 10) * 10 * self.zoom
            xgrid = np.int16(self.targetRect[0][0] + grid)
            ygrid = np.int16(self.targetRect[0][1] + grid)
            for xg in xgrid:
                cv2.line(overlay, (xg, ygrid[0]), (xg, ygrid[-1]),
                         self.gridColor, 2)
            for yg in ygrid:
                cv2.line(overlay, (xgrid[0], yg), (xgrid[-1], yg),
                         self.gridColor, 2)

            # beam position mark:
            if self.plotCanvas.isBeamPositionVisible:
                cv2.circle(
                    overlay, tuple(int(p) for p in self.beamPosRectified),
                    int(ps*0.75), self.beamMarkColor, int(ps/3.), CV_AA)

            # rectangle corners:
            if self.plotCanvas.isRectVisible:
                for corner in self.targetRect:
                    cv2.circle(overlay, corner, int(ps/3.), self.cornerColor,
                               -1, CV_AA)

        else:
            overlay = self.img.copy()
            ps = self.img.shape[0] * 0.02

            # beam position mark + text:
            if self.plotCanvas.isBeamPositionVisible:
                beamPos = tuple(self.plotCanvas.beamPos)
#                beamMarkTextPos = (beamPos[0]+10, beamPos[1]+20)
                cv2.circle(
                    overlay, beamPos,
                    int(ps), self.beamMarkColor, int(ps/3.), CV_AA)
                # cv2.putText(
                #     overlay, 'beam', beamMarkTextPos,
                #     cv2.FONT_HERSHEY_SIMPLEX, 0.75, self.beamMarkColor, 1)

            # rectangle corners:
            if self.plotCanvas.isRectVisible:
                for icorner, corner in enumerate(self.buttonBaseRect.corners):
                    if corner is None:
                        continue
                    color = self.cornerColor
                    if self.buttonBaseRect.isChecked():
                        if icorner == self.buttonBaseRect.currentDefCorner:
                            color = self.currentCornerColor
                    cv2.circle(overlay, corner, int(ps/3.), color, -1, CV_AA)

        alpha = 0.75  # transparency factor
        imageNew = cv2.addWeighted(overlay, alpha, self.img, 1-alpha, 0)
        self.plotCanvas.imshow(imageNew)

    def canTransform(self):
        return ((None not in self.buttonBaseRect.corners) and
                self.buttonScaleX.scale > 0 and self.buttonScaleY.scale > 0)

    def getTransform(self):
        dY2, dX2 = self.img.shape[:2]
        dX, dY = self.buttonScaleX.scale, self.buttonScaleY.scale
        self.zoom = dX2 / dX
        dX = int(dX * self.zoom)
        dY = int(dY * self.zoom)
        pIn = self.buttonBaseRect.corners
        pOut = [(0, 0), (dX, 0), (dX, dY), (0, dY)]
        self.perspectiveTransform1 = cv2.getPerspectiveTransform(
            np.float32(pIn), np.float32(pOut))

        inCorners = [[(0, 0), (dX2, 0), (dX2, dY2), (0, dY2)]]
        outCorners = cv2.perspectiveTransform(
            np.float32(inCorners), self.perspectiveTransform1)
        self.boundingRect = cv2.boundingRect(outCorners)
        self.beamPosRectified = self.transformPoint(self.plotCanvas.beamPos)
        self.targetRect = [(x-self.boundingRect[0], y-self.boundingRect[1])
                           for x, y in pOut]
        self.perspectiveTransform2 = cv2.getPerspectiveTransform(
            np.float32(pIn), np.float32(self.targetRect))

    def transformPoint(self, p):
        outPoint = cv2.perspectiveTransform(
            np.float32([[p]]), self.perspectiveTransform1)
        return (outPoint[0][-1][0]-self.boundingRect[0],
                outPoint[0][-1][1]-self.boundingRect[1])


if __name__ == "__main__":
    if isTest:
        app = qt.QApplication(sys.argv)
    else:
        from taurus.qt.qtgui.application import TaurusApplication
        app = TaurusApplication(sys.argv)
    icon = qt.QIcon(os.path.join(selfDir, '_static', 'orthoview.ico'))
    app.setWindowIcon(icon)

    window = OrthoView()
    window.show()
    sys.exit(app.exec_())
