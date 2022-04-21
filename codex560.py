#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#   Copyright 2012 Aslak Grinsted
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#
#

# Aslak UPDATED 21/04/2022 to work in python 3 and only import redis when necessary
#
"""

.. moduleauthor:: Aslak Grinsted <ag@glaciology.net>

Driver for the Kübler Codex 560 counter, for communication via the Modbus RTU protocol.

"""


import minimalmodbus
import struct
import time
import glob
import sys
import math


__author__  = "Aslak Grinsted"
__email__   = "ag@glaciology.net"
__license__ = "Apache License, Version 2.0"

slaveaddress = 1 # this is the address of the unit.
REDIS_HOST = "localhost"






class Codex560( minimalmodbus.Instrument ):
    """Instrument class for Codex 560 process controller.

    Communicates via Modbus RTU protocol (via RS232 or RS485), using the *MinimalModbus* Python module.

    Args:
        * portname (str): port name
        * slaveaddress (int): slave address in the range 1 to 247

    """

    def __init__(self, portname, slaveaddress):
        #default is big-endian..
        minimalmodbus.Instrument.__init__(self, portname, slaveaddress)
        self.serial.baudrate = 9600   # Baud
        self.serial.bytesize = 8
        self.serial.parity   = minimalmodbus.serial.PARITY_EVEN
        self.serial.stopbits = 1
        self.serial.timeout = 0.6
        time.sleep(0.05) #dont start reading immediately


    #
    #            GETTER METHODS
    #

    def get_main_counter(self):
        """get main counter"""
        return self.read_float(registeraddress = 0x0000)

    def get_secondary_counter(self):
        """get secondary counter"""
        return self.read_float(registeraddress = 0x0002)

    def get_preset1(self):
        """desc"""
        return self.read_float(registeraddress = 0x0004)

    def get_preset2(self):
        """desc"""
        return self.read_float(registeraddress = 0x0006)

    def get_decimalplaces(self):
        """desc"""
        return self.read_long(registeraddress = 0x8012) >> 24

    def get_status(self):
        """desc"""
        packedbytes=self.read_long(registeraddress = 0x8014)
        return struct.unpack("BBBB",struct.pack("I",packedbytes))

    #
    #            SETTER METHODS
    #

    def reset_main_counter(self):
        """Resets the main counter"""
        self.write_float(registeraddress = 0, value = 0.0);
        return

    def reset_secondary_counter(self):
        """Resets the secondary counter"""
        self.write_float(registeraddress = 2, value = 0.0);
        return

    def set_preset1(self,value):
        """Sets preset 1"""
        self.write_float(registeraddress = 4, value = value);
        return

    def set_preset2(self,value):
        """Sets preset 2"""
        self.write_float(registeraddress = 6, value = value);
        return

    def set_multiplication_factor(self,value):
        """Sets multiplication factor. 0 to 99.99999 """
        self.write_float(registeraddress = 8, value = value);
        return

    def set_division_factor(self,value):
        """Sets division factor. 0 to 99.99999 """
        self.write_float(registeraddress = 0xA, value = value);
        return

    #def store_set_value(self):
    #    self.write_float(registeraddress = 0xC,0.0);
    #    return

    #def perform_set_function(self):
    #    """"""
    #    self.write_float(registeraddress = 0xE,0.0);
    #    return

    #def set_preset_1_sign_setting(self):
    #    self.write_registers(0x8010,????);
    #    return

    #def set_decimal_places(self,value):
    #    """Must be between 0-5 """
    #    self.write_registers(0x8012,????);
    #    return


########################
## Testing the module ##
########################

if __name__ == '__main__':
    import redis
    print("Winch encoder")
    try:
        encoderDisplay = Codex560(sys.argv[1], slaveaddress)
    except:
        ports=glob.glob("/dev/ttyUSB*")
        encoderDisplay = None
        for port in ports:
            try:
                print("- testing for codex560 with address {0} on {1}".format(slaveaddress,port))
                encoderDisplay = Codex560(port, slaveaddress)
                encoderDisplay.get_status()
                print("Kübler CODEX-560 found on {0}".format(port))
                break
            except Exception as e:
                encoderDisplay = None

        if encoderDisplay is None:
            sys.exit("No port found for Kübler CODEX-560 encoder!")

    redis_conn = redis.StrictRedis(host=REDIS_HOST)

    #When we the drill is moving slowly then we need to make a moving average because the depthencoder only gives us cm-resolution.
    #w is a constant that controls how much "memory" is in the system when we calculate the velocity.
    efolding_time = 5.0 #Forget history after about 5-10 seconds.;
    efolding_depth = 0.02 #Forget history after moving 2-4cm we should have almost forgotten previous states.

    #encoderDisplay.debug = True
    olddepth=0.0
    oldtime=time.time()
    while True:
        time.sleep(0.1) #note: sleep at least by 0.01
        curdepth=encoderDisplay.get_main_counter()
        curtime=time.time()
        dt = curtime - oldtime
        dz = curdepth - olddepth
        w = math.exp(-math.fabs(dz) / efolding_depth - dt / efolding_time);
        velocity=(curdepth-olddepth)/(curtime-oldtime)
        redis_conn.set("depth-encoder", "{\"depth\": %f, \"velocity\": %f}" % (curdepth, velocity))
        # redis_conn.set("depth-encoder-velocity", velocity)
        # print("{0} // {1}".format(curdepth,velocity))

        oldtime=curtime
        olddepth=curdepth






    #a.debug = True
    #minimalmodbus._print_out( 'Main counter:           {0}'.format(  a.get_main_counter()      ))
    #time.sleep(0.01)
    #minimalmodbus._print_out( 'Status:                 {0}'.format(  repr(a.get_status())      ))
    #minimalmodbus._print_out( 'Secondary counter:      {0}'.format(  a.get_secondary_counter()  ))
    #minimalmodbus._print_out( 'Preset 1:               {0}'.format(  a.get_preset1()           ))
    #minimalmodbus._print_out( 'Preset 2:               {0}'.format(  a.get_preset2()           ))
    #time.sleep(0.01)
    #minimalmodbus._print_out( 'Decimal places:         {0}'.format(  a.get_decimalplaces()     ))
    #todo: more tests
    #minimalmodbus._print_out( 'DONE!' )

pass
