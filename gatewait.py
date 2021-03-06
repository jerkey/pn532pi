#!/usr/bin/python3
# To enable debug message, set DEBUG in nfc/PN532_log.h
import time
import binascii
import datetime
import serial

from pn532pi.nfc.pn532 import Pn532
import pn532pi.nfc.pn532 as pn532
from pn532pi.interfaces.pn532hsu import Pn532Hsu

keypad = serial.Serial(port='/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_00897CCA-if00-port0', baudrate=57600)
keypadString = '' # used to build up strings from key pad
lastKeyTime = time.time() # initialize global variable

accessfile = open('/home/pi/pn532pi/access.list','r')

logfile = open('/tmp/'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.log','w')

PN532_HSU = Pn532Hsu('/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0')
PN532_HSU._serial.setRTS(False) # keep RTS pin high (3.3v) when program starts
PN532_HSU._serial.setDTR(False) # keep DTR pin high (3.3v) when program starts
nfc = Pn532(PN532_HSU)

accesslist = {}

def loadaccessfile():
    for line in accessfile:
        if line.split(' ')[-1][0:2] == "b'":
            accesslist[line.split(' ')[-1].split('\'')[1]] = line.split(' ')[-3:-1] # key is text of UID, store two things before it
        else:
            logwrite('skipping accessfile line: '+line[:-1]) # don't log the \n at the end of the line

def logwrite(record):
    print(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'	'+record)
    logfile.write(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'	'+record+'\n')
    logfile.flush()

def setup():
    nfc.begin()

    versiondata = nfc.getFirmwareVersion()
    if not versiondata:
        logwrite("Didn't find PN53x board")
        raise RuntimeError("Didn't find PN53x board")  # halt

    # Got ok data, print it out!
    logwrite("Found chip PN5 {:#x} Firmware ver. {:d}.{:d}".format((versiondata >> 24) & 0xFF, (versiondata >> 16) & 0xFF,
                                                                (versiondata >> 8) & 0xFF))
    # Set the max number of retry attempts to read from a card
    # This prevents us from waiting forever for a card, which is
    # the default behaviour of the pn532.
    nfc.setPassiveActivationRetries(0xFF)

    # configure board to read RFID tags
    nfc.SAMConfig()

    logwrite("Waiting for an ISO14443A card")

def handleKeypad():
    global keypadString, lastKeyTime
    while keypad.in_waiting:
        lastKeyTime = time.time()
        key = chr(keypad.read(1)[0]) # read a single byte from the buffer
        if key == '\r': # arduino Serial.println() terminates lines with \r\n
            keypad.read(1) # swallow the \n from the arduino
            ksf = keypadString.find('found in record') # record number comes after "record"
            if ksf >= 0:
                logwrite("code " + keypadString[ksf:]) # truncate everything before "found in record"
                keypadString = '' # clear the string so it doesn't get printed
                bleepForSeconds(7) # make the bleeping sound while latch is held by arduino
        else:
            keypadString += key
    if len(keypadString) and time.time() - lastKeyTime > 5: # from ENTRYCODETIMEOUT in doorkeypad.ino
        logwrite("keypad: " + keypadString)
        keypadString = ''

def bleepForSeconds(howManySeconds):
    for bleeps in range(howManySeconds):
        time.sleep(0.9)
        PN532_HSU._serial.setRTS(True) # start the beeper
        time.sleep(0.1)
        PN532_HSU._serial.setRTS(False) # stop the beeper

def loop():
    # Wait for an ISO14443A type cards (Mifare, etc.).  When one is found
    # 'uid' will be populated with the UID, and uidLength will indicate
    # if the uid is 4 bytes (Mifare Classic) or 7 bytes (Mifare Ultralight)
    success, uid = nfc.readPassiveTargetID(pn532.PN532_MIFARE_ISO14443A_106KBPS)

    if (success):
        print("Found a card!  UID Length: {:d}                                           ".format(len(uid)))
        uid_str = str(binascii.hexlify(uid)).split('\'')[1]
        if uid_str in accesslist:
            logwrite("UID Value: {} is {} and {}".format(uid_str, accesslist[uid_str][0], accesslist[uid_str][1]))
            if accesslist[uid_str][1] == 'grant':
                PN532_HSU._serial.setRTS(True) # start the beeper
                PN532_HSU._serial.setDTR(True) # energize the solenoid
                time.sleep(1) # Wait before stopping the beeper
                PN532_HSU._serial.setRTS(False) # stop the beeper
                bleepForSeconds(7) # Wait before de-energizing the solenoid
                PN532_HSU._serial.setDTR(False)
            else:
                logwrite("not granting access to UID Value: {} because {} != \'grant\'".format(uid_str, accesslist[uid_str][1]))
                keypad.write(b"S") # tell keypad to make a sad tone
                time.sleep(5) # Wait before continuing
        else:
            logwrite("UID Value: UNRECOGNIZED {}".format(binascii.hexlify(uid)))
            keypad.write(b"S") # tell keypad to make a sad tone
            time.sleep(5) # Wait before continuing
        return True
    else:
        # pn532 probably timed out waiting for a card
        #print(str(time.time())+" Timed out waiting for a card                 ",end='\r')
        handleKeypad()
        return False


if __name__ == '__main__':
    loadaccessfile()
    logwrite('loaded access.list with '+str(len(accesslist))+' records')
    setup()
    while True:
        loop()
