# -*- coding: utf-8 -*-
"""
USBCamera class for a USB camera connected to a Raspberry Pi.
The image is a device attribute of PyTango.DevULong type that packs 3 
one-byte-long color channels. The client should unpack colors like this:

``
    frame = self.camera.read_attribute('Image').value
    unpacked = np.empty(list(frame.shape)+[3], dtype=np.uint8)
    unpacked[:, :, 2] = (frame >> 16) & 0xff
    unpacked[:, :, 1] = (frame >> 8) & 0xff
    unpacked[:, :, 0] = frame & 0xff
``

"""
__author__ = "started by Juliano Murari, finished by Konstantin Klementiev"
__versioninfo__ = (1, 0, 0)
__version__ = '.'.join(map(str, __versioninfo__))
__date__ = "24 Mar 2020"
__license__ = "MIT license"

import time
import datetime

import cv2  # > 3.0!
import numpy as np
# import os
import glob

import PyTango
from PyTango import AttrWriteType, DevState, DebugIt
from PyTango.server import Device, DeviceMeta, attribute, server_run
from PyTango.server import device_property


class USBCamera(Device):
    __metaclass__ = DeviceMeta

    # Device name from /dev/v4l/by-id/usb-[name]-index0
    # check info with usb-devices command
    dev_name = device_property(dtype=str)

    # image from camera device
    # use dtype=((PyTango.DevUShort,),), for monochrome images
    image = attribute(label="Image", dtype=((PyTango.DevULong,),),
                      max_dim_x=640, max_dim_y=480,
                      access=AttrWriteType.READ)

    @DebugIt()
    def init_device(self):
        self.set_state(DevState.INIT)
        self.get_device_properties()  # necessary before use the properties

        # dev_name = 'Image_Processor_USB_2.0_PC_Cam' (property)
        camera_path = '/dev/v4l/by-id/usb-' + self.dev_name + '*'
#        camera_path = "/dev/video*"
        self._image = None
        self.previous_frame = np.empty((0))

        device_paths = sorted(glob.glob(camera_path))
        print(device_paths)
        if len(device_paths) == 0:
            status = "Error: device does not exist. Check connection.\n"
            self.info_stream(status)
            self.set_status(status)
            self.set_state(DevState.FAULT)
        else:
            for device_path in device_paths:
                self.info_stream("init device on " + device_path)
                self.camera = cv2.VideoCapture(str(device_path))
                time.sleep(2)
                if self.camera.isOpened():
                    break
                self.camera.release()

            # check camera
            if self.camera.isOpened():
                now = datetime.datetime.now()
                status = now.strftime("%Y/%m/%d %H:%M:%S :")
                status += " camera has started correctly"
                self.info_stream(status)
                self.set_status(status)
                self.set_state(DevState.ON)
            else:
                status = "Error: camera has not started correctly"
                self.info_stream(status)
                self.set_status(status)
                self.set_state(DevState.FAULT)

    def delete_device(self):
        try:
            self.camera.release()
            del(self.camera)
        except:
            pass
        time.sleep(1)

    def info_stream(self, info):
        print(info)
        super(USBCamera, self).info_stream(info)

    def pack_frame(self, fr):
        return (fr[:, :, 0] * 0x10000) + (fr[:, :, 1] * 0x100) + fr[:, :, 2]

    def was_fault(self):
        if self.get_state() != DevState.FAULT:
            return False
        self.delete_device()
        self.init_device()
        return True

    @DebugIt()
    def read_attr_hardware(self, attr_list):
        if self.was_fault():
            return
        if not self.camera.isOpened():
            status = "Error with camera connection"
            self.info_stream(status)
            self.set_status(status)
            self.set_state(DevState.FAULT)
            self.delete_device()
            self.init_device()
            return

        try:
            ret, frame = self.camera.read()
        except Exception as e:
            print('**********')
            print(e)

        # ret can be True even if you unplug the camera, wtf!
        if not ret or np.array_equal(self.previous_frame, frame):
            status = "Error to read image"
            self.info_stream(status)
            self.set_status(status)
            self.set_state(DevState.FAULT)
            self.delete_device()
            self.init_device()
            return

        if self._image is None:
            self._image = np.empty(frame.shape[0:2], dtype=np.uint32)
        # convert to gray scale:
        # self._image[:, :] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self._image[:, :] = self.pack_frame(frame)
        status = "The device is ON"
        # self.info_stream(status)
        self.set_status(status)
        self.set_state(DevState.ON)
        self.previous_frame = frame

    @DebugIt()
    def read_image(self):
        self.was_fault()
        return self._image

    def is_image_allowed(self, request):
        self.was_fault()
        return self.get_state() != DevState.FAULT


def main():
    server_run([USBCamera])


if __name__ == "__main__":
    main()
