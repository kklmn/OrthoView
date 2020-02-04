OrthoView
=========

OrthoView is a Qt widget for viewing a scene with a camera and converting the
image coordinates to orthogonal coordinates in a selected target plane. These
coordinates can later be used for commanding a shift of the plane by its local
XY movements. This can be used to visually select a sample in a sample plate.

<p align="center">
  <img src="_images/OrthoView_ani.gif " width=802 />
</p>

Dependencies
------------

cv2 (opencv-python), optionally taurus.

How to use
----------

With the Perspective Rectangle button (the 1st in the right group) define four
points that form a rectangle in a plane. A blue dot on the button shows the
expected corner to define. Set X and Y dimensions with the next two buttons.
Define the local origin (beam position) by the right mouse click. Check the
resulting image orthogonality in the expected plane by the last button. Also
observe the mouse coordinates in the target plane, as displayed at the top.

To use the motion functionality, set `isTest = False`, define your motions in
the top part of the module and use them in the method `moveToBeam()`.
