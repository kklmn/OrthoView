OrthoView
=========

OrthoView is a Qt widget for viewing a scene with a camera and converting the
image coordinates to orthogonal coordinates in a selected target plane. After
this conversion, any cursor position on the image can define a relative shift
of the plane by its local XY movements. The widget is used to visually select
a sample in a sample plate.

<p align="center">
  <img src="_images/OrthoView_ani.gif " width=600 />
</p>

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

An example of Tango device for a USB camera is also supplied: `USBCamera.py`.
