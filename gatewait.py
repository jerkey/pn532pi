#!/usr/bin/python3
# To enable debug message, set DEBUG in nfc/PN532_log.h
import time
import binascii
import datetime

from pn532pi.nfc.pn532 import Pn532
import pn532pi.nfc.pn532 as pn532
from pn532pi.interfaces.pn532hsu import Pn532Hsu

accessfile = open('access.list','r')

logfile = open('/tmp/'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.log','w')

PN532_HSU = Pn532Hsu('/dev/ttyUSB0')
PN532_HSU._serial.setRTS(False)
PN532_HSU._serial.setDTR(False)
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
        else:
            logwrite("UID Value: UNRECOGNIZED {}".format(binascii.hexlify(uid)))
        # Wait 5 seconds before continuing
        time.sleep(5)
        return True
    else:
        # pn532 probably timed out waiting for a card
        print(str(time.time())+" Timed out waiting for a card                 ",end='\r')
        return False


if __name__ == '__main__':
    loadaccessfile()
    logwrite('loaded accessfile.list with '+str(len(accesslist))+' records')
    setup()
    while True:
        loop()
