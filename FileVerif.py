import csv
import sys
import copy
import re

import inspect
import os
import logging
from datetime import datetime
from xml.dom.minidom import parse

logging.basicConfig(level=logging.INFO,
                    format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
                    datefmt="%H:%M:%S", stream=sys.stdout)

logger = logging.getLogger(__name__)

############### CONFIGURATION  ################

DEBUG_ON = 0
DEBUG_LOG = 0
SEND_TO_CARD = 1

EXP_FROM_CARD = 0  # 1= build expected value from card (only if the parameter is empty)

OPT_CHV1_DISABLED = 0 # MS

OPT_SCANNING_CARD_HEADER = 1    # 1 = CTD support read header command (default)
                                # 0 = CTD not support read header command

OPT_SCANNING_CARD_DEEP = 0      # 1 = Deep scanning logical model under MF (default)
                                # 0 = Scanning base on common logical model

OPT_HEX_ARRREREF = 1  # Record number in ARR Reference
OPT_HEX_RECORDNUMBER = 0  # For reference to EF ARR
OPT_HEX_SFI = 1
OPT_SHAREABLE_WARNING = 0
OPT_EXPECTED_PADDING = 1    # 1 = Padding the expected content if the length is less than the actual file
                            # 0 = Compare only up to the expected content value (the rest are not checked)

FILESIZE_RULE = 1   # When using single field "File Size" for rule
                    # 1: RecSize x NumOfRecord
                    # 2: NumOfRecord x RecSize
                    # in any case, number after '=' sign means File Size, and if there are no multiplication
                    # it means only file size

OPT_FILEID_EF_FULLPATH = 0  # when using only FileID to define the path
                            # 1: EF always defined the full path

OPT_SELECT3G_ADF = 0    # Use this when using POP CTD
                        # 1: When select ADF_AID for USIM

OPT_CHECK_CONTENT_3G = 0    # when it needed check 3G content
                            # 1: Checking 3G content
OPT_CHECK_LINK3G = 0        # when it needed to check link on 3G content
                            # 1: Checking link 3G

OPT_CHECK_LINK = 1
OPT_CHECK_LINK_UPDATE = 1

OPT_2G_ACC = 0  # option if there is more than 1 ACC in 2G mode (AND or OR Template)
                # 0 : if the one that was consider is the first ACC
                # 1 : if the one that was consider is the second ACC

OPT_3G_ACC_ALL_MATCH = 0    # 0: for more than 1 SCDO ( AND or OR Template), all must exist and LOGIC must be correct
                            # 1: At least one of the SCDO match found in card

OPT_ARR4_2G = 0  # use ARR for 2G Access condition
ArrFileId1 = "2F06"  # For ARR ID under MF
ArrFileId2 = "6F06"

OPT_PRINT_ERROR = 0 # print errors to stdout
OPT_ERROR_FILE = 1 # generate error document

# leave as it is; used internally by VerifClient
OPT_USE_CLIENT = False
runlog_buffer = []
runlogFileName = 'run.log'
opt_debugprint_client_variables = False

OPT_USE_VARIABLES = True # use Variables.txt generated from Adv Save
OPT_CREATE_FULL_SCRIPT = True # create full script
FILE_VERIF_VERSION = '0.0.7'

# list of possible value. Be careful that the list should be mutually exclusive
# for example, if linear fixed are ['LF', 'L'] but linked file as ['LK',], linked file can be detected as Linear Fixed.
sFileTypeMF = ('MF', 'M')
sFileTypeDF = ('DF', 'D')
sFileTypeADF = ['ADF']
sFileTypeEF = ['EF', 'E']

sFileStructTR = ['Transparent', 'TR', 'T']
sFileStructLF = ['Linear', 'LF']
sFileStructCY = ['Cyclic', 'CY', 'C']
sFileStructLK = ['LK', 'VIR', 'Link']  # Handle Link File

sMandatoryYes = ['M', 'YES', 'Y']
sMandatoryNo = ['O', 'NO', 'N']

sShareableYes = ['YES', 'Y']
sUpdateActivityHigh = ['High', 'HIGH', 'Y']

sAccALW = ['Always', 'ALW']
sAccCHV1 = ['GPIN1', 'CHV1','APIN1']
sAccCHV2 = ['LPIN1', 'CHV2','2APIN1']
sAccADM1 = ['ADM1']
sAccADM2 = ['ADM2']
sAccADM3 = ['ADM3']
sAccADM4 = ['ADM4']
sAccADM5 = ['ADM5']
sAccNEV = ['Never', 'NEV']
sAccAND = ['AND','&'] 
sAccOR = ['OR','|']

OPT_USE_ADM2 = 1
OPT_USE_ADM3 = 0
OPT_USE_ADM4 = 0

############### END OF CONFIGURATION  ################

# ScriptPath = os.path.dirname(os.path.realpath(__file__))
ScriptPath = os.path.dirname(os.path.realpath(sys.argv[0]))

############### INPUT - OUTPUT ################
file = '2849'
FileName = ScriptPath + '\\' + file + '.csv'
ReaderNumber = 0  # start from 0

OptWrite2File = 1
OutputFileName = ScriptPath + '\\' + file + '_output.pcom'
DebugFileName = ScriptPath + '\\' + file + '_debug.txt'
ErrorFileName = ScriptPath + '\\' + file + '_error.html'
VariablesFileName = '..\\' + 'Variables.txt'
FullScriptFileName = ScriptPath + '\\' + file + '_FULLSCRIPT.pcom'

# Change accordingly
ADM1 = "933F57845F706921"
ADM2 = "933F57845F706921"
ADM3 = "933F57845F706921"
ADM4 = "933F57845F706921"
CHV1 = "31323334FFFFFFFF"
CHV2 = "31323334FFFFFFFF"
ADF_AID = "A0000000871002FF49FFFF89040B00FF"
ADF_AID_LENGTH = 0x10

# Update this if the variables are manually provided.
# Should the variables taken from file Variables.txt, the VarList is generated in the section below
if not OPT_USE_VARIABLES:   
    VarList = {'ICCID': '98123108001757010071',
               'IMSI': '084981041000200010',
               'GPUK1': '12345678',
               'LPUK1': '12345678',
               'ACC': '0002'}

# global variables
OutputFile = None
fiContent = None
curFilePath = None
prevFilePath = None
curFile = None
curOps = None
curRec = None
curFileDescName = None
verificationErrors = None
ErrorFile = None
runLog = None
tmpContent = None
efMarker = '(marker not set)'

# APDU params
verify2gAdm1p1 = 0x00
verify2gAdm1p2 = 0x00
verify2gAdm1p3 = 0x08

verify2gAdm2p1 = 0x00
verify2gAdm2p2 = 0x05
verify2gAdm2p3 = 0x08

verify2gAdm3p1 = 0x00
verify2gAdm3p2 = 0x06
verify2gAdm3p3 = 0x08

verify2gAdm4p1 = 0x00
verify2gAdm4p2 = 0x07
verify2gAdm4p3 = 0x08

verify2gChv1p1 = 0x00
verify2gChv1p2 = 0x01
verify2gChv1p3 = 0x08

verify2gChv2p1 = 0x00
verify2gChv2p2 = 0x02
verify2gChv2p3 = 0x08

verify3gAdm1p1 = 0x00
verify3gAdm1p2 = 0x0A
verify3gAdm1p3 = 0x08

verify3gAdm2p1 = 0x00
verify3gAdm2p2 = 0x0B
verify3gAdm2p3 = 0x08

verify3gAdm3p1 = 0x00
verify3gAdm3p2 = 0x0C
verify3gAdm3p3 = 0x08

verify3gAdm4p1 = 0x00
verify3gAdm4p2 = 0x0D
verify3gAdm4p3 = 0x08

verify3gGlobalPin1p1 = 0x00
verify3gGlobalPin1p2 = 0x01
verify3gGlobalPin1p3 = 0x08

verify3gLocalPin1p1 = 0x00
verify3gLocalPin1p2 = 0x81
verify3gLocalPin1p3 = 0x08

ENABLECHV1 = [0xA0, 0x28, 0x00, 0x01, 0x08] # MS
DISABLECHV1 = [0xA0, 0x26, 0x00, 0x01, 0x08] # MS
VERIFPIN2G = [0xA0, 0x20, 0x00, 0x00, 0x00]
VERIFPIN3G = [0x00, 0x20, 0x00, 0x00, 0x00]
SELECT3GADF = [0x00, 0xA4, 0x04, 0x04, 0x10]

def PINVerification2G():
    global OutputFile

    runlog_buffer.append('Verify ADM1..')
    Header = copy.deepcopy(VERIFPIN2G)
    Header[2] = verify2gAdm1p1
    Header[3] = verify2gAdm1p2
    Header[4] = verify2gAdm1p3
    SendAPDU(Header, ADM1, None, "9000")

    if OPT_USE_ADM2:
        runlog_buffer.append('Verify ADM2..')
        Header = copy.deepcopy(VERIFPIN2G)
        Header[2] = verify2gAdm2p1
        Header[3] = verify2gAdm2p2
        Header[4] = verify2gAdm2p3
        SendAPDU(Header, ADM2, None, "9000")

    if OPT_USE_ADM3:
        runlog_buffer.append('Verify ADM3..')
        Header = copy.deepcopy(VERIFPIN2G)
        Header[2] = verify2gAdm3p1
        Header[3] = verify2gAdm3p2
        Header[4] = verify2gAdm3p3
        SendAPDU(Header, ADM3, None, "9000")

    if OPT_USE_ADM4:
        runlog_buffer.append('Verify ADM4..')
        Header = copy.deepcopy(VERIFPIN2G)
        Header[2] = verify2gAdm4p1
        Header[3] = verify2gAdm4p2
        Header[4] = verify2gAdm4p3
        SendAPDU(Header, ADM4, None, "9000")
    
    if not OPT_CHV1_DISABLED:
        # enable CHV1
        # OutputFile.writelines('; enable CHV1\n')
        # Header = copy.deepcopy(ENABLECHV1)
        # SendAPDU(Header, CHV1, None, "9000")

        runlog_buffer.append('Verify CHV1..')
        Header = copy.deepcopy(VERIFPIN2G)
        Header[2] = verify2gChv1p1
        Header[3] = verify2gChv1p2
        Header[4] = verify2gChv1p3
        SendAPDU(Header, CHV1, None, "9000")
    else:
        OutputFile.writelines('; CHV1 is disabled. No CHV1 verification required.\n')

    runlog_buffer.append('Verify CHV2..')
    Header = copy.deepcopy(VERIFPIN2G)
    Header[2] = verify2gChv2p1
    Header[3] = verify2gChv2p2
    Header[4] = verify2gChv2p3
    SendAPDU(Header, CHV2, None, "9000")

    return

def PINVerification3G():
    global OutputFile

    runlog_buffer.append('Verify ADM1..')
    Header = copy.deepcopy(VERIFPIN3G)
    Header[2] = verify3gAdm1p1
    Header[3] = verify3gAdm1p2
    Header[4] = verify3gAdm1p3
    SendAPDU(Header, ADM1, None, "9000")

    if OPT_USE_ADM2:
        runlog_buffer.append('Verify ADM2..')
        Header = copy.deepcopy(VERIFPIN3G)
        Header[2] = verify3gAdm2p1
        Header[3] = verify3gAdm2p2
        Header[4] = verify3gAdm2p3
        SendAPDU(Header, ADM2, None, "9000")

    if OPT_USE_ADM3:
        runlog_buffer.append('Verify ADM3..')
        Header = copy.deepcopy(VERIFPIN3G)
        Header[2] = verify3gAdm3p1
        Header[3] = verify3gAdm3p2
        Header[4] = verify3gAdm3p3
        SendAPDU(Header, ADM3, None, "9000")

    if OPT_USE_ADM4:
        runlog_buffer.append('Verify ADM4..')
        Header = copy.deepcopy(VERIFPIN3G)
        Header[2] = verify3gAdm4p1
        Header[3] = verify3gAdm4p2
        Header[4] = verify3gAdm4p3
        SendAPDU(Header, ADM4, None, "9000")

    if not OPT_CHV1_DISABLED:
        # enable CHV1
        # OutputFile.writelines('; enable CHV1\n')
        # Header = copy.deepcopy(ENABLECHV1)
        # SendAPDU(Header, CHV1, None, "9000")

        runlog_buffer.append('Verify Global PIN..')
        Header = copy.deepcopy(VERIFPIN3G)
        Header[2] = verify3gGlobalPin1p1
        Header[3] = verify3gGlobalPin1p2
        Header[4] = verify3gGlobalPin1p3
        SendAPDU(Header, CHV1, None, "9000")
    else:
        OutputFile.writelines('; GPIN is disabled. No GPIN verification required.\n')

    runlog_buffer.append('Verify Local PIN..')
    Header = copy.deepcopy(VERIFPIN3G)
    Header[2] = verify3gLocalPin1p1
    Header[3] = verify3gLocalPin1p2
    Header[4] = verify3gLocalPin1p3
    SendAPDU(Header, CHV2, None, "9000")

    return

############### END OF INPUT - OUTPUT ################

def GetVarValue(VarName):
    if VarName in VarList:
        return VarList[VarName]
    else:
        return None

#Generate VarList from Variables.txt
if OPT_USE_VARIABLES:   
    VarList = {}

    # create variables.txt in parent folder if doesn't exist
    if not os.path.isfile(VariablesFileName):
        f = open(VariablesFileName, 'w')
        f.close()
        logger.info('Created Variables.txt')

    # Read file
    with open(VariablesFileName, 'r') as f:
         variables = f.read()
    f.close()

    # Find all .DEFINE
    var = re.findall(r'%.*', variables, flags=re.MULTILINE)

    # Split VarList into keys and values
    for i in var:
        key,val = re.findall(r'([^\s]+)',i)
        key = key[1:]   # remove % sign
        VarList[key] = val

    # print VarList

################# CONSTANT ##################
iAccUNDEF = -1

NOT_SAVED = 1
SAVED = 0

# Generic Access condition
iAccALW = 0
iAccNEV = 15

# 3G access condition
iAccAPin1 = 1
iAccAPin2 = 2
iAccAPin3 = 3
iAccAPin4 = 4
iAccAPin5 = 5
iAccAPin6 = 6
iAccAPin7 = 7
iAccAPin8 = 8
iAccADM1 = 10
iAccADM2 = 11
iAccADM3 = 12
iAccADM4 = 13
iAccADM5 = 14
iAccAND = 99
iAccOR = 88
iAccUPin = 0x11
iAccCHV1 = 1  # or Application PIN 1
iAccCHV2 = 2  # or Application PIN 2 -> Convert from 0x81 Application PIN 1?

iAccSecAPin1 = 0x81
iAccSecAPin2 = 0x82
iAccSecAPin3 = 0x83
iAccSecAPin4 = 0x84
iAccSecAPin5 = 0x85
iAccSecAPin6 = 0x86
iAccSecAPin7 = 0x87
iAccSecAPin8 = 0x88
iAccADM6 = 0x8A
iAccADM7 = 0x8B
iAccADM8 = 0x8C
iAccADM9 = 0x8D
iAccADM10 = 0x8E

# 2G conversion from 3G access condition
iAcc2GCHV1 = 1  # or Application PIN 1
iAcc2GCHV2 = 2  # or Application PIN 2 -> Convert from 0x81 Application PIN 1
iAcc2GADM1 = 5
iAcc2GADM2 = 6
iAcc2GADM3 = 7
iAcc2GADM4 = 8
iAcc2GADM5 = 9

# PIN mapping into key references
def getACC(accCode):
    if accCode == iAccALW:
        return 'ALW'
    if accCode == iAccNEV:
        return 'NEV'
    if accCode == iAccAPin1:
        return 'PIN Appl 1'
    if accCode == iAccAPin2:
        return 'PIN Appl 2'
    if accCode == iAccAPin3:
        return 'PIN Appl 3'
    if accCode == iAccAPin4:
        return 'PIN Appl 4'
    if accCode == iAccAPin5:
        return 'PIN Appl 5'
    if accCode == iAccAPin6:
        return 'PIN Appl 6'
    if accCode == iAccAPin7:
        return 'PIN Appl 7'
    if accCode == iAccAPin8:
        return 'PIN Appl 8'
    if accCode == iAccSecAPin1:
        return 'Second PIN Appl 1'
    if accCode == iAccSecAPin2:
        return 'Second PIN Appl 2'
    if accCode == iAccSecAPin3:
        return 'Second PIN Appl 3'
    if accCode == iAccSecAPin4:
        return 'Second PIN Appl 4'
    if accCode == iAccSecAPin5:
        return 'Second PIN Appl 5'
    if accCode == iAccSecAPin6:
        return 'Second PIN Appl 6'
    if accCode == iAccSecAPin7:
        return 'Second PIN Appl 7'
    if accCode == iAccSecAPin8:
        return 'Second PIN Appl 8'
    if accCode == iAccADM1:
        return 'ADM1'
    if accCode == iAccADM2:
        return 'ADM2'
    if accCode == iAccADM3:
        return 'ADM3'
    if accCode == iAccADM4:
        return 'ADM4'
    if accCode == iAccADM5:
        return 'ADM5'
    if accCode == iAccADM6:
        return 'ADM6'
    if accCode == iAccADM7:
        return 'ADM7'
    if accCode == iAccADM8:
        return 'ADM8'
    if accCode == iAccADM9:
        return 'ADM9'
    if accCode == iAccADM10:
        return 'ADM10'
    if accCode == iAccUPin:
        return 'PIN Universal PIN'
    if accCode == iAccOR:
        return 'OR'
    if accCode == iAccAND:
        return 'AND'

# def ConvertACC(cur):
def CovertACC3GTo2G(Cur):
    if Cur == iAccSecAPin1:  # Some Second Appl 2 map 2 CHV2
        return iAcc2GCHV2
    if Cur == iAccADM1:
        return iAcc2GADM1
    if Cur == iAccADM2:
        return iAcc2GADM2
    if Cur == iAccADM3:
        return iAcc2GADM3
    if Cur == iAccADM3:
        return iAcc2GADM3
    if Cur == iAccADM4:
        return iAcc2GADM4
    if Cur == iAccADM5:
        return iAcc2GADM5
    # default: Return without modification
    return Cur

# File information
fFileName = "FileName"
fFileDescription = "FileDescription"
fFilePath = "FilePath"
fFileIdLevel1 = "FileIdLevel1"
fFileIdLevel2 = "FileIdLevel2"
fFileIdLevel3 = "FileIdLevel3"
fFileID = "FileID"
fSFI = "SFI"
fMandatory = "Mandatory"
fADF_AID = "ADF_AID"
fFileType = "FileType"
fFileStructure = "FileStructure"
fShareable = "Shareable"
fFileSize = "FileSize"
fFileRecordSize = "FileRecordSize"
fFileRecordOrFileSize = "FileRecordOrFileSize"
fNumberOfRecord = "NumberOfRecord"
fUpdateActivity = "UpdateActivity"
fLinkTo = "LinkTo"
fLinkToApp = "LinkToApp"
fRecordNumber = "RecordNumber"
fContent = "Content"
fADN_AlphaID = "ADN_AlphaID"
fADNNumber = "ADNNumber"

# 2G ACC
fRead_ACC = "Read_ACC"
fUpdate_ACC = "Update_ACC"
fIncrease_ACC = "Increase_ACC"
fRFU_ACC = "RFU_ACC"
fRehabilitate_ACC = "Rehabilitate_ACC"
fInvalidate_ACC = "Invalidate_ACC"
fACC_2G = "ACC_2G"

# Access Record Rules
fARRPath = "ARRPath"
fARRID = "ARRID"
fARRRecordNumber = "ARRRecordNumber"
fARRRef = "ARRRef"
fARRContent = "ARRContent"

# 3G ACC
fDeleteChild_ACC = "DeleteChild_ACC"
fDeleteSelf_ACC = "DeleteSelf_ACC"
fCreateDFEF_ACC = "CreateDFEF_ACC"
fCreateEF_ACC = "CreateEF_ACC"
fCreateDF_ACC = "CreateDF_ACC"
fDeactivate_ACC = "Deactivate_ACC"
fActivate_ACC = "Activate_ACC"
fTerminate_ACC = "Terminate_ACC"
fResize_ACC = "Resize_ACC"
fOtherCLA_ACC = "OtherCLA_ACC"
fOtherINS_ACC = "OtherINS_ACC"
fOtherValue_ACC = "OtherValue_ACC"
fRead3G_ACC = "Read3G_ACC"
fUpdate3G_ACC = "Update3G_ACC"
fWrite3G_ACC = "Write3G_ACC"
fIncrease3G_ACC = "Increase3G_ACC"
fReadDeleteChild_ACC = "ReadDeleteChild_ACC"
fUpdateCreateChild_ACC = "UpdateCreateChild_ACC"
fCustom_ACC = "Custom_ACC"

# Other
fOTAAccess = "OTAAccess"
fValuated = "Valuated"
fVariableName = "VariableName"
fDummy = "Dummy"

INS_INCREASE = 0x32
INS_RESIZE = 0xD4

MAX_RESPONSE_LEN = 250

# Initialize the global variable if needed
if SEND_TO_CARD:
    from smartcard.Exceptions import NoCardException
    from smartcard.System import readers
    from smartcard.util import toHexString

    # r=readers()
    # reader = r[ReaderNumber]
    # connection = reader.createConnection()
    # connection.connect()

    r = None
    reader = None
    connection = None

################# END OF CONSTANT ##################

def InitSCard(RNumber):
    global OutputFile, runlog_buffer

    global reader, connection
    if SEND_TO_CARD:
        r = readers()
        if OPT_USE_CLIENT:
            runlog_buffer.append(str(r))
        else:
            print r
        reader = r[RNumber]
        try:
            connection = reader.createConnection()
            connection.connect()
            if OPT_USE_CLIENT:
                runlog_buffer.append(str(reader) + ': ' + str(toHexString(connection.getATR())))
            else:
                print(reader, toHexString(connection.getATR()))
        except NoCardException:
            return -1
            # print(reader, 'no card inserted')
            # if 'win32' == sys.platform:
                # print('press Enter to continue')
                # sys.stdin.read(1)
                # sys.exit()

    if OptWrite2File:
        OutputFile.writelines("\n.POWER_ON")
        OutputFile.writelines('\n')
    
    return 0

response = []
sw1 = 0
sw2 = 0

################  FUNCTIONS   #################

# APDU Header in text or in list of hexadecimal
# APDU data in text (to add support in list)
def SendAPDU(apduheader, apdudata, expResp, expSW, *Condition):
    global response, sw1, sw2, OutputFile, runlog_buffer

    if apdudata != None:
        if type(apdudata) == str:
            apdudata = FilterHexWildCard(apdudata)
        else:
            apdudata = toHexString(apdudata)

    if expResp != None: expResp = FilterHexWildCard(expResp)
    if expSW != None: expSW = FilterHexWildCard(expSW)

    if type(apduheader) == str:
        apduString = FilterHex(apduheader)
    else:
        apduString = toHexString(apduheader)

    if apdudata:
        apduString = apduString + ' ' + FilterHex(apdudata)

    if SEND_TO_CARD:
        if type(apduheader) == str:
            if OPT_USE_CLIENT:
                runlog_buffer.append("Command         : " + str(apduheader))
            else:
                print "Command         : " + apduheader
        else:
            if OPT_USE_CLIENT:
                runlog_buffer.append("Command         : " + str(toHexString(apduheader)))
            else:
                print "Command         : " + toHexString(apduheader)
        if apdudata:
            if OPT_USE_CLIENT:
                runlog_buffer.append("Input Data      : " + str(apdudata))
            else:
                print "Input Data      : " + apdudata
        if type(apduheader) == str:
            apdu = HexString2Bytes(apduheader)
        else:
            apdu = apduheader
        if apdudata:
            apdu = apdu + HexString2Bytes(apdudata)
        response, sw1, sw2 = connection.transmit(apdu)

    # if EXP_FROM_CARD == 1 and expResp == None and SEND_TO_CARD:
    if EXP_FROM_CARD == 1 and SEND_TO_CARD:
        if response != []:
            apduString = apduString + ' [' + toHexString(response).replace(' ', '') + ']'
    else:
        if expResp:
            apduString = apduString + ' [' + FilterHexWildCard(expResp) + ']'

    # if EXP_FROM_CARD == 1 and expSW == None:
    if EXP_FROM_CARD == 1 and SEND_TO_CARD:
        apduString = apduString + ' (%.2X%.2X)' % (sw1, sw2)
    else:
        if expSW:
            apduString = apduString + ' (' + FilterHexWildCard(expSW) + ')'

    if OPT_USE_CLIENT:
        runlog_buffer.append(apduString)
    else:
        print apduString
    if OptWrite2File:
        #        if Condition and Condition == NOT_SAVED:
        if Condition:
            if OPT_USE_CLIENT:
                runlog_buffer.append("APDU not saved in PCOM")
            else:
                print "APDU not saved in PCOM"
        else:
            # if Condition parameter not exist or Condition == SAVED, save to file
            OutputFile.writelines(apduString)
            OutputFile.writelines('\n')

    if SEND_TO_CARD:
        if response:
            if OPT_USE_CLIENT:
                runlog_buffer.append("Output Data     : " + str(toHexString(response)))
            else:
                print "Output Data     : " + toHexString(response)
        else:
            if OPT_USE_CLIENT:
                runlog_buffer.append("Output Data     : none")
            else:
                print "Output Data     : none"

        # Check expected data
        IndexExpected = 0
        IndexResponse = 0
        Diff = False
        DiffList = []

        if expResp != None:
            for a in response:
                if IndexExpected >= len(expResp):
                    # No more data in expected length, stop checking
                    break
                MaskVal = 0xFF
                ByteVal = 0
                if expResp[IndexExpected] == 'X':
                    MaskVal &= 0x0F
                else:
                    ByteVal = int(expResp[IndexExpected], 16) << 4
                IndexExpected += 1
                if IndexExpected != len(expResp):
                    if expResp[IndexExpected] == 'X':
                        MaskVal &= 0xF0
                    else:
                        ByteVal |= int(expResp[IndexExpected], 16)
                if (a & MaskVal) != (ByteVal & MaskVal):
                    Diff = True
                    DiffList.append(IndexResponse)
                IndexExpected += 1
                IndexResponse += 1

            if Diff:
                ERROR("Wrong Expected Response!")
                output = ""
                # print "Expected Data   :",
                IndexResponse = 0
                IndexExpected = 0
                for a in expResp:
                    output += a
                    IndexExpected += 1
                    if IndexExpected % 2 == 0:
                        d2 = False
                        for b in DiffList:
                            if IndexResponse == b:
                                output += "<"
                                d2 = True
                                break
                        if not d2:  # if not the difference
                            output += ' '  # Add space to be more consistent
                        IndexResponse += 1

                # variable
                if tmpContent.startswith('%'): output = output +'\n\n Variable name:'+ tmpContent

                if OPT_USE_CLIENT:
                    runlog_buffer.append("Expected Data   : " + str(output))
                else:
                    print "Expected Data   : " + output

                if OPT_ERROR_FILE: 
                    appendVerifError(curFile, '', curOps, 'Wrong Expected Response', 1, output, curRec, toHexString(response), curFileDescName)

        if OPT_USE_CLIENT:
            runlog_buffer.append("Status          : %.2X %.2X" % (sw1, sw2))
        else:
            print "Status          : %.2X %.2X" % (sw1, sw2)
        # Check expected SW
        IndexExpected = 0
        IndexResponse = 0
        Diff = False
        DiffList = []
        if expSW != None:
            SW = [sw1, sw2]
            for a in SW:
                if IndexExpected >= len(expSW):
                    break
                MaskVal = 0xFF
                ByteVal = 0
                if expSW[IndexExpected] == 'X':
                    MaskVal &= 0x0F
                else:
                    ByteVal = int(expSW[IndexExpected], 16) << 4
                IndexExpected += 1
                if IndexExpected != len(expSW):
                    if expSW[IndexExpected] == 'X':
                        MaskVal &= 0xF0
                    else:
                        ByteVal |= int(expSW[IndexExpected], 16)
                if (a & MaskVal) != (ByteVal & MaskVal):
                    Diff = True
                    DiffList.append(IndexResponse)
                IndexExpected += 1
                IndexResponse += 1

            if Diff:
                ERROR("Wrong Expected SW!")
                output = ""
                # print "Expected SW     :",
                IndexResponse = 0
                IndexExpected = 0
                for a in expSW:
                    output += a
                    IndexExpected += 1
                    if IndexExpected % 2 == 0:
                        d2 = False
                        for b in DiffList:
                            if IndexResponse == b:
                                output += "<"
                                d2 = True
                                break
                        if not d2:  # if not the difference
                            output += ' '  # Add space to be more consistent
                        IndexResponse += 1
                if OPT_USE_CLIENT:
                    runlog_buffer.append("Expected SW     : " + str(output))
                else:
                    print "Expected SW     : " + output
        if OPT_USE_CLIENT:
            runlog_buffer.append("")
        else:
            print ""
    return

def formatFileId(fileId):
    if len(fileId) == 4:
        formatted = fileId
        return formatted
    if len(fileId) == 8:
        formatted = fileId[:4] + '/' + fileId[4:]
        return formatted
    if len(fileId) == 12:
        formatted = fileId[:4] + '/' + fileId[4:8] + '/' + fileId[8:]
        return formatted
    if len(fileId) == 16:
        formatted = fileId[:4] + '/' + fileId[4:8] + '/' + fileId[8:12] + '/' + fileId[12:]
        return formatted

def lineno():
    curFrame = inspect.currentframe()
    frameinfo = inspect.getframeinfo(curFrame)
    print frameinfo.filename, frameinfo.lineno
    return curFrame.f_back.f_lineno

def DEBUGPRINT(x):  # Print debug message
    if DEBUG_ON != 0:
        print x

iSysWarning = 0
iSysError = 0

def WARNING(x):  # Print WARNING message
    global iSysWarning, runlog_buffer
    iSysWarning += 1
    if OPT_USE_CLIENT:
        runlog_buffer.append("WARNING :" + str(x))
    else:
        print '#######################################################'
        print ("WARNING :" + str(x))
        print '#######################################################'

def ERROR(x):  # Print ERROR message
    global iSysError, runlog_buffer
    iSysError += 1
    if OPT_USE_CLIENT:
        runlog_buffer.append("ERROR :" + str(x))
    else:
        print '#######################################################'
        print ("ERROR :" + str(x))
        print '#######################################################'

def RESULT_SUMMARY():
    global runlog_buffer
    if OPT_USE_CLIENT:
        runlog_buffer.append("Number of WARNING :" + str(iSysWarning))
        runlog_buffer.append("Number of ERROR   :" + str(iSysError))
    else:
        print '#######################################################'
        print ("Number of WARNING :" + str(iSysWarning))
        print '#######################################################'
        print '#######################################################'
        print ("Number of ERROR   :" + str(iSysError))
        print '#######################################################'

def FATAL(x):  # Print FATAL ERROR and Exit
    global iSysError, runlog_buffer
    iSysError += 1
    if OPT_USE_CLIENT:
        runlog_buffer.append("FATAL ERROR :" + x)
        runlog_buffer.append('\n')
    else:
        print '#######################################################'
        print ("FATAL ERROR :" + x)
        print '#######################################################'
        print '\n'
    RESULT_SUMMARY()
    if 'win32' == sys.platform:
        # print('press Enter to continue')
        # sys.stdin.read(1)
        sys.exit()

def CheckPrev(cur, prev):
    if cur == '':  # empty?
        if prev != '':
            return prev
            # else:
            #    return -1
    return cur

# Check if the one of the text in the list is found in the Val
#  This will be helpful if the value is like "ADM1 or PIN1"
#   and we would like to know if "PIN1" is part of the value.
#   This will allow to have more than one value in single string/field.
def CheckList(val, list):
    if type(val) == str:
        val = val.upper()
    for a in list:
        # if a == val:
        if type(a) == str:
            temp = a.upper()
        else:
            temp = a
        # if a in val:    # if the text is found in the value
        if temp in val:  # if the text is found in the value
            return True
    return False

# filter string of hexadecimal value, remove unused character
#   do conversion to capital letter for a-f as well
#   return the converted string
def FilterHex(String):
    temp = ''
    String = String.upper()

    for a in String:
        if a >= '0' and a <= '9':
            temp = temp + a
        elif a >= 'A' and a <= 'F':
            temp = temp + a

    return temp

# Filter Hex with additional wildcard 'X'
def FilterHexWildCard(String):
    temp = ''
    String = String.upper()

    for a in String:
        if a >= '0' and a <= '9':
            temp = temp + a
        elif a >= 'A' and a <= 'F':
            temp = temp + a
        elif a == 'X':
            # special handle of ignored value
            temp = temp + a

    # print ("Filtered :" + temp)
    return temp

# filter string of value, remove unused character
#   do conversion to capital letter as well
#   return the converted string
def FilterString(String):
    temp = ''
    String = String.upper()

    Percent = False

    for a in String:
        if Percent:
            # Special handle if '%' sign is found:
            # add the ' ' space separator to indicate the variable name
            if a == ' ':
                Percent = False
                temp = temp + a

        # In other case, the ' ' space are removed
        if a >= '0' and a <= '9':
            temp = temp + a
        elif a >= 'A' and a <= 'Z':
            temp = temp + a
        elif a == '%':
            Percent = True
            # special handle of value with percent sign
            temp = temp + a
        elif a == '=':
            # special handle of equal sign in File Size
            temp = temp + a
        elif a == '&':
            # special handle of equal sign in File Size
            temp = temp + a
        elif a == '|':
            # special handle of equal sign in File Size
            temp = temp + a

    # print ("Filtered :" + temp)
    return temp


# global: curFilePath, prevFilePath
def CheckPrevIfNew(cur, prev):
    # May be empty, does not always get the previous value.
    if curFilePath == prevFilePath:
        # If the file path is the same as the previous one, then check with previous one
        return CheckPrev(cur, prev)
    else:
        # If the file is different, get the new value. Do not use CheckPrev
        return cur

# Convert Access condition text to integer
# Global: iAccUNDEF, sACCALW, iAccCHV1, iAccCHV2, iAccADM1, iAccADM2, iAccNEV
#           sAccUNDEF, sACCALW, sAccCHV1, sAccCHV2, sAccADM1, sAccADM2, sAccNEV
def ConvertACC(cur):
    Temp = []
    if CheckList(cur, sAccALW):
        Temp.append(iAccALW)
    if CheckList(cur, sAccCHV1):
        Temp.append(iAccCHV1)
    if CheckList(cur, sAccCHV2):
        # Temp.append(iAccCHV2)
        Temp.append(iAccSecAPin1) # MS
    if CheckList(cur, sAccADM1):
        Temp.append(iAccADM1)
    if CheckList(cur, sAccADM2):
        Temp.append(iAccADM2)
    if CheckList(cur, sAccADM3):
        Temp.append(iAccADM3)
    if CheckList(cur, sAccADM4):
        Temp.append(iAccADM4)
    if CheckList(cur, sAccADM5):
        Temp.append(iAccADM5)
    if CheckList(cur, sAccNEV):
        Temp.append(iAccNEV)
    if CheckList(cur, sAccAND):
        Temp.append(iAccAND)
    if CheckList(cur, sAccOR):
        Temp.append(iAccOR)
    return Temp

def ConvertACC2G(cur):
    Temp = []

    if CheckList(cur, sAccALW):
        Temp.append(iAccALW)
    if CheckList(cur, sAccCHV1):
        Temp.append(iAccCHV1)
    if CheckList(cur, sAccCHV2):
        Temp.append(iAccCHV2)

    if CheckList(cur, sAccADM1):
        Temp.append(CovertACC3GTo2G(iAccADM1))
    if CheckList(cur, sAccADM2):
        Temp.append(CovertACC3GTo2G(iAccADM2))
    if CheckList(cur, sAccADM3):
        Temp.append(CovertACC3GTo2G(iAccADM3))
    if CheckList(cur, sAccADM4):
        Temp.append(CovertACC3GTo2G(iAccADM4))
    if CheckList(cur, sAccADM5):
        Temp.append(CovertACC3GTo2G(iAccADM5))

    if CheckList(cur, sAccNEV):
        Temp.append(iAccNEV)

    if CheckList(cur, sAccAND):
        Temp.append(iAccAND)
    if CheckList(cur, sAccOR):
        Temp.append(iAccOR)

    return Temp

# Convert hex string to bytes
def HexString2Bytes(String):
    String = FilterHex(String)
    Length = len(String)
    i = Length - 2
    Temp = []
    # Convert from the end to beginning
    while i >= 0:
        Temp.append(int(String[i: i + 2], 16))
        i -= 2
    # handle the last byte if only 1 digit
    if i == -1:
        Temp.append(int(String[0:1], 16))
    # reverse
    i = len(Temp)
    Result = []
    while i > 0:
        i -= 1
        Result.append(Temp[i])
    return Result

# Version 2: use HexString2Bytes() to better handle the odd number of bytes
def ParseARRV2(String):
    index = 0
    ARR = []
    AMDO = None
    SCDO = []
    ListBytes = HexString2Bytes(String)
    while index < len(ListBytes):
        a = ListBytes[index]
        if AMDO != None and a >= 0x80 and a <= 0x8F:
            # AMDO has been set, append AMDO and SCDO to ARR and flush
            ARR.append([AMDO, SCDO])
            AMDO = None
            SCDO = []
        # Access Mode byte
        if a == 0x80:
            index += 1
            Length = ListBytes[index]
            if Length != 1: FATAL("Wrong ARR content")
            index += 1
            val = ListBytes[index]
            AMDO = [a, Length, val]
        elif a >= 0x81 and a <= 0x8F:
            # Command Header Description
            index += 1
            Length = ListBytes[index]
            AMDO = [a, Length]
            i = 0
            while i < Length:
                index += 1
                i += 1
                AMDO.append(ListBytes[index])
        elif a == 0xA0:  # More than 1 SCDO, at least one fulfilled (OR template)
            temp = []
            temp.append(a)
            index += 1  # skip the tag 'A0', the length will be skipped at the end of while loop.
            SCDO.append(temp)
        elif a == 0xAF:  # More than 1 SCDO, at least one fulfilled (OR template)
            temp = []
            temp.append(a)
            index += 1  # skip the tag 'A0', the length will be skipped at the end of while loop.
            SCDO.append(temp)
        elif a == 0x90 or a == 0xA4 or a == 0x97:
            # SCDOs
            temp = []
            temp.append(a)
            index += 1
            Length = ListBytes[index]
            temp.append(Length)
            i = 0
            while i < Length:
                index += 1
                i += 1
                temp.append(ListBytes[index])
            SCDO.append(temp)
        elif a == 0xFF:
            # padding, break.
            break
        else:
            ERROR("Unsupported TLV in ARR")
            break
        index += 1

    if AMDO != None:
        # append last ARR
        ARR.append([AMDO, SCDO])
    return ARR

# Access condition can only be known if the file type is known
# knowing the ARR content cannot determine directly the access condition
# however, we can define a generic data structure for access condition
# ACC data structure in the following order:
siRead_ACC = 0
siUpdate_ACC = 1
siWrite3G_ACC = 2
siIncrease_ACC = 3  # use tag 0x81-0x8F
siDeleteChild_ACC = 4  # according TS102.222 V7.1.0, "Delete File (Child)" shall not be used.
siDeleteSelf_ACC = 5  # equal to delete (for EF) and Delete Self for DF.
siCreateEF_ACC = 6
siCreateDF_ACC = 7
siDeactivate_ACC = 8
siActivate_ACC = 9
siTerminate_ACC = 10
siResize_ACC = 11
siCustom_ACC = 12  # List of [CLA, INS, P1, P2]

#   TS102.221 indicate multiple security condition should be 'OR' condition.
#   input: arr, file type
def ARR2ACC(arr, Type):
    TempAcc = [[], [], [], [], [], [], [], [], [], [], [], [], []]
    # First get the list of access mode defined in AMDO
    CustomAccNumber = 0
    for a in arr:
        AccTypeList = []
        if a[0][0] == 0x80:
            # Access Mode byte
            val = a[0][2]
            # convert the access type based on the file type. Can be more than 1.
            if CheckList(Type, sFileTypeMF) or \
                    CheckList(Type, sFileTypeDF) or \
                    CheckList(Type, sFileTypeADF):
                if a[0][2] & 0x04:
                    AccTypeList.append(siCreateDF_ACC)
                if a[0][2] & 0x02:
                    AccTypeList.append(siCreateEF_ACC)
                if a[0][2] & 0x01:
                    AccTypeList.append(siDeleteChild_ACC)
                if a[0][2] & 0x80:
                    # only 3 bits
                    pass
                else:
                    # 7 bits
                    if a[0][2] & 0x08:
                        AccTypeList.append(siDeactivate_ACC)
                    if a[0][2] & 0x10:
                        AccTypeList.append(siActivate_ACC)
                    if a[0][2] & 0x20:
                        AccTypeList.append(siTerminate_ACC)
                    if a[0][2] & 0x40:
                        AccTypeList.append(siDeleteSelf_ACC)
            else:
                # handle for EF
                if a[0][2] & 0x04:
                    AccTypeList.append(siWrite3G_ACC)
                if a[0][2] & 0x02:
                    AccTypeList.append(siUpdate_ACC)
                if a[0][2] & 0x01:
                    AccTypeList.append(siRead_ACC)
                if a[0][2] & 0x80:
                    # only 3 bits
                    pass
                else:
                    # 7 bits
                    if a[0][2] & 0x08:
                        AccTypeList.append(siDeactivate_ACC)
                    if a[0][2] & 0x10:
                        AccTypeList.append(siActivate_ACC)
                    if a[0][2] & 0x20:
                        AccTypeList.append(siTerminate_ACC)
                    if a[0][2] & 0x40:
                        AccTypeList.append(siDeleteSelf_ACC)
        elif a[0][0] >= 0x81 and a[0][0] <= 0x8F:
            # Custom access condition, convert to access type
            apdu = [None, None, None, None]  # CLA, INS, P1, P2
            b = 2
            if a[0][0] & 0x08:
                apdu[0] = a[0][b]
                b += 1
            if a[0][0] & 0x04:
                apdu[1] = a[0][b]
                b += 1
            if a[0][0] & 0x02:
                apdu[2] = a[0][b]
                b += 1
            if a[0][0] & 0x01:
                apdu[3] = a[0][b]
                b += 1
            # Check for increase
            if apdu[1] == INS_INCREASE:
                AccTypeList.append(siIncrease_ACC)
            else:
                AccTypeList.append(siCustom_ACC)
                TempAcc[siCustom_ACC].append(apdu)
                CustomAccNumber += 1
            # Check for resize ;additional still on test
            if apdu[1] == INS_RESIZE:
                AccTypeList.append(siResize_ACC)
            else:
                AccTypeList.append(siCustom_ACC)
                TempAcc[siCustom_ACC].append(apdu)
                CustomAccNumber += 1

        # get SCDO (can be more than 1 SCDO)
        SecurityCondition = iAccUNDEF
        for b in a[1]:
            if b[0] == 0x90:
                # Always
                SecurityCondition = iAccALW
            elif b[0] == 0x97:
                # Never
                SecurityCondition = iAccNEV
            elif b[0] == 0xA4:  # A4 06 83 01 Val 95 01 08
                # Other
                SecurityCondition = b[4]
            elif b[0] == 0xA0:
                # Or
                SecurityCondition = iAccOR
            elif b[0] == 0xAF:
                # And
                SecurityCondition = iAccAND
            else:
                FATAL("Invalid SCDO")
            # Set all access mode with the security condition defined in the current SCDO
            # support multiple SC on one access mode.
            for c in AccTypeList:
                if c == siCustom_ACC:
                    # apdu.append(SecurityCondition)
                    TempAcc[c][CustomAccNumber - 1].append(SecurityCondition)

                    # TempAcc[c] = apdu
                else:
                    TempAcc[c].append(SecurityCondition)
                    # TempAcc[c] = SecurityCondition

    return TempAcc

def SearchTLV(Tag, ListBytes):
    Length = len(ListBytes)
    i = 0
    TempResult = []
    while i < Length:
        TempResult.append(ListBytes[i])  # Tag
        i += 1
        j = 0
        Length2 = ListBytes[i]
        TempResult.append(ListBytes[i])  # Length
        i += 1
        while j < Length2:
            TempResult.append(ListBytes[i])  # Value
            i += 1
            j += 1

        # DEBUGPRINT("TempResult: " + str(TempResult))
        if Tag == TempResult[0]:
            break
        else:
            TempResult = []
    return TempResult

def CmdSelect3G(path, expRes, expSw):
    # Select the parents, no need to check the result
    path = FilterHex(path)
    i = 0
    while i < (len(path) - 4):
        Header = copy.deepcopy(SELECT3G)
        # SendAPDU2(Header,path[i:i+4], None, "61XX")
        SendAPDU(Header, path[i:i + 4], None, "61XX")
        i += 4
    # Select The last one, check the result
    Header = copy.deepcopy(SELECT3G)
    # SendAPDU2(Header,path[i:], None, "61xx")
    SendAPDU(Header, path[i:], None, "61xx")
    Header = copy.deepcopy(GETRESP3G)
    Header[4] = sw2
    # SendAPDU2(Header,None, expRes, expSw)
    SendAPDU(Header, None, expRes, expSw)

def CmdSelect3G_not_recorded(path, expRes, expSw):
    # Select the parents, no need to check the result
    path = FilterHex(path)
    i = 0
    while i < (len(path) - 4):
        Header = copy.deepcopy(SELECT3G)
        # SendAPDU2(Header,path[i:i+4], None, "61XX")
        SendAPDU(Header, path[i:i + 4], None, "61XX", NOT_SAVED)
        i += 4
    # Select The last one, check the result
    Header = copy.deepcopy(SELECT3G)
    # SendAPDU2(Header,path[i:], None, "61xx")
    SendAPDU(Header, path[i:], None, "61xx", NOT_SAVED)
    Header = copy.deepcopy(GETRESP3G)
    Header[4] = sw2
    # SendAPDU2(Header,None, expRes, expSw)
    SendAPDU(Header, None, expRes, expSw, NOT_SAVED)


SELECT3G = [0x00, 0xA4, 0x00, 0x04, 0x02]
GETRESP3G = [0x00, 0xC0, 0x00, 0x00, 0x0F]

SELECT2G = "A0A4000002"
GETRESP2G = "A0C000000F"
DF_TELECOM = "7F10"

UPDATEBIN2G = [0xA0, 0xD6, 0x00, 0x00, 0x00]
READBIN2G = [0xA0, 0xB0, 0x00, 0x00, 0x00]

UPDATEREC2G = [0xA0, 0xDC, 0x00, 0x00, 0x00]
READREC2G = [0xA0, 0xB2, 0x00, 0x00, 0x00]

READHEADER2G = [0xA0, 0xE8, 0x00, 0x00, 0x17]


def CmdReadHeader2G(Number, Mode, expRes, expSw, *Condition):
    Header = copy.deepcopy(READHEADER2G)
    # Make Sure Offset is not longer than 64K-1
    Header[2] = int(Number)
    Header[3] = int(Mode)

    # SendAPDU2(Header,None, expRes, expSw)
    if Condition:
        SendAPDU(Header, None, expRes, expSw, Condition)
    else:
        SendAPDU(Header, None, expRes, expSw)

def CmdSelect2G(path, expRes, expSw, *Condition):
    # Select the parents, no need to check the result
    path = FilterHex(path)
    i = 0
    while i < (len(path) - 4):
        if Condition:
            SendAPDU(SELECT2G, path[i:i + 4], None, None, Condition)
        else:
            SendAPDU(SELECT2G, path[i:i + 4], None, None)
        i += 4
    # Select The last one, check the result
    if Condition:
        SendAPDU(SELECT2G, path[i:], None, "9Fxx", Condition)
        SendAPDU(GETRESP2G, None, expRes, expSw, Condition)
    else:
        SendAPDU(SELECT2G, path[i:], None, "9Fxx")
        SendAPDU(GETRESP2G, None, expRes, expSw)

def CmdReadBinary2G(Offset, Le, expRes, expSw, *Condition):
    Header = copy.deepcopy(READBIN2G)
    # Make Sure Offset is not longer than 64K-1
    Header[2] = ((int(Offset) % 0x10000) >> 8)
    Header[3] = (int(Offset) % 0x10000) & 0x00FF

    # Make Sure Length is not longer than 255
    Header[4] = int(Le) % 0x100
    # SendAPDU2(Header,None, expRes, expSw)
    if Condition:
        SendAPDU(Header, None, expRes, expSw, Condition)
    else:
        SendAPDU(Header, None, expRes, expSw)

def CmdUpdateBinary2G(Offset, Lc, Data, expSw, *Condition):
    Header = copy.deepcopy(UPDATEBIN2G)
    # Make Sure Offset is not longer than 64K-1
    Header[2] = ((int(Offset) % 0x10000) >> 8)
    Header[3] = (int(Offset) % 0x10000) & 0x00FF

    # Make Sure Length is not longer than 255
    Header[4] = int(Lc) % 0x100
    # SendAPDU2(Header,Data, None, expSw)
    if Condition:
        SendAPDU(Header, Data, None, expSw, Condition)
    else:
        SendAPDU(Header, Data, None, expSw)

def CmdReadRecord2G(RecordNumber, Mode, Le, expRes, expSw, *Condition):
    Header = copy.deepcopy(READREC2G)
    # Make Sure Offset is not longer than 64K-1
    Header[2] = int(RecordNumber) % 0x100
    Header[3] = int(Mode) % 0x100

    # Make Sure Length is not longer than 255
    Header[4] = int(Le) % 0x100
    # SendAPDU2(Header,None, expRes, expSw)
    if Condition:
        SendAPDU(Header, None, expRes, expSw, Condition)
    else:
        SendAPDU(Header, None, expRes, expSw)

def CmdUpdateRecord2G(RecordNumber, Mode, Lc, Data, expSw, *Condition):
    Header = copy.deepcopy(UPDATEREC2G)
    # Make Sure Offset is not longer than 64K-1
    Header[2] = int(RecordNumber) % 0x100
    Header[3] = int(Mode) % 0x100

    # Make Sure Length is not longer than 255
    Header[4] = int(Lc) % 0x100
    # SendAPDU2(Header,Data, None, expSw)
    if Condition:
        SendAPDU(Header, Data, None, expSw, Condition)
    else:
        SendAPDU(Header, Data, None, expSw)

# UPDATE COMMAND 3G
GETRESP3GADF = [0x00, 0xC0, 0x00, 0x00, 0x1C]
UPDATEBIN3G = [0x00, 0xD6, 0x00, 0x00, 0x00]
READBIN3G = [0x00, 0xB0, 0x00, 0x00, 0x00]
UPDATEREC3G = [0x00, 0xDC, 0x00, 0x00, 0x00]
READREC3G = [0x00, 0xB2, 0x00, 0x00, 0x00]

def CmdSelect3GADF(aid_length):
    # Select the parents, no need to check the result
    Header = copy.deepcopy(SELECT3GADF)
    Header[4] = aid_length
    SendAPDU(Header, ADF_AID, None, "61XX")

def CmdReadBinary3G(Offset, Le, expRes, expSw, *Condition):
    Header = copy.deepcopy(READBIN3G)
    # Make Sure Offset is not longer than 64K-1
    Header[2] = ((int(Offset) % 0x10000) >> 8)
    Header[3] = (int(Offset) % 0x10000) & 0x00FF

    # Make Sure Length is not longer than 255
    Header[4] = int(Le) % 0x100
    # SendAPDU2(Header,None, expRes, expSw)
    if Condition:
        SendAPDU(Header, None, expRes, expSw, Condition)
    else:
        SendAPDU(Header, None, expRes, expSw)

def CmdUpdateBinary3G(Offset, Lc, Data, expSw, *Condition):
    Header = copy.deepcopy(UPDATEBIN3G)
    # Make Sure Offset is not longer than 64K-1
    Header[2] = ((int(Offset) % 0x10000) >> 8)
    Header[3] = (int(Offset) % 0x10000) & 0x00FF

    # Make Sure Length is not longer than 255
    Header[4] = int(Lc) % 0x100
    # SendAPDU2(Header,Data, None, expSw)
    if Condition:
        SendAPDU(Header, Data, None, expSw, Condition)
    else:
        SendAPDU(Header, Data, None, expSw)

def CmdReadRecord3G(RecordNumber, Mode, Le, expRes, expSw, *Condition):
    Header = copy.deepcopy(READREC3G)
    # Make Sure Offset is not longer than 64K-1
    Header[2] = int(RecordNumber) % 0x100
    Header[3] = int(Mode) % 0x100

    # Make Sure Length is not longer than 255
    Header[4] = int(Le) % 0x100
    # SendAPDU2(Header,None, expRes, expSw)
    if Condition:
        SendAPDU(Header, None, expRes, expSw, Condition)
    else:
        SendAPDU(Header, None, expRes, expSw)

def CmdUpdateRecord3G(RecordNumber, Mode, Lc, Data, expSw, *Condition):
    Header = copy.deepcopy(UPDATEREC3G)
    # Make Sure Offset is not longer than 64K-1
    Header[2] = int(RecordNumber) % 0x100
    Header[3] = int(Mode) % 0x100

    # Make Sure Length is not longer than 255
    Header[4] = int(Lc) % 0x100
    # SendAPDU2(Header,Data, None, expSw)
    if Condition:
        SendAPDU(Header, Data, None, expSw, Condition)
    else:
        SendAPDU(Header, Data, None, expSw)

# END OF UPDATE COMMAND 3G

def FileType2G(string):
    if CheckList(string, sFileTypeMF): return "01"
    if CheckList(string, sFileTypeDF): return "02"
    if CheckList(string, sFileTypeEF): return "04"
    ERROR("Invalid 2G File Type")
    return "XX"

def FileStructure2G(string):
    if CheckList(string, sFileStructTR): return "00"
    if CheckList(string, sFileStructLF): return "01"
    if CheckList(string, sFileStructCY): return "03"
    ERROR("Invalid 2G File Structure")
    return "XX"

def appendVerifError(fileId, linkedfile, operation, errMsg, severity, expected, recNum, output, fileName):
    global verificationErrors

    verificationErrors.append({'fileId': fileId, \
                               'linkedFile': linkedfile, \
                               'operation': operation, \
                               'errMsg': errMsg, \
                               'severity': severity, \
                               'expected': expected, \
                               'recNum': recNum, \
                               'output': output, \
                               'fileName': fileName})

def booleanStrToInt(booleanStr):
    if str(booleanStr) == 'true':
        return 1
    else:
        return 0

def literalStrToList(literalStr):
    tmpList = str(literalStr).split(';')
    resultList = []
    for item in tmpList:
        resultList.append(str(item))
    return resultList

def parseConfigXml():
    global FileName
    global OutputFileName
    global FullScriptFileName
    global ErrorFileName
    global VariablesFileName
    global ReaderNumber
    global OPT_CHV1_DISABLED
    global OPT_HEX_RECORDNUMBER
    global OPT_HEX_SFI
    global OPT_USE_VARIABLES
    global OPT_USE_ADM2
    global OPT_USE_ADM3
    global OPT_USE_ADM4
    global ADM1
    global ADM2
    global ADM3
    global ADM4
    global CHV1
    global CHV2
    global sFileStructTR
    global sFileStructLF
    global sFileStructCY
    global sFileStructLK
    global sAccALW
    global sAccCHV1
    global sAccCHV2
    global sAccADM1
    global sAccADM2
    global sAccADM3
    global sAccADM4
    global sAccADM5
    global sAccADM6
    global sAccADM7
    global sAccADM8
    global sAccNEV
    global sAccAND
    global sAccOR
    global verify2gAdm1p1
    global verify2gAdm1p2
    global verify2gAdm1p3
    global verify2gAdm2p1
    global verify2gAdm2p2
    global verify2gAdm2p3
    global verify2gAdm3p1
    global verify2gAdm3p2
    global verify2gAdm3p3
    global verify2gAdm4p1
    global verify2gAdm4p2
    global verify2gAdm4p3
    global verify2gChv1p1
    global verify2gChv1p2
    global verify2gChv1p3
    global verify2gChv2p1
    global verify2gChv2p2
    global verify2gChv2p3
    global verify3gAdm1p1
    global verify3gAdm1p2
    global verify3gAdm1p3
    global verify3gAdm2p1
    global verify3gAdm2p2
    global verify3gAdm2p3
    global verify3gAdm3p1
    global verify3gAdm3p2
    global verify3gAdm3p3
    global verify3gAdm4p1
    global verify3gAdm4p2
    global verify3gAdm4p3
    global verify3gGlobalPin1p1
    global verify3gGlobalPin1p2
    global verify3gGlobalPin1p3
    global verify3gLocalPin1p1
    global verify3gLocalPin1p2
    global verify3gLocalPin1p3
    global OPT_SELECT3G_ADF
    global OPT_CHECK_CONTENT_3G
    global OPT_CHECK_LINK3G
    global ADF_AID
    global ADF_AID_LENGTH

    config_file = 'config.xml'
    try:
        DOMTree = parse(config_file)
    except IOError, e:
        return False, 'Error parsing config.xml: ' + str(e.strerror)

    verifConfig = DOMTree.documentElement

    ReaderNumber = int(verifConfig.getElementsByTagName('readerNumber')[0].childNodes[0].data)
    if ReaderNumber == -1:
        return False, 'no terminal/reader detected'
    else:
        # options
        OPT_CHV1_DISABLED = booleanStrToInt(verifConfig.getAttribute('chv1Disabled'))
        OPT_HEX_RECORDNUMBER = booleanStrToInt(verifConfig.getAttribute('hexRecordNumber'))
        OPT_HEX_SFI = booleanStrToInt(verifConfig.getAttribute('hexSfi'))
        OPT_USE_VARIABLES = booleanStrToInt(verifConfig.getAttribute('useVariablesTxt'))
        OPT_USE_ADM2 = booleanStrToInt(verifConfig.getAttribute('useAdm2'))
        OPT_USE_ADM3 = booleanStrToInt(verifConfig.getAttribute('useAdm3'))
        OPT_USE_ADM4 = booleanStrToInt(verifConfig.getAttribute('useAdm4'))
        OPT_CHECK_CONTENT_3G = booleanStrToInt(verifConfig.getAttribute('usimIn3GMode'))

        # hotfix in verifclient v0.0.5: this option will be kept 'false'
        if OPT_CHECK_CONTENT_3G:
            OPT_SELECT3G_ADF = 0
            OPT_CHECK_LINK3G = 1
        else:
            OPT_SELECT3G_ADF = 0
            OPT_CHECK_LINK3G = 0
        
        ADF_AID = str(verifConfig.getElementsByTagName('usimAid')[0].childNodes[0].data)
        ADF_AID_LENGTH = len(ADF_AID) / 2

        FileName = str(verifConfig.getElementsByTagName('pathToCsv')[0].childNodes[0].data)
        csvName = os.path.basename(FileName)
        FilePath = os.path.dirname(FileName)
        OutputFileName = os.path.join(FilePath, csvName[:-4]) + '.txt'
        ErrorFileName = os.path.join(FilePath, csvName[:-4]) + '_error.html'
        FullScriptFileName = os.path.join(FilePath, csvName[:-4]) + '_FULLSCRIPT.pcom'

        if OPT_USE_VARIABLES:
            VariablesFileName = str(verifConfig.getElementsByTagName('pathToVariablesTxt')[0].childNodes[0].data)

        # security codes
        ADM1 = str(verifConfig.getElementsByTagName('codeAdm1')[0].childNodes[0].data)
        if OPT_USE_ADM2:
            ADM2 = str(verifConfig.getElementsByTagName('codeAdm2')[0].childNodes[0].data)
        if OPT_USE_ADM3:
            ADM3 = str(verifConfig.getElementsByTagName('codeAdm3')[0].childNodes[0].data)
        if OPT_USE_ADM4:
            ADM4 = str(verifConfig.getElementsByTagName('codeAdm4')[0].childNodes[0].data)
        CHV1 = str(verifConfig.getElementsByTagName('codeChv1')[0].childNodes[0].data)
        CHV2 = str(verifConfig.getElementsByTagName('codeChv2')[0].childNodes[0].data)

        # literals
        verifLiterals = verifConfig.getElementsByTagName('verifLiterals')[0]
        sFileStructTR = literalStrToList(verifLiterals.getElementsByTagName('sFileStructTR')[0].childNodes[0].data)
        sFileStructLF = literalStrToList(verifLiterals.getElementsByTagName('sFileStructLF')[0].childNodes[0].data)
        sFileStructCY = literalStrToList(verifLiterals.getElementsByTagName('sFileStructCY')[0].childNodes[0].data)
        sFileStructLK = literalStrToList(verifLiterals.getElementsByTagName('sFileStructLK')[0].childNodes[0].data)
        sAccALW = literalStrToList(verifLiterals.getElementsByTagName('sAccALW')[0].childNodes[0].data)
        sAccCHV1 = literalStrToList(verifLiterals.getElementsByTagName('sAccCHV1')[0].childNodes[0].data)
        sAccCHV2 = literalStrToList(verifLiterals.getElementsByTagName('sAccCHV2')[0].childNodes[0].data)
        sAccADM1 = literalStrToList(verifLiterals.getElementsByTagName('sAccADM1')[0].childNodes[0].data)
        sAccADM2 = literalStrToList(verifLiterals.getElementsByTagName('sAccADM2')[0].childNodes[0].data)
        sAccADM3 = literalStrToList(verifLiterals.getElementsByTagName('sAccADM3')[0].childNodes[0].data)
        sAccADM4 = literalStrToList(verifLiterals.getElementsByTagName('sAccADM4')[0].childNodes[0].data)
        sAccADM5 = literalStrToList(verifLiterals.getElementsByTagName('sAccADM5')[0].childNodes[0].data)
        sAccADM6 = literalStrToList(verifLiterals.getElementsByTagName('sAccADM6')[0].childNodes[0].data)
        sAccADM7 = literalStrToList(verifLiterals.getElementsByTagName('sAccADM7')[0].childNodes[0].data)
        sAccADM8 = literalStrToList(verifLiterals.getElementsByTagName('sAccADM8')[0].childNodes[0].data)
        sAccNEV = literalStrToList(verifLiterals.getElementsByTagName('sAccNEV')[0].childNodes[0].data)
        sAccAND = literalStrToList(verifLiterals.getElementsByTagName('sAccAND')[0].childNodes[0].data)
        sAccOR = literalStrToList(verifLiterals.getElementsByTagName('sAccOR')[0].childNodes[0].data)

        # custom APDU
        customApdu = verifConfig.getElementsByTagName('customApdu')[0]
        customVerify2g = customApdu.getElementsByTagName('verify2g')[0]
        customVerify3g = customApdu.getElementsByTagName('verify3g')[0]

        customVerify2gAdm1 = customVerify2g.getElementsByTagName('verify2gAdm1')[0]
        customVerify2gAdm2 = customVerify2g.getElementsByTagName('verify2gAdm2')[0]
        customVerify2gAdm3 = customVerify2g.getElementsByTagName('verify2gAdm3')[0]
        customVerify2gAdm4 = customVerify2g.getElementsByTagName('verify2gAdm4')[0]
        customVerify2gChv1 = customVerify2g.getElementsByTagName('verify2gChv1')[0]
        customVerify2gChv2 = customVerify2g.getElementsByTagName('verify2gChv2')[0]

        customVerify3gAdm1 = customVerify3g.getElementsByTagName('verify3gAdm1')[0]
        customVerify3gAdm2 = customVerify3g.getElementsByTagName('verify3gAdm2')[0]
        customVerify3gAdm3 = customVerify3g.getElementsByTagName('verify3gAdm3')[0]
        customVerify3gAdm4 = customVerify3g.getElementsByTagName('verify3gAdm4')[0]
        customVerify3gGlobalPin1 = customVerify3g.getElementsByTagName('verify3gGlobalPin1')[0]
        customVerify3gLocalPin1 = customVerify3g.getElementsByTagName('verify3gLocalPin1')[0]

        verify2gAdm1p1 = int(customVerify2gAdm1.getAttribute('p1'), 16)
        verify2gAdm1p2 = int(customVerify2gAdm1.getAttribute('p2'), 16)
        verify2gAdm1p3 = int(customVerify2gAdm1.getAttribute('p3'), 16)

        verify2gAdm2p1 = int(customVerify2gAdm2.getAttribute('p1'), 16)
        verify2gAdm2p2 = int(customVerify2gAdm2.getAttribute('p2'), 16)
        verify2gAdm2p3 = int(customVerify2gAdm2.getAttribute('p3'), 16)

        verify2gAdm3p1 = int(customVerify2gAdm3.getAttribute('p1'), 16)
        verify2gAdm3p2 = int(customVerify2gAdm3.getAttribute('p2'), 16)
        verify2gAdm3p3 = int(customVerify2gAdm3.getAttribute('p3'), 16)

        verify2gAdm4p1 = int(customVerify2gAdm4.getAttribute('p1'), 16)
        verify2gAdm4p2 = int(customVerify2gAdm4.getAttribute('p2'), 16)
        verify2gAdm4p3 = int(customVerify2gAdm4.getAttribute('p3'), 16)

        verify2gChv1p1 = int(customVerify2gChv1.getAttribute('p1'), 16)
        verify2gChv1p2 = int(customVerify2gChv1.getAttribute('p2'), 16)
        verify2gChv1p3 = int(customVerify2gChv1.getAttribute('p3'), 16)

        verify2gChv2p1 = int(customVerify2gChv2.getAttribute('p1'), 16)
        verify2gChv2p2 = int(customVerify2gChv2.getAttribute('p2'), 16)
        verify2gChv2p3 = int(customVerify2gChv2.getAttribute('p3'), 16)

        verify3gAdm1p1 = int(customVerify3gAdm1.getAttribute('p1'), 16)
        verify3gAdm1p2 = int(customVerify3gAdm1.getAttribute('p2'), 16)
        verify3gAdm1p3 = int(customVerify3gAdm1.getAttribute('p3'), 16)

        verify3gAdm2p1 = int(customVerify3gAdm2.getAttribute('p1'), 16)
        verify3gAdm2p2 = int(customVerify3gAdm2.getAttribute('p2'), 16)
        verify3gAdm2p3 = int(customVerify3gAdm2.getAttribute('p3'), 16)

        verify3gAdm3p1 = int(customVerify3gAdm3.getAttribute('p1'), 16)
        verify3gAdm3p2 = int(customVerify3gAdm3.getAttribute('p2'), 16)
        verify3gAdm3p3 = int(customVerify3gAdm3.getAttribute('p3'), 16)

        verify3gAdm4p1 = int(customVerify3gAdm4.getAttribute('p1'), 16)
        verify3gAdm4p2 = int(customVerify3gAdm4.getAttribute('p2'), 16)
        verify3gAdm4p3 = int(customVerify3gAdm4.getAttribute('p3'), 16)

        verify3gGlobalPin1p1 = int(customVerify3gGlobalPin1.getAttribute('p1'), 16)
        verify3gGlobalPin1p2 = int(customVerify3gGlobalPin1.getAttribute('p2'), 16)
        verify3gGlobalPin1p3 = int(customVerify3gGlobalPin1.getAttribute('p3'), 16)

        verify3gLocalPin1p1 = int(customVerify3gLocalPin1.getAttribute('p1'), 16)
        verify3gLocalPin1p2 = int(customVerify3gLocalPin1.getAttribute('p2'), 16)
        verify3gLocalPin1p3 = int(customVerify3gLocalPin1.getAttribute('p3'), 16)

        if opt_debugprint_client_variables:
            print 'ReaderNumber: ' + str(ReaderNumber)

            print 'OPT_CHV1_DISABLED: ' + str(OPT_CHV1_DISABLED)
            print 'OPT_HEX_RECORDNUMBER: ' + str(OPT_HEX_RECORDNUMBER)
            print 'OPT_HEX_SFI: ' + str(OPT_HEX_SFI)
            print 'OPT_USE_VARIABLES: ' + str(OPT_USE_VARIABLES)
            print 'OPT_CHECK_CONTENT_3G: ' + str(OPT_CHECK_CONTENT_3G)
            print 'OPT_SELECT3G_ADF: ' + str(OPT_SELECT3G_ADF)
            print 'ADF_AID: ' + ADF_AID
            print 'ADF_AID_LENGTH: ' + str(ADF_AID_LENGTH)

            print 'ADM1: ' + str(ADM1)
            if OPT_USE_ADM2:
                print 'ADM2: ' + str(ADM2)
            if OPT_USE_ADM3:
                print 'ADM3: ' + str(ADM3)
            if OPT_USE_ADM4:
                print 'ADM4: ' + str(ADM4)
            print 'CHV1: ' + str(CHV1)
            print 'CHV2: ' + str(CHV2)
            print 'FileName: ' + FileName
            print 'OutputFileName: ' + OutputFileName
            print 'FullScriptFileName: ' + FullScriptFileName
            print 'ErrorFileName: ' + ErrorFileName
            print 'VariablesFileName: ' + VariablesFileName

            print 'sFileStructTR: ' + str(sFileStructTR)
            print 'sFileStructLF: ' + str(sFileStructLF)
            print 'sFileStructCY: ' + str(sFileStructCY)
            print 'sFileStructLK: ' + str(sFileStructLK)
            print 'sAccALW: ' + str(sAccALW)
            print 'sAccCHV1: ' + str(sAccCHV1)
            print 'sAccCHV2: ' + str(sAccCHV2)
            print 'sAccADM1: ' + str(sAccADM1)
            print 'sAccADM2: ' + str(sAccADM2)
            print 'sAccADM3: ' + str(sAccADM3)
            print 'sAccADM4: ' + str(sAccADM4)
            print 'sAccADM5: ' + str(sAccADM5)
            print 'sAccADM6: ' + str(sAccADM6)
            print 'sAccADM7: ' + str(sAccADM7)
            print 'sAccADM8: ' + str(sAccADM8)
            print 'sAccNEV: ' + str(sAccNEV)
            print 'sAccAND: ' + str(sAccAND)
            print 'sAccOR: ' + str(sAccOR)

        return True, 'Parsing config.xml complete'

# command line progress bar by vladignatyev (https://gist.github.com/vladignatyev/06860ec2040cb497f0f3)
def progress(count, total, status=''):
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))

    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    sys.stdout.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
    sys.stdout.flush()

def createDocumentHeader():
    global ErrorFile

    ErrorFile.writelines("""<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
        <html>
        <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
        <title>Error Report</title>
        <script>
		    function doCount(text) {
		        var sel = window.getSelection();
				sel.collapse(document.body, 0);
		        var cnt = 0;
		        while (window.find(text)) {
		            cnt = cnt + 1;
		        }
		        sel.collapse(document.body, 0);
		        return cnt;
		    }

			function doSearch(text) {
				document.designMode = "on";
				window.find(text);
				document.execCommand("HiliteColor", false, "yellow");
				document.designMode = "off";
			}

			function doClear(text) {
				if (window.find) {
				    var sel = window.getSelection();
					sel.collapse(document.body, 0);
					document.designMode = "on";
					while (window.find(text)) {
						document.execCommand("HiliteColor", false, "transparent");
					}
					document.designMode = "off";
					sel.collapse(document.body, 0);
				}
			}
        </script>
        <style type="text/css">
        html,
        body {
          height: 100%;
        }
        html {
          font-size: 16px;
        }
        body {
            margin: 0px;
            padding: 0px;
            overflow-x: hidden;
            min-width: 320px;
            background: #F9F9F9;
            font-family: calibri;
            font-size: 13px;
            line-height: 1.33;
            color: #212121;
            font-smoothing: antialiased;
        }
        div {
            margin-top: 20px;
            margin-left: 40px;
            margin-right: 40px;
        }
        h1,
        h2,
        h3,
        h4,
        h5 {
          font-family: calibri;
          line-height: 1.33em;
          margin: calc(2rem -  0.165em ) 0em 1rem;
          font-weight: 400;
          padding: 0em;
        }
        table {
            border-collapse: collapse;
        }
        th,
        td {
            border: 1px solid gray;
            padding: 5px;
        }
        th.error {
            background-color: firebrick;
            color: #F9F9F9;
        }
        th.warning {
            background-color: darkorange;
            color: #F9F9F9;
        }
        td.error {
            background-color: #FDEDEC;
            color: #17202A;
        }
        td.warning {
            background-color: #FEF9E7;
            color: #17202A;
        }
        td.data {
            font-family: consolas;
            font-size: 11px;
        }
        mark.varname {
            color:maroon;
            background-color:cornsilk;
            font-family:consolas;
            font-size: 11px;
        }
        </style>
        </head>
        <body>""")

def createDocumentFooter():
    global ErrorFile
    ErrorFile.writelines('</body></html>')

def createTableHeader():
    global ErrorFile
    ErrorFile.writelines('<div><table><tbody>')

def createTableFooter():
    global ErrorFile
    ErrorFile.writelines('</tbody></table></div>')

# highlight error bytes with red
def markErrorByte(out, exp):
    outb = []
    expb = []

    for a in range(0, len(out.replace(' ', '')), 2):
        outb.append(out.replace(' ', '')[a:a + 2])

    if not exp.startswith('%'):
        for b in range(0, len(exp.replace(' ', '')), 2):
            expb.append(exp.replace(' ', '')[b:b + 2])

        i = 0
        for byte in outb:
            try:
                if expb[i] == 'XX' or byte == expb[i]:
                    i += 1
                    continue
                outb[i] = '<span style="color: #ff0000">' + byte + '</span>'
                i += 1
            except IndexError:
                return 'bad data/content'

        outb_str = ''
        for byte in outb:
            outb_str += byte + ' '

    else:
        outb_str = '<span style="color: #ff0000">' + out + '</span>'

    return outb_str

def run(useClient=False):
    # 'useClient' switch is for enabling printing to stdout or to a file.
    global OPT_USE_CLIENT
    OPT_USE_CLIENT = useClient

    global EXP_FROM_CARD

    global OutputFile, fiContent, curFilePath, prevFilePath, curFile, curOps, curRec, curFileDescName, \
        verificationErrors, ErrorFile, runlog_buffer, runLog, tmpContent
    
    global efMarker

    ### START OF RUN BLOCK ###

    # CmdVerify2G(pin
    # CmdReadBinary2G
    # CmdUpdateBinary2G
    # CmdReadRecord2G
    # CmdUpdateRecord2G

    ################  END OF FUNCTIONS   #################

    ###############################################
    # File List Structure:
    #   - FilePathID Path to FileID, starting from MF. MF (3F00) MUST BE THE FIRST.
    #   - FileSFI
    #   - LinkTo (FilePath, same as in FilePathID)
    #   - Mandatory
    #   - UpdateActivity
    #   - FileType
    #   - FIleStruct
    #   - Shareable
    #   - File Size
    #   - RecordSize
    #   - NumberOfRecord
    #   - Read_ACC
    #   - Update_ACC
    #   - Increase_ACC
    #   - Rehabilitate_ACC
    #   - Invalidate_ACC
    #   - Read3G_ACC
    #   - Update3G_ACC
    #   - Increase3G_ACC
    #   - DeleteChild_ACC
    #   - DeleteSelf_ACC
    #   - CreateEF_ACC
    #   - CreateDF_ACC
    #   - Deactivate_ACC
    #   - Activate_ACC
    #   - Terminate_ACC
    #   - Custom_ACC List of custom access condition. None if no custom access condition
    #   - OTAAccess
    #   - ADF_AID
    #   - ListOfContent -> List of List with RecordNumber (integer) and Content in hexadecimal string.
    #                       Record Number '0' means undefined
    #                       '%' indicate a variable
    #	- ResizeACC

    FileList = []
    FieldList = []

    fiFilePathID = 0
    fiFileSFI = 1
    fiLinkTo = 2
    fiMandatory = 3
    fiUpdateActivity = 4
    fiFileType = 5
    fiFIleStruct = 6
    fiShareable = 7
    fiFileSize = 8
    fiRecordSize = 9
    fiNumberOfRecord = 10
    fiRead_ACC = 11
    fiUpdate_ACC = 12
    fiIncrease_ACC = 13
    fiRehabilitate_ACC = 14
    fiInvalidate_ACC = 15
    fiRead3G_ACC = 16
    fiUpdate3G_ACC = 17
    fiWrite3G_ACC = 18
    fiIncrease3G_ACC = 19
    fiDeleteChild_ACC = 20
    fiDeleteSelf_ACC = 21
    fiCreateEF_ACC = 22
    fiCreateDF_ACC = 23
    fiDeactivate_ACC = 24
    fiActivate_ACC = 25
    fiTerminate_ACC = 26
    fiResize_ACC = 27
    fiCustom_ACC = 28
    fiARRRef = 29
    fiOTAAccess = 30
    fiADF_AID = 31
    fiRecordNumber = 32
    fiContent = 33
    fiFileName = 34

    ##############  DATA STRUCTURE  ###############

    # Internal List of file, to be built based on the CSV
    # We need first to build the data structure before processing to become test script

    ###############################################

    ###############  MAIN PROGRAM  ################

    if DEBUG_LOG:
        DebugFile = open(DebugFileName, 'w')

    isArrRefAvailable = 0

    # Open CSV File
    with open(FileName) as csvfile:
        csvReader = csv.DictReader(csvfile)

        # initialize the variables
        prevFileID = ''
        curFileID = ''
        prevFileType = ''
        curFileType = ''
        prevFileStruct = ''
        curFileStruct = ''

        prevFileIdLevel1 = ''
        curFileIdLevel1 = ''
        prevFileIdLevel2 = ''
        curFileIdLevel2 = ''
        prevFileIdLevel3 = ''
        curFileIdLevel3 = ''
        curDF = '3F00'

        curFilePath = ''
        prevFilePath = ''

        prevSFI = ''
        curSFI = ''

        prevUpdateActivity = ''
        curUpdateActivity = ''
        prevMandatory = ''
        curMandatory = ''
        prevLinkTo = ''
        curLinkTo = ''

        prevShareable = ''
        curShareable = ''
        prevFileStructure = ''
        curFileStructure = ''

        prevFileRecordSize = ''
        curFileRecordSize = ''
        prevNumberOfRecord = ''
        curNumberOfRecord = ''
        prevFileSize = ''
        curFileSize = ''

        prevACC_2G = ''
        curACC_2G = ''
        prevRead_ACC = ''
        curRead_ACC = ''
        prevUpdate_ACC = ''
        curUpdate_ACC = ''
        prevIncrease_ACC = ''
        curIncrease_ACC = ''
        prevRehabilitate_ACC = ''
        curRehabilitate_ACC = ''
        prevInvalidate_ACC = ''
        curInvalidate_ACC = ''

        prevRead3G_ACC = ''
        curRead3G_ACC = ''
        prevUpdate3G_ACC = ''
        curUpdate3G_ACC = ''

        prevWrite3G_ACC = ''
        curWrite3G_ACC = ''

        prevIncrease3G_ACC = ''
        curIncrease3G_ACC = ''
        prevDeleteChild_ACC = ''
        curDeleteChild_ACC = ''
        prevDeleteSelf_ACC = ''
        curDeleteSelf_ACC = ''
        prevDelete_ACC = ''
        curDelete_ACC = ''
        prevCreateDFEF_ACC = ''
        curCreateDFEF_ACC = ''
        prevCreateEF_ACC = ''
        curCreateEF_ACC = ''
        prevCreateDF_ACC = ''
        curCreateDF_ACC = ''
        prevDeactivate_ACC = ''
        curDeactivate_ACC = ''
        prevActivate_ACC = ''
        curActivate_ACC = ''
        prevTerminate_ACC = ''
        curTerminate_ACC = ''
        prevResize_ACC = ''
        curResize_ACC = ''
        prevCustom_ACC = ''
        curCustom_ACC = ''
        prevOtherCLA_ACC = ''
        curOtherCLA_ACC = ''
        prevOtherINS_ACC = ''
        curOtherINS_ACC = ''
        prevOtherValue_ACC = ''
        curOtherValue_ACC = ''
        prevReadDeleteChild_ACC = ''
        curReadDeleteChild_ACC = ''
        prevUpdateCreateChild_ACC = ''
        curUpdateCreateChild_ACC = ''
        prevARRRef = ''
        curARRRef = ''
        prevARRPath = ''
        curARRPath = ''
        prevARRID = ''
        curARRID = ''
        prevOTAAccess = ''
        curOTAAccess = ''
        prevADF_AID = ''
        curADF_AID = ''
        prevFileName = ''
        curFileName = ''

        prevARRRecordNumber = ''
        curARRRecordNumber = ''

        if OPT_USE_CLIENT:
            runlog_buffer.append("Building the File List from CSV file...")
        else:
            print "-----------------------------------------"
            print "Building the File List from CSV file..."
            print "-----------------------------------------"
        index = 0
        rowNmbr = 1
        for row in csvReader:  # row is a dictionary
            rowNmbr += 1
            efMarker = 'CSV row ' + str(rowNmbr)
            # if row.has_key(fFileName):
            #    print row[fFileName]
            # if row.has_key(fFileID):
            #    print row[fFileID]

            CurFile = []

            if not row.has_key(fFileType):
                ERROR("FileType Does Not Exist!!")  # File Type is Mandatory
                return False, 'FileType field (mandatory) does not exist'
                # sys.exit()

            # Get File Type (Mandatory to have File Type)
            curFileType = CheckPrev(FilterString(row[fFileType]), prevFileType)
            # May need to check consistency of File Type in the future

            # ---------------------Current Path ---------------------------

            # Get the FilePathID
            if index == 0: FieldList.append(fFilePath)
            if row.has_key(fFilePath):
                # Rule FilePath#2, using Filepath and FileID
                curFilePath = CheckPrev(FilterHex(row[fFilePath]), prevFilePath)
                if row.has_key(fFileID):
                    curFileID = FilterHex(row[fFileID])
                    if curFileID != '':
                        # only need to add the file ID if it is not empty
                        curFileID = CheckPrev(curFileID, prevFileID)
                        curFilePath = curFilePath + curFileID
            else:
                if row.has_key(fFileIdLevel1):  # Key fFileIdLevel1 indicate Rule#3
                    # Rule FilePath#3, using FilePathID
                    # LEVEL1
                    curFileIdLevel1 = FilterHex(row[fFileIdLevel1])

                    # in this case, cannot use CheckPrev() as we need to reset the other level if empty
                    if curFileIdLevel1 == '':  # Level1 empty
                        if prevFileIdLevel1 != '':
                            # copy if the previous one not empty
                            curFileIdLevel1 = prevFileIdLevel1
                        else:
                            ERROR("ERROR: Inconsistent File Structure!!")  # Level 1 is mandatory
                    else:
                        # reset the next level if the higher level is not empty
                        prevFileIdLevel2 = ''
                        prevFileIdLevel3 = ''
                        curFileIdLevel2 = ''
                        curFileIdLevel3 = ''
                    # LEVEL2
                    if not row.has_key(fFileIdLevel2):
                        # Minimum 2 level is needed
                        ERROR("ERROR: Minimum 2 Level is needed!!")
                    curFileIdLevel2 = FilterHex(row[fFileIdLevel2])
                    DEBUGPRINT("FileIdLevel2: " + str(curFileIdLevel2))
                    # in this case, cannot use CheckPrev() as we need to reset the other level if empty
                    if curFileIdLevel2 == '':  # Level2 empty
                        if prevFileIdLevel2 != '':
                            # copy if the previous one not empty
                            curFileIdLevel2 = prevFileIdLevel2
                            DEBUGPRINT("Modified FileIdLevel2: " + str(curFileIdLevel2))
                    else:
                        # reset the next level if the higher level is not empty
                        prevFileIdLevel3 = ''
                        curFileIdLevel3 = ''
                    # LEVEL3
                    if row.has_key(fFileIdLevel3):
                        curFileIdLevel3 = CheckPrev(FilterHex(row[fFileIdLevel3]), prevFileIdLevel3)
                    else:
                        curFileIdLevel3 = ''
                    # Concatenate file path
                    curFilePath = curFileIdLevel1 + curFileIdLevel2 + curFileIdLevel3
                else:
                    # Rule FilePath#1, using only FileID, but in hierarchycal structure.
                    #  DF is path from MF.
                    if row.has_key(fFileID):
                        curFileID = FilterHex(row[fFileID])
                        # if the current ID is empty, use the previous one
                        if curFileID == '':
                            curFilePath = prevFilePath
                        else:
                            curFileID = CheckPrev(curFileID, prevFileID)
                            if OPT_USE_CLIENT:
                                runlog_buffer.append(str(curFileID))
                            else:
                                print curFileID
                            if CheckList(curFileType, sFileTypeMF) or CheckList(curFileType, sFileTypeDF):
                                # Get Path
                                curFilePath = curFileID
                                curDF = curFileID
                            else:
                                # Handle if FileID always contain full path
                                if OPT_FILEID_EF_FULLPATH:
                                    curFilePath = curFileID
                                else:
                                    curFilePath = curDF + curFileID
                    else:
                        # Does not meet all the rule, return error
                        FATAL("ERROR: File ID Not Found!!")  # May indicate a need to support new rule
            # Update File Path to FileList
            if curFilePath[:4] != '3F00':
                # CurFile.append(curFilePath)
                CurFile.append('3F00' + curFilePath)
            else:
                CurFile.append(curFilePath)
            if OPT_USE_CLIENT:
                runlog_buffer.append(str(curFilePath))
            else:
                print curFilePath

            ## Check Consistency for ADF
            # if CheckList(curFileType, sFileTypeADF):
            #    if curFilePath[0:4] != '3F00' or curFilePath[4:8] == '7FFF':
            #            print "ERROR: ADF Path/ID not correct !!"

            # ---------------------Current Path completed---------------------------

            # ---------------------SFI ---------------------------
            if index == 0: FieldList.append(fSFI)
            if row.has_key(fSFI):
                # May be empty, does not always get the previous value.
                curSFI = CheckPrevIfNew(FilterHex(row[fSFI]), prevSFI)
                if curSFI != '':
                    if OPT_HEX_SFI:
                        RefSFI = int(curSFI, 16)
                    else:
                        RefSFI = int(curSFI)
                    if RefSFI >= 32:
                        ERROR("Invalid SFI value")
            else:
                curSFI = ''
            CurFile.append(curSFI)
            # ---------------------SFI END ---------------------------

            # ---------------------Link To ---------------------------
            # Currently only support Link To a path from MF.
            if index == 0: FieldList.append(fLinkTo)
            if row.has_key(fLinkTo):
                curLinkTo = CheckPrevIfNew(FilterHex(row[fLinkTo]), prevLinkTo)
            else:
                curLinkTo = ''
            CurFile.append(curLinkTo)
            # ---------------------Link To END ---------------------------

            # ---------------------Mandatory ---------------------------
            if index == 0: FieldList.append(fMandatory)
            if row.has_key(fMandatory):
                # May be empty, does not always get the previous value.
                curMandatory = CheckPrevIfNew(FilterString(row[fMandatory]), prevMandatory)
                # convert to boolean value
                if CheckList(curMandatory, sMandatoryYes):
                    CurFile.append(True)
                else:
                    CheckList(curMandatory, sMandatoryNo)
                    CurFile.append(True)
            else:
                # default: not mandatory
                CurFile.append(True)
            # ---------------------Mandatory END ---------------------------

            # ---------------------Update Activity ---------------------------
            if index == 0: FieldList.append(fUpdateActivity)
            if row.has_key(fUpdateActivity):
                curUpdateActivity = CheckPrevIfNew(FilterString(row[fUpdateActivity]), prevUpdateActivity)
                # convert to boolean value
                if CheckList(curUpdateActivity, sUpdateActivityHigh):
                    CurFile.append(True)
                else:
                    CurFile.append(False)
            else:
                # default Not High Activity
                CurFile.append(None)
            # ---------------------Update Activity END ---------------------------

            # ---------------------File Type ---------------------------
            # File Type is mandatory
            if index == 0: FieldList.append(fFileType)
            if CheckList(curFileType, sFileTypeMF) or \
                    CheckList(curFileType, sFileTypeDF) or \
                    CheckList(curFileType, sFileTypeADF):
                CurFile.append(curFileType)
            else:
                # Set to EF if it is not MF, DF, or ADF
                CurFile.append(sFileTypeEF[0])
            # ---------------------File Type END ---------------------------

            # ---------------------File Structure ---------------------------
            # Some customer use File Type for File Structure
            if index == 0: FieldList.append(fFileStructure)
            if row.has_key(fFileStructure):
                # Use File Structure
                curFileStructure = CheckPrevIfNew(FilterString(row[fFileStructure]), prevFileStructure)
            else:
                # Use File Type
                curFileStructure = curFileType

            if CheckList(curFileType, sFileTypeMF) or \
                    CheckList(curFileType, sFileTypeDF) or \
                    CheckList(curFileType, sFileTypeADF):
                curFileStructure = ''
            CurFile.append(curFileStructure)
            # ---------------------File Structure END ---------------------------

            # ---------------------Shareable ---------------------------
            if index == 0: FieldList.append(fShareable)
            if row.has_key(fShareable):
                # May be empty, does not always get the previous value.
                curShareable = CheckPrevIfNew(FilterString(row[fShareable]), prevShareable)
                # convert to boolean value
                if CheckList(curShareable, sShareableYes):
                    CurFile.append(True)
                else:
                    CurFile.append(False)
            else:
                # default: not mandatory
                CurFile.append(True)
            # ---------------------Shareable END ---------------------------

            # ---------------------File Size, Record Size, number of rec ---------------------------
            iFileSize = 0
            iRecSize = 0
            iNumOfRec = 0
            if row.has_key(fFileSize):
                # File Size may be empty for DF, may not always get the previous value
                curFileSize = CheckPrevIfNew(FilterString(row[fFileSize]),
                                             prevFileSize)  # File Size may have '=' or 'x'
                if (not (CheckList(curFileType, sFileTypeMF) or \
                                 CheckList(curFileType, sFileTypeDF) or \
                                 CheckList(curFileType, sFileTypeADF) or \
                                 CheckList(curFileStructure, sFileStructLK))) and \
                        (CheckList(curFileStructure, sFileStructLF) or CheckList(curFileStructure, sFileStructCY)):
                    # Only for EF CYTLIC or LINEAR FIXED
                    # for Linear Fixed or Cyclic, set the record size and number of record.

                    # Handle special case of Linear Fixed or Cyclic with empty FileSize
                    if curFileSize == '':
                        if not (row.has_key(fNumberOfRecord) and row.has_key(fFileRecordSize)):
                            # It is possible to have single field for File size, number of record and record size as well.
                            #   If it is empty, it will not be checked.
                            # ERROR("Unable to compute the size !!")
                            curNumberOfRecord = ''
                            curFileRecordSize = ''
                        else:
                            curNumberOfRecord = CheckPrevIfNew(FilterHex(row[fNumberOfRecord]), prevNumberOfRecord)
                            curFileRecordSize = CheckPrevIfNew(FilterHex(row[fFileRecordSize]), prevFileRecordSize)
                        if curNumberOfRecord == '':
                            iNumOfRec = 0
                            WARNING("EMPTY Number Of Record")
                        else:
                            iNumOfRec = int(curNumberOfRecord)
                        if curFileRecordSize == '':
                            iRecSize = 0
                            WARNING("EMPTY Record Size")
                        else:
                            iRecSize = int(curFileRecordSize)
                        iFileSize = iNumOfRec * iRecSize

                    else:
                        if row.has_key(fNumberOfRecord) or row.has_key(fFileRecordSize):
                            # Rule #1 (Default): For Cyclic and Linear fixed, FileSize = Filesize, if the filesize information available.
                            #   For Transparent, only File Size are needed.
                            #   By default Number of record is used, but if it is not available, record length is used.
                            if not curFileSize.isdigit():
                                # In the future, may need to support hexadecimal value
                                WARNING("ERROR: Not a correct filesize !!")
                            iFileSize = int(curFileSize)
                            if row.has_key(fNumberOfRecord):
                                # If Number of record is available, RecordSize = Filesize/NumberOfRecord
                                curNumberOfRecord = CheckPrevIfNew(FilterHex(row[fNumberOfRecord]), prevNumberOfRecord)
                                if curNumberOfRecord == '':
                                    iRecSize = 0
                                else:
                                    iNumOfRec = int(curNumberOfRecord)
                                if iNumOfRec == 0:
                                    WARNING("ZERO Number Of Record !!")
                                    iRecSize = 0
                                else:
                                    iRecSize = iFileSize / iNumOfRec
                            else:
                                # If RecordSize is available, NumberOfRecord = Filesize/RecordSize
                                curFileRecordSize = CheckPrevIfNew(FilterHex(row[fFileRecordSize]), prevFileRecordSize)
                                if curFileRecordSize == '':
                                    iRecSize = 0
                                else:
                                    iRecSize = int(curFileRecordSize)
                                if iRecSize == 0:
                                    WARNING("ZERO Record Size !!")
                                    iNumOfRec = 0
                                else:
                                    iNumOfRec = iFileSize / iRecSize
                        else:
                            # Rule #3: Only 1 single field "FileSize" for File Size, record size, and record number.
                            #   For LF/CY, first number = record size, second number = number of record.
                            #   This rule activated if both record size and number of record field is not avalable.
                            if curFileSize == '':
                                iRecSize = 0
                                iNumOfRec = 0
                                iFileSize = 0
                                WARNING("EMPTY File Size")
                            else:
                                t = curFileSize.find('X')
                                u = curFileSize.find('=')
                                if FILESIZE_RULE == 1:
                                    # Rule 1: RecordSizeXNumOfRecord(=FileSize)
                                    if t == -1:
                                        # No multiplication, only file size
                                        iFileSize = int(curFileSize)
                                        iRecSize = 0
                                        iNumOfRec = 0
                                    else:
                                        iRecSize = int(curFileSize[0:t])
                                        if u == -1:
                                            # No equal sign
                                            iNumOfRec = int(curFileSize[t + 1:])
                                            iFileSize = iNumOfRec * iRecSize
                                        else:
                                            iNumOfRec = int(curFileSize[t + 1:u])
                                            iFileSize = int(curFileSize[u + 1:])
                                            if (iRecSize * iNumOfRec) != iFileSize:
                                                WARNING("Not a correct filesize !!")
                                else:
                                    # Rule 2: NumOfRecordXRecordSize(=FileSize)
                                    if t == -1:
                                        # No multiplication, only file size
                                        iFileSize = int(curFileSize)
                                        iRecSize = 0
                                        iNumOfRec = 0
                                    else:
                                        iNumOfRec = int(curFileSize[0:t])
                                        if u == -1:
                                            # No equal sign
                                            iRecSize = int(curFileSize[t + 1:])
                                            iFileSize = iNumOfRec * iRecSize
                                        else:
                                            iRecSize = int(curFileSize[t + 1:u])
                                            iFileSize = int(curFileSize[u + 1:])
                                            if (iRecSize * iNumOfRec) != iFileSize:
                                                WARNING("Not a correct filesize !!")
                else:
                    # for TR, DF, MF, ADF
                    if curFileSize == '':
                        iFileSize = 0
                    else:
                        if not curFileSize.isdigit():
                            # In the future, may need to support hexadecimal value
                            WARNING("Not a correct filesize !!")
                        iFileSize = int(curFileSize)

                    iRecSize = 0
                    iNumOfRec = 0
            else:
                if row.has_key(fFileRecordOrFileSize):
                    # Rule #2: If "FileRecordOrFileSize" is available, this will be used.
                    #   For LF/CY, FileSize = FileRecordOrFileSize * NumberOfRecord
                    curFileSize = CheckPrevIfNew(FilterHex(row[fFileRecordOrFileSize]), prevFileSize)

                    if not curFileSize.isdigit():
                        # In the future, may need to support hexadecimal value
                        WARNING("Not a correct filesize !!")
                        iFileSize = 0
                    else:
                        iFileSize = int(curFileSize)
                    if (not (CheckList(curFileType, sFileTypeMF) or \
                                     CheckList(curFileType, sFileTypeDF) or \
                                     CheckList(curFileType, sFileTypeADF))) and \
                            (CheckList(curFileStructure, sFileStructLF) or CheckList(curFileStructure, sFileStructCY)):
                        # Only for EF CYTLIC or LINEAR FIXED
                        # for Linear Fixed or Cyclic, set the record size and number of record.
                        iRecSize = iFileSize
                        if row.has_key(fNumberOfRecord):
                            curNumberOfRecord = CheckPrevIfNew(FilterHex(row[fNumberOfRecord]), prevNumberOfRecord)
                            if curNumberOfRecord == '':
                                iNumOfRec = 0
                                WARNING("EMPTY Number Of Record")
                            else:
                                iNumOfRec = int(curNumberOfRecord)
                            iFileSize = iRecSize * iNumOfRec
                        else:
                            if OPT_USE_CLIENT:
                                runlog_buffer.append("ERROR: Missing # Of Record !!")
                            else:
                                print "ERROR: Missing # Of Record !!"
                            iRecSize = 0
                            iNumOfRec = 0
                    else:
                        # for TR, DF, MF, ADF:
                        iRecSize = 0
                        iNumOfRec = 0
                else:
                    # either "FileSize" or "FileRecordOrFileSize" must be available.
                    ERROR("No proper filesize information available !!")
                    iFileSize = 0
                    iRecSize = 0
                    iNumOfRec = 0
            # DEBUGPRINT("iFileSize: " + str(iFileSize))
            # DEBUGPRINT("iRecordSize: " + str(iRecSize))
            # DEBUGPRINT("iNumberOfRecord: " + str(iNumOfRec))
            if index == 0: FieldList.append(fFileSize)
            if index == 0: FieldList.append(fFileRecordSize)
            if index == 0: FieldList.append(fNumberOfRecord)
            CurFile.append(iFileSize)
            CurFile.append(iRecSize)
            CurFile.append(iNumOfRec)
            # ---------------------File Size, Record Size, number of rec END ---------------------------

            # --------------------- 2G Access Condition ---------------------------
            iRead_ACC = []
            iUpdate_ACC = []
            iIncrease_ACC = []
            iRehabilitate_ACC = []
            iInvalidate_ACC = []
            if row.has_key(fACC_2G):
                # if single access condition field define the access condition
                curACC_2G = CheckPrevIfNew(FilterHex(row[fACC_2G]), prevACC_2G)
                if len(curACC_2G) != 6:
                    WARNING("Bad 2G Access Condition")
                else:
                    iRead_ACC.append(int(curACC_2G[0], 16))
                    iUpdate_ACC.append(int(curACC_2G[1], 16))
                    iIncrease_ACC.append(int(curACC_2G[2], 16))
                    iRehabilitate_ACC.append(int(curACC_2G[4], 16))
                    iInvalidate_ACC.append(int(curACC_2G[5], 16))
            else:
                # each access condition defined individually
                #   - Handle 2G access condition that is defined in 3G, if not available in 2G
                # masukinfile
                if row.has_key(fRead_ACC):
                    curRead_ACC = CheckPrevIfNew(FilterString(row[fRead_ACC]), prevRead_ACC)
                    iRead_ACC = ConvertACC2G(curRead_ACC)
                elif row.has_key(fRead3G_ACC):
                    curRead_ACC = CheckPrevIfNew(FilterString(row[fRead3G_ACC]), prevRead_ACC)
                    iRead_ACC = ConvertACC2G(curRead_ACC)
                if row.has_key(fUpdate_ACC):
                    curUpdate_ACC = CheckPrevIfNew(FilterString(row[fUpdate_ACC]), prevUpdate_ACC)
                    iUpdate_ACC = ConvertACC2G(curUpdate_ACC)
                elif row.has_key(fUpdate3G_ACC):
                    curUpdate_ACC = CheckPrevIfNew(FilterString(row[fUpdate3G_ACC]), prevUpdate_ACC)
                    iUpdate_ACC = ConvertACC2G(curUpdate_ACC)
                if row.has_key(fIncrease_ACC):
                    curIncrease_ACC = CheckPrevIfNew(FilterString(row[fIncrease_ACC]), prevIncrease_ACC)
                    iIncrease_ACC = ConvertACC2G(curIncrease_ACC)
                elif row.has_key(fIncrease3G_ACC):
                    curIncrease_ACC = CheckPrevIfNew(FilterString(row[fIncrease3G_ACC]), prevIncrease_ACC)
                    iIncrease_ACC = ConvertACC2G(curIncrease_ACC)
                if row.has_key(fRehabilitate_ACC):
                    curRehabilitate_ACC = CheckPrevIfNew(FilterString(row[fRehabilitate_ACC]), prevRehabilitate_ACC)
                    iRehabilitate_ACC = ConvertACC2G(curRehabilitate_ACC)
                elif row.has_key(fActivate_ACC):
                    curRehabilitate_ACC = CheckPrevIfNew(FilterString(row[fActivate_ACC]), prevRehabilitate_ACC)
                    iRehabilitate_ACC = ConvertACC2G(curRehabilitate_ACC)
                if row.has_key(fInvalidate_ACC):
                    curInvalidate_ACC = CheckPrevIfNew(FilterString(row[fInvalidate_ACC]), prevInvalidate_ACC)
                    iInvalidate_ACC = ConvertACC2G(curInvalidate_ACC)
                elif row.has_key(fDeactivate_ACC):
                    curInvalidate_ACC = CheckPrevIfNew(FilterString(row[fDeactivate_ACC]), prevInvalidate_ACC)
                    iInvalidate_ACC = ConvertACC2G(curInvalidate_ACC)
                    #   Access Condition defined using EF ARR content will be updated in the second/third loop.
            if index == 0: FieldList.append(fRead_ACC)
            if index == 0: FieldList.append(fUpdate_ACC)
            if index == 0: FieldList.append(fIncrease_ACC)
            if index == 0: FieldList.append(fRehabilitate_ACC)
            if index == 0: FieldList.append(fInvalidate_ACC)
            CurFile.append(iRead_ACC)
            CurFile.append(iUpdate_ACC)
            CurFile.append(iIncrease_ACC)
            CurFile.append(iRehabilitate_ACC)
            CurFile.append(iInvalidate_ACC)
            # ---------------------2G Access Condition END ---------------------------

            # ---------------------3G Access Condition ---------------------------
            # Initialize variables
            # iRead3G_ACC = iAccUNDEF
            # iUpdate3G_ACC = iAccUNDEF
            # iWrite3G_ACC = iAccUNDEF
            # iIncrease3G_ACC = iAccUNDEF
            # iDeleteChild_ACC = iAccUNDEF    # according TS102.222 V7.1.0, "Delete File (Child)" shall not be used.
            # iDeleteSelf_ACC = iAccUNDEF
            # iCreateEF_ACC = iAccUNDEF
            # iCreateDF_ACC = iAccUNDEF
            # iDeactivate_ACC = iAccUNDEF
            # iActivate_ACC = iAccUNDEF
            # iTerminate_ACC = iAccUNDEF
            # iResize_ACC = iAccUNDEF
            # ListCustom_ACC = []         # List of [Class, Instruction, P1, P2 and Access condition]

            CurACC = [[], [], [], [], [], [], [], [], [], [], [], [], []]
            # Rule #1: handle basic access condition
            # Rule #3: if 3G specific field are not present, use the 2G counterpart
            # masukinfile
            #   Applies to Read, Update, Increase, Activate (Rehabilitate), Deactivate (Invalidate)
            if row.has_key(fRead3G_ACC):
                curRead3G_ACC = CheckPrevIfNew(FilterString(row[fRead3G_ACC]), prevRead3G_ACC)
                CurACC[siRead_ACC] = ConvertACC(curRead3G_ACC)
            elif row.has_key(fRead_ACC):
                curRead3G_ACC = CheckPrevIfNew(FilterString(row[fRead_ACC]), prevRead3G_ACC)
                CurACC[siRead_ACC] = ConvertACC(curRead3G_ACC)
            if row.has_key(fUpdate3G_ACC):
                curUpdate3G_ACC = CheckPrevIfNew(FilterString(row[fUpdate3G_ACC]), prevUpdate3G_ACC)
                CurACC[siUpdate_ACC] = ConvertACC(curUpdate3G_ACC)
            elif row.has_key(fUpdate_ACC):
                curUpdate3G_ACC = CheckPrevIfNew(FilterString(row[fUpdate_ACC]), prevUpdate3G_ACC)
                CurACC[siUpdate_ACC] = ConvertACC(curUpdate3G_ACC)
            if row.has_key(fWrite3G_ACC):
                curWrite3G_ACC = CheckPrevIfNew(FilterString(row[fWrite3G_ACC]), prevWrite3G_ACC)
                CurACC[siWrite3G_ACC] = ConvertACC(curWrite3G_ACC)
            if row.has_key(fIncrease3G_ACC):
                curIncrease3G_ACC = CheckPrevIfNew(FilterString(row[fIncrease3G_ACC]), prevIncrease3G_ACC)
                CurACC[siIncrease_ACC] = ConvertACC(curIncrease3G_ACC)
            elif row.has_key(fIncrease_ACC):
                curIncrease3G_ACC = CheckPrevIfNew(FilterString(row[fIncrease_ACC]), prevIncrease3G_ACC)
                CurACC[siIncrease_ACC] = ConvertACC(curIncrease3G_ACC)
            if row.has_key(fDeleteChild_ACC):
                curDeleteChild_ACC = CheckPrevIfNew(FilterString(row[fDeleteChild_ACC]), prevDeleteChild_ACC)
                CurACC[siDeleteChild_ACC] = ConvertACC(curDeleteChild_ACC)
            if row.has_key(fDeleteSelf_ACC):
                curDeleteSelf_ACC = CheckPrevIfNew(FilterString(row[fDeleteSelf_ACC]), prevDeleteSelf_ACC)
                CurACC[siDeleteSelf_ACC] = ConvertACC(curDeleteSelf_ACC)
            if row.has_key(fCreateEF_ACC):
                curCreateEF_ACC = CheckPrevIfNew(FilterString(row[fCreateEF_ACC]), prevCreateEF_ACC)
                CurACC[siCreateEF_ACC] = ConvertACC(curCreateEF_ACC)
            if row.has_key(fCreateDF_ACC):
                curCreateDF_ACC = CheckPrevIfNew(FilterString(row[fCreateDF_ACC]), prevCreateDF_ACC)
                CurACC[siCreateDF_ACC] = ConvertACC(curCreateDF_ACC)
            if row.has_key(fDeactivate_ACC):
                curDeactivate_ACC = CheckPrevIfNew(FilterString(row[fDeactivate_ACC]), prevDeactivate_ACC)
                CurACC[siDeactivate_ACC] = ConvertACC(curDeactivate_ACC)
            elif row.has_key(fInvalidate_ACC):
                curDeactivate_ACC = CheckPrevIfNew(FilterString(row[fInvalidate_ACC]), prevDeactivate_ACC)
                CurACC[siDeactivate_ACC] = ConvertACC(curDeactivate_ACC)
            if row.has_key(fActivate_ACC):
                curActivate_ACC = CheckPrevIfNew(FilterString(row[fActivate_ACC]), prevActivate_ACC)
                CurACC[siActivate_ACC] = ConvertACC(curActivate_ACC)
            elif row.has_key(fRehabilitate_ACC):
                curActivate_ACC = CheckPrevIfNew(FilterString(row[fRehabilitate_ACC]), prevActivate_ACC)
                CurACC[siActivate_ACC] = ConvertACC(curActivate_ACC)
            if row.has_key(fTerminate_ACC):
                curTerminate_ACC = CheckPrevIfNew(FilterString(row[fTerminate_ACC]), prevTerminate_ACC)
                CurACC[siTerminate_ACC] = ConvertACC(curTerminate_ACC)
            if row.has_key(fResize_ACC):
                curResize_ACC = CheckPrevIfNew(FilterString(row[fResize_ACC]), prevResize_ACC)
                CurACC[siResize_ACC] = ConvertACC(curResize_ACC)

                # Special handle for Custom ACC.
                #   Custom access condition in single field is not supported for now
                # if row.has_key(fCustom_ACC):
                # curCustom_ACC = CheckPrevIfNew(FilterString(row[fCustom_ACC][8:]), prevCustom_ACC)
                # CurACC[siCustom_ACC] = ConvertACC(curCustom_ACC)

            # Update for custom access condition

            if row.has_key(fCustom_ACC):
                curCustom_ACC = CheckPrevIfNew(FilterString(row[fCustom_ACC][8:]), prevCustom_ACC)
                CurACC[siCustom_ACC] = ConvertACC(curCustom_ACC)

            # End of update for custom access condition

            if row.has_key(fOtherCLA_ACC) and row.has_key(fOtherINS_ACC) and row.has_key(fOtherValue_ACC):
                CurACC[siCustom_ACC] = [None, None, None, None]
                curOtherCLA_ACC = CheckPrevIfNew(FilterHex(row[fOtherCLA_ACC]), prevOtherCLA_ACC)
                if curOtherCLA_ACC != '':
                    iOtherCLA = int(curOtherCLA_ACC)
                    CurACC[siCustom_ACC][0] = iOtherCLA
                curOtherINS_ACC = CheckPrevIfNew(FilterHex(row[fOtherINS_ACC]), prevOtherINS_ACC)
                if curOtherINS_ACC != '':
                    iOtherINS = int(curOtherINS_ACC)
                    CurACC[siCustom_ACC][1] = iOtherINS
                curOtherValue_ACC = CheckPrevIfNew(FilterString(row[fOtherValue_ACC]), prevOtherValue_ACC)
                if curOtherValue_ACC != '':
                    CurACC[siCustom_ACC].append(ConvertACC(curOtherValue_ACC))

            # Rule #2: For Specific profile with specific field,
            #   i.e. "ReadDeleteChild", "UpdateCreateChild", "CreateDFEF"
            if row.has_key(fReadDeleteChild_ACC):
                curReadDeleteChild_ACC = CheckPrevIfNew(FilterString(row[fReadDeleteChild_ACC]),
                                                        prevReadDeleteChild_ACC)
                if CheckList(curFileType, sFileTypeMF) or \
                        CheckList(curFileType, sFileTypeDF) or \
                        CheckList(curFileType, sFileTypeADF):
                    CurACC[siDeleteChild_ACC] = ConvertACC(curReadDeleteChild_ACC)
                else:
                    CurACC[siRead_ACC] = ConvertACC(curReadDeleteChild_ACC)
            if row.has_key(fUpdateCreateChild_ACC):
                curUpdateCreateChild_ACC = CheckPrevIfNew(FilterString(row[fUpdateCreateChild_ACC]),
                                                          prevUpdateCreateChild_ACC)
                if CheckList(curFileType, sFileTypeMF) or \
                        CheckList(curFileType, sFileTypeDF) or \
                        CheckList(curFileType, sFileTypeADF):
                    CurACC[siCreateEF_ACC] = ConvertACC(curUpdateCreateChild_ACC)
                else:
                    CurACC[siUpdate_ACC] = ConvertACC(curUpdateCreateChild_ACC)
            if row.has_key(fCreateDFEF_ACC):
                curCreateDFEF_ACC = CheckPrevIfNew(FilterString(row[fCreateDFEF_ACC]), prevCreateDFEF_ACC)
                CurACC[siCreateEF_ACC] = ConvertACC(curCreateDFEF_ACC)
                CurACC[siCreateDF_ACC] = ConvertACC(curCreateDFEF_ACC)

            # Rule #4: When "ARR Content" field is available and not empty,
            # the script can decode from this field in the row. (NOT SUPPORTED FOR NOW)

            # Rule #5: When "ARRRef" (or "ARRID" and "ARRRecordNumber" field) is available and not empty,
            #   The script can build the ARR List (second pass)
            #   the script can search for a ARR file in the list (third pass).
            # Store the ARR Reference for now
            if row.has_key(fARRRef):
                curARRRef = CheckPrevIfNew(FilterString(row[fARRRef]), prevARRRef)
                isArrRefAvailable = 1  # indicate that ARR reference is available
            # elif row.has_key(fARRPath) and row.has_key(fARRID):
            elif row.has_key(fARRRecordNumber) and row.has_key(fARRID):
                # curARRPath = CheckPrevIfNew(FilterString(row[fARRPath]), prevARRPath)
                curARRRecordNumber = CheckPrevIfNew(FilterString(row[fARRRecordNumber]), prevARRRecordNumber)
                curARRID = CheckPrevIfNew(FilterString(row[fARRID]), prevARRID)
                # curARRRef = curARRPath + curARRID
                curARRRef = curARRID + curARRRecordNumber
                isArrRefAvailable = 1  # indicate that ARR reference is available

            # Append to field list and current file at the end
            if index == 0: FieldList.append(fRead3G_ACC)
            if index == 0: FieldList.append(fUpdate3G_ACC)
            if index == 0: FieldList.append(fWrite3G_ACC)
            if index == 0: FieldList.append(fIncrease3G_ACC)
            if index == 0: FieldList.append(fDeleteChild_ACC)
            if index == 0: FieldList.append(fDeleteSelf_ACC)
            if index == 0: FieldList.append(fCreateEF_ACC)
            if index == 0: FieldList.append(fCreateDF_ACC)
            if index == 0: FieldList.append(fDeactivate_ACC)
            if index == 0: FieldList.append(fActivate_ACC)
            if index == 0: FieldList.append(fTerminate_ACC)
            if index == 0: FieldList.append(fResize_ACC)
            if index == 0: FieldList.append(fCustom_ACC)
            if index == 0: FieldList.append(fARRRef)
            for a in CurACC:
                CurFile.append(a)
            CurFile.append(curARRRef)
            # CurFile.append(iRead3G_ACC)
            # CurFile.append(iUpdate3G_ACC)
            # CurFile.append(iWrite3G_ACC)
            # CurFile.append(iIncrease3G_ACC)
            # CurFile.append(iDeleteChild_ACC)
            # CurFile.append(iDeleteSelf_ACC)
            # CurFile.append(iCreateEF_ACC)
            # CurFile.append(iCreateDF_ACC)
            # CurFile.append(iDeactivate_ACC)
            # CurFile.append(iActivate_ACC)
            # CurFile.append(iTerminate_ACC)
            # CurFile.append(iResize_ACC)
            # CurFile.append(ListCustom_ACC)
            # ---------------------3G Access Condition END ---------------------------

            # ---------------------OTA Access ---------------------------
            # The script will just save the value for now
            if row.has_key(fOTAAccess):
                curOTAAccess = CheckPrevIfNew(FilterString(row[fOTAAccess]), prevOTAAccess)
            if index == 0: FieldList.append(fOTAAccess)
            CurFile.append(curOTAAccess)
            # ---------------------OTA Access END ---------------------------

            # ---------------------ADF AID ---------------------------
            # The script will just save the value for now
            if row.has_key(fADF_AID):
                curADF_AID = CheckPrevIfNew(FilterString(row[fADF_AID]), prevADF_AID)
            if index == 0: FieldList.append(fADF_AID)
            CurFile.append(curADF_AID)
            # ---------------------ADF AID END ---------------------------

            # ---------------------Content ---------------------------
            if row.has_key(fRecordNumber) and row.has_key(fContent):  # Both Record Number and Content must be present
                # only check the current row for content
                curRecordNumber = FilterString(row[fRecordNumber])
                # curContent = FilterString(row[fContent])
                curContent = row[fContent]  # do not filter the content
            if curContent != '':
                # Process if the content is not empty
                pass
            else:
                # Maybe to handle variable?
                pass
            if index == 0: FieldList.append(fRecordNumber)
            if index == 0: FieldList.append(fContent)
            CurFile.append(curRecordNumber)
            CurFile.append(curContent)

            # ---------------------Content END ---------------------------

            if row.has_key(fFileName):
                curFileName = row[fFileName]  # working

                #         if row.has_key(fFileName):
                #             curFileName = CheckPrevIfNew(FilterString(row[fFileName]), prevFileName)

            if index == 0: FieldList.append(fFileName)
            CurFile.append(curFileName)

            # Stop if the current file is considered empty
            if curFilePath == prevFilePath and curContent == '':
                break
            # Add the File List before continue.
            #   There is no need to add to file list if the Current file is empty.
            FileList.append(CurFile)
            index = index + 1

            # Before going to the next loop, save the previous value and reset the current value

            # Created in the beginning

            prevARRRecordNumber = curARRRecordNumber
            curARRRecordNumber = ''
            prevOTAAccess = curOTAAccess
            curOTAAccess = ''
            prevADF_AID = curADF_AID
            curADF_AID = ''

            prevARRRef = curARRRef
            curARRRef = ''
            prevARRPath = curARRPath
            curARRPath = ''
            prevARRID = curARRID
            curARRID = ''

            prevRead3G_ACC = curRead3G_ACC
            curRead3G_ACC = ''
            prevUpdate3G_ACC = curUpdate3G_ACC
            curUpdate3G_ACC = ''

            prevWrite3G_ACC = curWrite3G_ACC
            curWrite3G_ACC = ''

            prevIncrease3G_ACC = curIncrease3G_ACC
            curIncrease3G_ACC = ''
            prevDeleteChild_ACC = curDeleteChild_ACC
            curDeleteChild_ACC = ''
            prevDeleteSelf_ACC = curDeleteSelf_ACC
            curDeleteSelf_ACC = ''
            prevDelete_ACC = curDelete_ACC
            curDelete_ACC = ''
            prevCreateDFEF_ACC = curCreateDFEF_ACC
            curCreateDFEF_ACC = ''
            prevCreateEF_ACC = curCreateEF_ACC
            curCreateEF_ACC = ''
            prevCreateDF_ACC = curCreateDF_ACC
            curCreateDF_ACC = ''
            prevDeactivate_ACC = curDeactivate_ACC
            curDeactivate_ACC = ''
            prevActivate_ACC = curActivate_ACC
            curActivate_ACC = ''
            prevTerminate_ACC = curTerminate_ACC
            curTerminate_ACC = ''
            prevResize_ACC = curResize_ACC
            curResize_ACC = ''
            prevCustom_ACC = curCustom_ACC
            curCustom_ACC = ''
            prevOtherCLA_ACC = curOtherCLA_ACC
            curOtherCLA_ACC = ''
            prevOtherINS_ACC = curOtherINS_ACC
            curOtherINS_ACC = ''
            prevOtherValue_ACC = curOtherValue_ACC
            curOtherValue_ACC = ''
            prevReadDeleteChild_ACC = curReadDeleteChild_ACC
            curReadDeleteChild_ACC = ''
            prevUpdateCreateChild_ACC = curUpdateCreateChild_ACC
            curUpdateCreateChild_ACC = ''

            prevACC_2G = curACC_2G
            curACC_2G = ''
            prevRead_ACC = curRead_ACC
            curRead_ACC = ''
            prevUpdate_ACC = curUpdate_ACC
            curUpdate_ACC = ''
            prevIncrease_ACC = curIncrease_ACC
            curIncrease_ACC = ''
            prevRehabilitate_ACC = curRehabilitate_ACC
            curRehabilitate_ACC = ''
            prevInvalidate_ACC = curInvalidate_ACC
            curInvalidate_ACC = ''
            prevFileRecordSize = curFileRecordSize
            curFileRecordSize = ''
            prevNumberOfRecord = curNumberOfRecord
            curNumberOfRecord = ''
            prevFileSize = curFileSize
            curFileSize = ''
            prevShareable = curShareable
            curShareable = ''
            prevFileStructure = curFileStructure
            curFileStructure = ''
            prevUpdateActivity = curUpdateActivity
            curUpdateActivity = ''
            prevMandatory = curMandatory
            curMandatory = ''
            prevLinkTo = curLinkTo
            curLinkTo = ''
            prevSFI = curSFI
            curSFI = ''
            prevFileID = curFileID
            curFileID = ''
            prevFileType = curFileType
            curFileType = ''
            prevFileStruct = curFileStruct
            curFileStruct = ''

            prevFileIdLevel1 = curFileIdLevel1
            curFileIdLevel1 = ''
            prevFileIdLevel2 = curFileIdLevel2
            curFileIdLevel2 = ''
            prevFileIdLevel3 = curFileIdLevel3
            curFileIdLevel3 = ''

            prevFilePath = curFilePath
            curFilePath = ''

            prevFileName = curFileName  # experimental
            curFileName = ''  # experimental

        # DEBUGPRINT("FieldList" + str(FieldList))
        DEBUGPRINT("FileList before ARR: " + str(FileList))

    efMarker = '(marker not set)'

    ARRList = []
    if isArrRefAvailable == 1:  # indicate that ARR reference is available
        # Second Pass: if ARR Reference is defined, build the ARR List
        # ARR Structure: fiFilePathID, fiRecordNumber, fiContent
        if OPT_USE_CLIENT:
            runlog_buffer.append("Updating the File List based on ARR value in CSV...")
            runlog_buffer.append("Second Pass: Create ARR List...")
        else:
            print "Updating the File List based on ARR value in CSV..."
            print "Second Pass: Create ARR List..."
        for file in FileList:
            DEBUGPRINT("file" + str(file))
            tempContent = FilterString(file[fiContent])  # Filter content for ARR
            # if file[fiRecordNumber] == '' or file[fiContent] == '':
            if file[fiRecordNumber] == '' or tempContent == '':
                # Skip if there is no content
                continue
            if ArrFileId1 in file[fiFilePathID] or ArrFileId2 in file[fiFilePathID]:
                if OPT_HEX_RECORDNUMBER:
                    # ARRList.append([file[fiFilePathID], int(file[fiRecordNumber],16), file[fiContent]])
                    ARRList.append([file[fiFilePathID], int(file[fiRecordNumber], 16), tempContent])
                else:
                    # ARRList.append([file[fiFilePathID], int(file[fiRecordNumber]), file[fiContent]])
                    ARRList.append([file[fiFilePathID], int(file[fiRecordNumber]), tempContent])
            else:
                # Not ARR file, skip
                continue
        DEBUGPRINT("ARRList: " + str(ARRList))
        # Third Pass: if ARR Reference is defined, Update the File List with the ARR value.
        if OPT_USE_CLIENT:
            runlog_buffer.append("Third Pass: Update File List with access condition from ARR List...")
        else:
            print " Third Pass: Update File List with access condition from ARR List..."
        for file in FileList:
            if OPT_USE_CLIENT:
                runlog_buffer.append(str(file[fiFilePathID]))
            else:
                print file[fiFilePathID]
            if file[fiARRRef] == '':
                continue  # Skip if the ARR reference is empty
            # find the ARR
            ArrId = file[fiARRRef][:4]
            # ARR Reference may use different format as the Record Number field
            if OPT_HEX_ARRREREF:
                ArrRec = int(file[fiARRRef][4:], 16)
            else:
                ArrRec = int(file[fiARRRef][4:])
            # TODO: Handle path of DF/MF/ADF (not -4)
            if CheckList(file[fiFileType], sFileTypeMF) or \
                    CheckList(file[fiFileType], sFileTypeDF) or \
                    CheckList(file[fiFileType], sFileTypeADF):
                path = file[fiFilePathID]
            else:
                path = file[fiFilePathID][:len(file[fiFilePathID]) - 4]
            CurAcc = None
            level = len(path)
            while level >= 4:
                for arr in ARRList:
                    if ArrFileId1 == ArrId:
                        if ArrId in arr[0]:
                            # For ArrFileId1, assuming under MF (no checking of path)
                            if ArrRec == arr[1]:
                                if OPT_USE_CLIENT:
                                    runlog_buffer.append("ARR Ref: " + str(arr[0]) + str(arr[1]))
                                    runlog_buffer.append("ARR Content: " + str(arr[2]))
                                else:
                                    print "ARR Ref: " + str(arr[0]) + str(arr[1])
                                    print "ARR Content: " + arr[2]
                                CurAcc = ARR2ACC(ParseARRV2(arr[2]), file[fiFileType])
                                break
                    elif path[:level] in arr[0] and ArrId in arr[0]:
                        # For other ArrFileId, look for the same parent?
                        if ArrRec == arr[1]:
                            if OPT_USE_CLIENT:
                                runlog_buffer.append("ARR Ref: " + str(arr[0]) + str(arr[1]))
                                runlog_buffer.append("ARR Content: " + str(arr[2]))
                            else:
                                print "ARR Ref: " + str(arr[0]) + str(arr[1])
                                print "ARR Content: " + arr[2]
                            CurAcc = ARR2ACC(ParseARRV2(arr[2]), file[fiFileType])
                            break
                if CurAcc == None:
                    level -= 4  # go up 1 level and look for ARR
                else:
                    break
            if CurAcc == None:
                if OPT_USE_CLIENT:
                    runlog_buffer.append("File: " + str(file[fiFilePathID]))
                    runlog_buffer.append("Arr: " + str(file[fiARRRef]))
                else:
                    print("File: " + str(file[fiFilePathID]))
                    print("Arr: " + str(file[fiARRRef]))
                ERROR("Reference ARR not Found")
                # DEBUGPRINT("File :"+ str(file))
            else:  # Reference ARR Found:
                DEBUGPRINT("file: " + str(file))
                DEBUGPRINT("arr: " + str(arr))
                DEBUGPRINT("CurAcc: " + str(CurAcc))

                # TODO: In the future, may need to check if the field has been populated
                #   and optionally to check the consistency with the EF ARR
                if file[fiRead3G_ACC] == []:
                    file[fiRead3G_ACC] = CurAcc[siRead_ACC]
                else:
                    if len(file[fiRead3G_ACC]) != len(CurAcc[siRead_ACC]) or \
                                    set(file[fiRead3G_ACC]).intersection(CurAcc[siRead_ACC]) != set(CurAcc[siRead_ACC]):
                        WARNING("Different Read 3G Access Condition with ARR Reference")
                if file[fiUpdate3G_ACC] == []:
                    file[fiUpdate3G_ACC] = CurAcc[siUpdate_ACC]
                else:
                    if len(file[fiUpdate3G_ACC]) != len(CurAcc[siUpdate_ACC]) or \
                                    set(file[fiUpdate3G_ACC]).intersection(CurAcc[siUpdate_ACC]) != set(
                                CurAcc[siUpdate_ACC]):
                        WARNING("Different Update 3G Access Condition with ARR Reference")

                if file[fiWrite3G_ACC] == []:
                    file[fiWrite3G_ACC] = CurAcc[siWrite3G_ACC]
                else:
                    if len(file[fiWrite3G_ACC]) != len(CurAcc[siWrite3G_ACC]) or \
                                    set(file[fiWrite3G_ACC]).intersection(CurAcc[siWrite3G_ACC]) != set(
                                CurAcc[siWrite3G_ACC]):
                        WARNING("Different Write 3G Access Condition with ARR Reference")
                if file[fiIncrease3G_ACC] == []:
                    file[fiIncrease3G_ACC] = CurAcc[siIncrease_ACC]
                else:
                    if len(file[fiIncrease3G_ACC]) != len(CurAcc[siIncrease_ACC]) or \
                                    set(file[fiIncrease3G_ACC]).intersection(CurAcc[siIncrease_ACC]) != set(
                                CurAcc[siIncrease_ACC]):
                        WARNING("Different Inrease 3G Access Condition with ARR Reference")
                if file[fiDeleteChild_ACC] == []:
                    file[fiDeleteChild_ACC] = CurAcc[siDeleteChild_ACC]
                else:
                    if len(file[fiDeleteChild_ACC]) != len(CurAcc[siDeleteChild_ACC]) or \
                                    set(file[fiDeleteChild_ACC]).intersection(CurAcc[siDeleteChild_ACC]) != set(
                                CurAcc[siDeleteChild_ACC]):
                        WARNING("Different Delete Child 3G Access Condition with ARR Reference")
                if file[fiDeleteSelf_ACC] == []:
                    file[fiDeleteSelf_ACC] = CurAcc[siDeleteSelf_ACC]
                else:
                    if len(file[fiDeleteSelf_ACC]) != len(CurAcc[siDeleteSelf_ACC]) or \
                                    set(file[fiDeleteSelf_ACC]).intersection(CurAcc[siDeleteSelf_ACC]) != set(
                                CurAcc[siDeleteSelf_ACC]):
                        WARNING("Different Delete Self 3G Access Condition with ARR Reference")
                if file[fiCreateEF_ACC] == []:
                    file[fiCreateEF_ACC] = CurAcc[siCreateEF_ACC]
                else:
                    if len(file[fiCreateEF_ACC]) != len(CurAcc[siCreateEF_ACC]) or \
                                    set(file[fiCreateEF_ACC]).intersection(CurAcc[siCreateEF_ACC]) != set(
                                CurAcc[siCreateEF_ACC]):
                        WARNING("Different Create EF 3G Access Condition with ARR Reference")
                if file[fiCreateDF_ACC] == []:
                    file[fiCreateDF_ACC] = CurAcc[siCreateDF_ACC]
                else:
                    if len(file[fiCreateDF_ACC]) != len(CurAcc[siCreateDF_ACC]) or \
                                    set(file[fiCreateDF_ACC]).intersection(CurAcc[siCreateDF_ACC]) != set(
                                CurAcc[siCreateDF_ACC]):
                        WARNING("Different Create DF 3G Access Condition with ARR Reference")
                if file[fiDeactivate_ACC] == []:
                    file[fiDeactivate_ACC] = CurAcc[siDeactivate_ACC]
                else:
                    if len(file[fiDeactivate_ACC]) != len(CurAcc[siDeactivate_ACC]) or \
                                    set(file[fiDeactivate_ACC]).intersection(CurAcc[siDeactivate_ACC]) != set(
                                CurAcc[siDeactivate_ACC]):
                        WARNING("Different Deactivate 3G Access Condition with ARR Reference")
                if file[fiActivate_ACC] == []:
                    file[fiActivate_ACC] = CurAcc[siActivate_ACC]
                else:
                    if len(file[fiActivate_ACC]) != len(CurAcc[siActivate_ACC]) or \
                                    set(file[fiActivate_ACC]).intersection(CurAcc[siActivate_ACC]) != set(
                                CurAcc[siActivate_ACC]):
                        WARNING("Different Activate 3G Access Condition with ARR Reference")
                if file[fiTerminate_ACC] == []:
                    file[fiTerminate_ACC] = CurAcc[siTerminate_ACC]
                else:
                    if len(file[fiTerminate_ACC]) != len(CurAcc[siTerminate_ACC]) or \
                                    set(file[fiTerminate_ACC]).intersection(CurAcc[siTerminate_ACC]) != set(
                                CurAcc[siTerminate_ACC]):
                        WARNING("Different Terminate 3G Access Condition with ARR Reference")
                if file[fiResize_ACC] == []:
                    file[fiResize_ACC] = CurAcc[siResize_ACC]
                else:
                    if len(file[fiResize_ACC]) != len(CurAcc[siResize_ACC]) or \
                                    set(file[fiResize_ACC]).intersection(CurAcc[siResize_ACC]) != set(
                                CurAcc[siResize_ACC]):
                        WARNING("Different Resize 3G Access Condition with ARR Reference")
                # change 'CurAcc to CurACC'
                if file[fiCustom_ACC] == []:
                    file[fiCustom_ACC] = CurACC[siCustom_ACC]
                else:
                    if len(file[fiCustom_ACC]) != len(CurACC[siCustom_ACC]) or \
                                    set(file[fiCustom_ACC]).intersection(CurACC[siCustom_ACC]) != set(
                                CurACC[siCustom_ACC]):
                        WARNING("Different Custom 3G Custom Condition with ARR Reference")

                # May be used to initialize 2G access condition
                if OPT_ARR4_2G:
                    # DEBUGPRINT("CurAcc: " + str(CurAcc))
                    # For now, Local PIN 1 map to CHV2 (Single Verification UICC, as in TS102.221)
                    # if CurAcc[siRead_ACC] == [0x81]:
                    #    file[fiRead_ACC] = [iAccCHV2]
                    # else:
                    #    file[fiRead_ACC] = CurAcc[siRead_ACC]
                    # if CurAcc[siUpdate_ACC] == [0x81]:
                    #    file[fiUpdate_ACC] = [iAccCHV2]
                    # else:
                    #    file[fiUpdate_ACC] = CurAcc[siUpdate_ACC]
                    # if CurAcc[siIncrease_ACC] == [0x81]:
                    #    file[fiIncrease_ACC] = [iAccCHV2]
                    # else:
                    #    file[fiIncrease_ACC] = CurAcc[siIncrease_ACC]
                    # if CurAcc[siDeactivate_ACC] == [0x81]:
                    #    file[fiInvalidate_ACC] = [iAccCHV2]
                    # else:
                    #    file[fiInvalidate_ACC] = CurAcc[siDeactivate_ACC]
                    # if CurAcc[siActivate_ACC] == [0x81]:
                    #    file[fiRehabilitate_ACC] = [iAccCHV2]
                    # else:
                    #    file[fiRehabilitate_ACC] = CurAcc[siActivate_ACC]

                    # file[fiRead_ACC] = [CovertACC3GTo2G(CurAcc[siRead_ACC])]
                    # file[fiUpdate_ACC] = [CovertACC3GTo2G(CurAcc[siUpdate_ACC])]
                    # file[fiIncrease_ACC] = [CovertACC3GTo2G(CurAcc[siIncrease_ACC])]
                    # file[fiInvalidate_ACC] = [CovertACC3GTo2G(CurAcc[siDeactivate_ACC])]
                    # file[fiRehabilitate_ACC] = [CovertACC3GTo2G(CurAcc[siActivate_ACC])]

                    if CurAcc[siRead_ACC] == []:
                        file[fiRead_ACC] = []
                    else:
                        file[fiRead_ACC] = [CovertACC3GTo2G(CurAcc[siRead_ACC][0])]
                    if CurAcc[siUpdate_ACC] == []:
                        file[fiUpdate_ACC] = []
                    else:
                        file[fiUpdate_ACC] = [CovertACC3GTo2G(CurAcc[siUpdate_ACC][0])]
                    if CurAcc[siIncrease_ACC] == []:
                        file[fiIncrease_ACC] = []
                    else:
                        file[fiIncrease_ACC] = [CovertACC3GTo2G(CurAcc[siIncrease_ACC][0])]
                    if CurAcc[siDeactivate_ACC] == []:
                        file[fiInvalidate_ACC] = []
                    else:
                        file[fiInvalidate_ACC] = [CovertACC3GTo2G(CurAcc[siDeactivate_ACC][0])]
                    if CurAcc[siActivate_ACC] == []:
                        file[fiRehabilitate_ACC] = []
                    else:
                        file[fiRehabilitate_ACC] = [CovertACC3GTo2G(CurAcc[siActivate_ACC][0])]

                        # file[fiRead_ACC] = [CovertACC3GTo2G(CurAcc[siRead_ACC][0])]
                        # file[fiUpdate_ACC] = [CovertACC3GTo2G(CurAcc[siUpdate_ACC][0])]
                        # file[fiIncrease_ACC] = [CovertACC3GTo2G(CurAcc[siIncrease_ACC][0])]
                        # file[fiInvalidate_ACC] = [CovertACC3GTo2G(CurAcc[siDeactivate_ACC][0])]
                        # file[fiRehabilitate_ACC] = [CovertACC3GTo2G(CurAcc[siActivate_ACC][0])]

                DEBUGPRINT("file after modification: " + str(file))

        DEBUGPRINT("FileList After ARR: " + str(FileList))

    # Fourth Pass:
    #   - Add handle for Link file: resolve the link (file type) and check the consistency.
    if OPT_USE_CLIENT:
        runlog_buffer.append("Fourth Pass: Perform Other check/update on File list ...")
    else:
        print "---------------------------------------------"
        print "Fourth Pass: Perform Other check/update on File list ..."
        print "---------------------------------------------"
    for file in FileList:
        # Consistency check here
        # i.e. Check if the 2G Access condition have more than 1 SC
        if OPT_USE_CLIENT:
            runlog_buffer.append(str(file[fiFilePathID]))
        else:
            print file[fiFilePathID]
        # Other check, if any should be done before the information updated

        # check if file pathID does not start from MF
        if file[fiFilePathID][:4] != "3F00":
            file[fiFilePathID] = "3F00" + file[fiFilePathID]
            if OPT_USE_CLIENT:
                runlog_buffer.append("Modified FilePathID : " + str(file[fiFilePathID]))
            else:
                print "Modified FilePathID : " + str(file[fiFilePathID])

        # Update Linked File.
        # - Update Link File that are defined only by "LinkTo" Field (file may not be defined as "Linked File")
        # TODO:
        # - Handle the Link that is only defined as "Link to USIM"
        # if CheckList(file[fiFIleStruct], sFileStructLK):
        if file[fiLinkTo] != '':
            DEBUGPRINT("file: " + str(file))
            linkedfile = None
            for file2 in FileList:
                # DEBUGPRINT("file2: " + str(file2))
                # print "file[fiLinkTo] :" + file[fiLinkTo]
                # print "file2[fiFilePathID] :" + file2[fiFilePathID]
                if file[fiLinkTo] == file2[fiFilePathID]:
                    linkedfile = file2
                    # Consistency check betweek linked file can be done here.
                    # TODO: Need to check for consistency with linked file
                    #   Access condition of 2 linked file can be different.
                    #   File Type, File Size, Record length, number of record, Structure should be the same.
                    #   Content should be the same, but only need to be defined once.
                    #   File content will be checked when testing on actual card.

                    # if found, resolve some information here
                    DEBUGPRINT("file2: " + str(file2))
                    file[fiFileSize] = file2[fiFileSize]
                    file[fiRecordSize] = file2[fiRecordSize]
                    file[fiNumberOfRecord] = file2[fiNumberOfRecord]

                    # Lastly, restore the file structure
                    file[fiFIleStruct] = file2[fiFIleStruct]
                    break;
            # check if linked file found
            if linkedfile == None:
                ERROR("LINKED FILE NOT FOUND!!")
            DEBUGPRINT("file after update: " + str(file))
        else:
            continue

    # ---------------------------------------------------------------------------------------------
    # AT THIS POINT, THE FILE LIST STRUCTURE SHOULD HAVE BEEN FILLED WITH GOOD INFORMATION
    # ---------------------------------------------------------------------------------------------

    # Start Testing/building Script...
    if OptWrite2File:
        OutputFile = open(OutputFileName, 'w')

    if OPT_ERROR_FILE:
        ErrorFile = open(ErrorFileName, 'w')

    if OPT_USE_CLIENT:
        runLog = open(runlogFileName, 'w')

    if DEBUG_LOG:
        DebugFile.writelines("File List :")
        DebugFile.writelines("FieldList" + str(FieldList))
        DebugFile.writelines("\n")
        for file in FileList:
            DebugFile.writelines(str(file))
            DebugFile.writelines(",\n")

        DebugFile.writelines("ARR List :")
        DebugFile.writelines("ARR FieldList : ARRPath, ARR Record Number, Content")
        DebugFile.writelines("\n")
        for ARR in ARRList:
            DebugFile.writelines(str(ARR))
            DebugFile.writelines(",\n")

    verificationErrors = []  # contains dictionaries of errors

    # -------------------------------------------------------------------------------
    # Check 2G Access condition + File Size + structure, record size and content
    # -------------------------------------------------------------------------------
    RECMODE2G_ABS = 0x04
    RECMODE2G_PREV = 0x03
    RECMODE2G_NEXT = 0x02
    if OPT_USE_CLIENT:
        runlog_buffer.append("Test on 2G Context ...")
    else:
        print "-----------------------------------------"
        print "Test on 2G Context ..."
        print "-----------------------------------------"
    
    if InitSCard(ReaderNumber) != 0:
        return False, 'Card not inserted'

    # 2G Secret Code Verification
    PINVerification2G()

    ############### SCANNING CARD  ################
    # Build the list of files in the card using Read Header
    # NOTE: This Script only work on OT card that support Read Header
    # In the future, we might scan the card using another method.
    # CmdReadHeader2G(Number, Mode, expRes, expSw)
    CardFileList = []

    fiCardFilePathID = 0
    fiCardFileType = 1

    curCardFilePath = ''
    prevCardFilePath = ''
    curCardDF = '3F00'
    prevCardDF = ''
    CardDFSecond = ''
    CardDFThird = ''
    curCardFileID = ''
    prevCardFileID = ''
    curCardFileType = ''
    prevCardFileType = ''
    curCardIndex = 0
    prevCardIndex = 0
    prevCardMFIndex = 0

    if OPT_USE_CLIENT:
        runlog_buffer.append("Scanning Card ...")
    else:
        print "-----------------------------------------"
        print "Scanning Card ..."
        print "-----------------------------------------"

    # Build card EF path table
    if OPT_SCANNING_CARD_HEADER == 1:
        index = 1
        ReadHeaderSupported = 1
        while index < 256:
            CmdReadHeader2G(index, 0x04, None, None, NOT_SAVED)
            if sw1 == 0x90 and sw2 == 0x00:
                curCardFileID = toHexString(response[0:2])
                curCardFileID = curCardFileID.replace(" ", "")
                # print("curCardFileID" + '=' + curCardFileID)
                curCardFilePath = curCardDF + curCardFileID
                # print("curCardFilePath" + '=' + curCardFilePath)
                CardFileList.append(curCardFilePath)
                CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                curCardFileType = response[6]
                if curCardFileType == 0x04:
                    CmdSelect2G(curCardDF, None, '9000', NOT_SAVED)
                else:
                    if curCardDF == '3F00':
                        curCardDF = curCardDF + curCardFileID
                        # print("curCardDF" + '=' + curCardDF)
                        prevCardMFIndex = curCardIndex
                        # print("prevCardMFIndex" + '=' + str(prevCardMFIndex))
                        index = 0
                    else:
                        curCardDF = curCardDF + curCardFileID
                        # print("curCardDF" + '=' + curCardDF)
                        prevCardIndex = curCardIndex
                        # print("prevCardIndex" + '=' + str(prevCardIndex))
                        index = 0
            else:
                if (sw1 == 0x94 and sw2 == 0x02) or (sw1 == 0x6A and sw2 == 0x83):
                    # Select the parents, no need to check the result
                    path = FilterHex(curCardDF)
                    i = 0
                    while i < (len(path) - 4):
                        SendAPDU(SELECT2G, path[i:i + 4], None, None, NOT_SAVED)
                        i += 4
                        curCardDF = path[0:i]
                        # print("curCardDF" + '=' + curCardDF)
                        if curCardDF == '3F00':
                            index = prevCardMFIndex + 1
                        else:
                            index = prevCardIndex + 1
                else:
                    ERROR("ERROR Reading Header")
                    ReadHeaderSupported = 0  # Let's assume that Read Header Not supported
                    break
            curCardIndex = index
            # print("curCardIndex" + '=' + str(curCardIndex))
            index += 1

    else:
        index = 1
        ReadHeaderSupported = 0
        if OPT_SCANNING_CARD_DEEP == 1 and OPT_SCANNING_CARD_HEADER == 0:
            for index in xrange(65536):
                # Restart and make sure scanning start from 1st level
                curCardDF = '3F00'
                SendAPDU(SELECT2G, curCardDF, None, None, NOT_SAVED)
                curCardFileID = hex(index)[2:].zfill(4)
                curCardFileID = curCardFileID.upper()
                # print("curCardFileID" + '=' + curCardFileID)
                curCardFilePath = curCardDF + curCardFileID
                # print("curCardFilePath" + '=' + curCardFilePath)
                if curCardFileID != '3F00':
                    prevCardDFList = []
                    # Select the parents, no need to check the result
                    path = FilterHex(curCardFilePath)
                    i = 0
                    while i < (len(path) - 4):
                        SendAPDU(SELECT2G, path[i:i + 4], None, None, NOT_SAVED)
                        i += 4
                    SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                    if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                        pass
                    else:
                        CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                        curCardFileType = response[6]
                        # print("curCardFileType" + "=" + str(curCardFileType))
                        if curCardFileType == 0x04:
                            CardFileList.append(curCardFilePath)
                            pass
                        else:
                            # Scanning 2nd level Dedicated File
                            if OPT_USE_CLIENT:
                                runlog_buffer.append("DF 2nd level")
                            else:
                                print("DF 2nd level")
                            CardDFSecond = curCardFileID
                            prevCardDFList.append(CardDFSecond)
                            # print("prevCardDFList" + "=", prevCardDFList)
                            curCardDF = curCardFilePath
                            # print("curCardDF" + "=" + curCardDF)
                            for index in xrange(65536):
                                curCardFileID = hex(index)[2:].zfill(4)
                                curCardFileID = curCardFileID.upper()
                                # print("curCardFileID" + '=' + curCardFileID)
                                curCardFilePath = curCardDF + curCardFileID
                                # print("curCardFilePath" + '=' + curCardFilePath)
                                if curCardFileID != '3F00' and curCardFileID != curCardFilePath[
                                                                                4:8] and curCardFileID not in prevCardDFList:
                                    # Select the parents, no need to check the result
                                    path = FilterHex(curCardFilePath)
                                    i = 0
                                    while i < (len(path) - 4):
                                        SendAPDU(SELECT2G, path[i:i + 4], None, None, NOT_SAVED)
                                        i += 4
                                    SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                                    if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                                        pass
                                    else:
                                        CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                                        curCardFileType = response[6]
                                        # print("curCardFileType" + "=" + str(curCardFileType))
                                        if curCardFileType == 0x04:
                                            CardFileList.append(curCardFilePath)
                                            pass
                                        else:
                                            # Scanning 2nd level Dedicated File
                                            if OPT_USE_CLIENT:
                                                runlog_buffer.append("DF 3rd level")
                                            else:
                                                print("DF 3rd level")
                                            if int(curCardFilePath[4:6], 16) > int(curCardFileID[:2], 16):
                                                CardDFThird = curCardFileID
                                                prevCardDFList.append(CardDFThird)
                                                # print("prevCardDFList" + "=", prevCardDFList)
                                                curCardDF = curCardFilePath
                                                # print("curCardDF" + "=" + curCardDF)
                                                if len(curCardFilePath) <= 12:
                                                    for index in xrange(65536):
                                                        curCardFileID = hex(index)[2:].zfill(4)
                                                        curCardFileID = curCardFileID.upper()
                                                        # print("curCardFileID" + '=' + curCardFileID)
                                                        curCardFilePath = curCardDF + curCardFileID
                                                        # print("curCardFilePath" + '=' + curCardFilePath)
                                                        if curCardFileID != '3F00' and curCardFileID != curCardFilePath[
                                                                                                        8:12] and curCardFileID not in prevCardDFList:
                                                            # Select the parents, no need to check the result
                                                            path = FilterHex(curCardFilePath)
                                                            i = 0
                                                            while i < (len(path) - 4):
                                                                SendAPDU(SELECT2G, path[i:i + 4], None, None, NOT_SAVED)
                                                                i += 4
                                                            SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                                                            if (sw1 == 0x94 and sw2 == 0x04) or (
                                                                    sw1 == 0x6A and sw2 == 0x82):
                                                                pass
                                                            else:
                                                                CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                                                                curCardFileType = response[6]
                                                                # print("curCardFileType" + "=" + str(curCardFileType))
                                                                if curCardFileType == 0x04:
                                                                    CardFileList.append(curCardFilePath)
                                                                    pass
                                                                else:
                                                                    # 4th level not scanned
                                                                    if OPT_USE_CLIENT:
                                                                        runlog_buffer.append("DF ID wrong")
                                                                    else:
                                                                        print("DF ID wrong")
                                                        else:
                                                            index += 1
                                                curCardDF = CardDFSecond
                                            else:
                                                pass
                                else:
                                    index += 1
                else:
                    index += 1
        else:
            if curCardDF == '3F00':
                # Scanning EF under Master File
                for index in xrange(256):
                    curCardFileID = '2F' + hex(index)[2:].zfill(2)
                    curCardFileID = curCardFileID.upper()
                    # print("curCardFileID" + '=' + curCardFileID)
                    SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                    if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                        pass
                    else:
                        curCardFilePath = curCardDF + curCardFileID
                        # print("curCardFilePath" + '=' + curCardFilePath)
                        CardFileList.append(curCardFilePath)

                # Scanning 1st level Dedicated File
                for index in xrange(256):
                    # Restart and make sure scanning start from 1st level
                    curCardDF = '3F00'
                    SendAPDU(SELECT2G, curCardDF, None, None, NOT_SAVED)
                    curCardFileID = '5F' + hex(index)[2:].zfill(2)
                    curCardFileID = curCardFileID.upper()
                    # print("curCardFileID" + '=' + curCardFileID)
                    SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                    if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                        pass
                    else:
                        curCardFilePath = curCardDF + curCardFileID
                        # print("curCardFilePath" + '=' + curCardFilePath)
                        CardFileList.append(curCardFilePath)
                        prevCardIndex = index
                        curCardDF = curCardFilePath
                        # Scanning EF under Dedicated File
                        for index in xrange(256):
                            curCardFileID = '4F' + hex(index)[2:].zfill(2)
                            curCardFileID = curCardFileID.upper()
                            # print("curCardFileID" + '=' + curCardFileID)
                            SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                            if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                                pass
                            else:
                                curCardFilePath = curCardDF + curCardFileID
                                # print("curCardFilePath" + '=' + curCardFilePath)
                                CardFileList.append(curCardFilePath)
                                CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                                curCardFileType = response[6]
                                if curCardFileType == 0x04:
                                    pass
                                else:
                                    WARNING("DF ID wrong!")
                                    break
                        # Scanning EF under Dedicated File
                        for index in xrange(256):
                            curCardFileID = '6F' + hex(index)[2:].zfill(2)
                            curCardFileID = curCardFileID.upper()
                            # print("curCardFileID" + '=' + curCardFileID)
                            path = FilterHex(curCardDF)
                            i = 0
                            while i < (len(path) - 4):
                                i += 4
                            if curCardFileID != path[i:i + 4]:
                                SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                                if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                                    pass
                                else:
                                    curCardFilePath = curCardDF + curCardFileID
                                    # print("curCardFilePath" + '=' + curCardFilePath)
                                    CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                                    curCardFileType = response[6]
                                    if curCardFileType == 0x04:
                                        CardFileList.append(curCardFilePath)
                                        pass
                                    else:
                                        WARNING("DF ID wrong!")
                                        CmdSelect2G(curCardDF, None, '9000', NOT_SAVED)

                # Scanning 1st level Dedicated File
                for index in xrange(256):
                    # Restart and make sure scanning start from 1st level
                    curCardDF = '3F00'
                    SendAPDU(SELECT2G, curCardDF, None, None, NOT_SAVED)
                    curCardFileID = '6F' + hex(index)[2:].zfill(2)
                    curCardFileID = curCardFileID.upper()
                    # print("curCardFileID" + '=' + curCardFileID)
                    SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                    if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                        pass
                    else:
                        curCardFilePath = curCardDF + curCardFileID
                        # print("curCardFilePath" + '=' + curCardFilePath)
                        CardFileList.append(curCardFilePath)
                        prevCardIndex = index
                        curCardDF = curCardFilePath
                        # Scanning EF under Dedicated File
                        for index in xrange(256):
                            curCardFileID = '4F' + hex(index)[2:].zfill(2)
                            curCardFileID = curCardFileID.upper()
                            # print("curCardFileID" + '=' + curCardFileID)
                            SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                            if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                                pass
                            else:
                                curCardFilePath = curCardDF + curCardFileID
                                # print("curCardFilePath" + '=' + curCardFilePath)
                                CardFileList.append(curCardFilePath)
                                CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                                curCardFileType = response[6]
                                if curCardFileType == 0x04:
                                    pass
                                else:
                                    WARNING("DF ID wrong!")
                                    break
                        # Scanning EF under Dedicated File
                        for index in xrange(256):
                            curCardFileID = '6F' + hex(index)[2:].zfill(2)
                            curCardFileID = curCardFileID.upper()
                            # print("curCardFileID" + '=' + curCardFileID)
                            path = FilterHex(curCardDF)
                            i = 0
                            while i < (len(path) - 4):
                                i += 4
                            if curCardFileID != path[i:i + 4]:
                                SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                                if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                                    pass
                                else:
                                    curCardFilePath = curCardDF + curCardFileID
                                    # print("curCardFilePath" + '=' + curCardFilePath)
                                    CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                                    curCardFileType = response[6]
                                    if curCardFileType == 0x04:
                                        CardFileList.append(curCardFilePath)
                                        pass
                                    else:
                                        WARNING("DF ID wrong!")
                                        CmdSelect2G(curCardDF, None, '9000', NOT_SAVED)

                # Scanning 1st level Dedicated File
                for index in xrange(256):
                    # Restart and make sure scanning start from 1st level
                    curCardDF = '3F00'
                    SendAPDU(SELECT2G, curCardDF, None, None, NOT_SAVED)
                    curCardFileID = '7F' + hex(index)[2:].zfill(2)
                    curCardFileID = curCardFileID.upper()
                    # print("curCardFileID" + '=' + curCardFileID)
                    SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                    if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                        pass
                    else:
                        curCardFilePath = curCardDF + curCardFileID
                        # print("curCardFilePath" + '=' + curCardFilePath)
                        CardFileList.append(curCardFilePath)
                        prevCardIndex = index
                        curCardDF = curCardFilePath
                        # Scanning EF under Dedicated File
                        for index in xrange(256):
                            curCardFileID = '5F' + hex(index)[2:].zfill(2)
                            curCardFileID = curCardFileID.upper()
                            # print("curCardFileID" + '=' + curCardFileID)
                            path = FilterHex(curCardDF)
                            i = 0
                            while i < (len(path) - 4):
                                i += 4
                            if curCardFileID != path[i:i + 4]:
                                SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                                if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                                    pass
                                else:
                                    curCardFilePath = curCardDF + curCardFileID
                                    # print("curCardFilePath" + '=' + curCardFilePath)
                                    CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                                    curCardFileType = response[6]
                                    if curCardFileType == 0x04:
                                        CardFileList.append(curCardFilePath)
                                        pass
                                    else:
                                        # Scanning 2nd level Dedicated File
                                        print("DF 2nd level")
                                        prevCardDF = curCardDF
                                        curCardDF = curCardFilePath
                                        # Scanning EF under Dedicated File
                                        for index in xrange(256):
                                            curCardFileID = '4F' + hex(index)[2:].zfill(2)
                                            curCardFileID = curCardFileID.upper()
                                            # print("curCardFileID" + '=' + curCardFileID)
                                            SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                                            if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                                                pass
                                            else:
                                                curCardFilePath = curCardDF + curCardFileID
                                                # print("curCardFilePath" + '=' + curCardFilePath)
                                                CardFileList.append(curCardFilePath)
                                                CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                                                curCardFileType = response[6]
                                                if curCardFileType == 0x04:
                                                    pass
                                                else:
                                                    WARNING("DF ID wrong!")
                                                    break
                                        # Scanning EF under Dedicated File
                                        for index in xrange(256):
                                            curCardFileID = '6F' + hex(index)[2:].zfill(2)
                                            curCardFileID = curCardFileID.upper()
                                            # print("curCardFileID" + '=' + curCardFileID)
                                            path = FilterHex(curCardDF)
                                            i = 0
                                            while i < (len(path) - 4):
                                                i += 4
                                            if curCardFileID != path[i:i + 4]:
                                                SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                                                if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                                                    pass
                                                else:
                                                    curCardFilePath = curCardDF + curCardFileID
                                                    # print("curCardFilePath" + '=' + curCardFilePath)
                                                    CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                                                    curCardFileType = response[6]
                                                    if curCardFileType == 0x04:
                                                        CardFileList.append(curCardFilePath)
                                                        pass
                                                    else:
                                                        WARNING("DF ID wrong!")
                                                        CmdSelect2G(curCardDF, None, '9000', NOT_SAVED)
                                                        # curCardDF = prevCardDF
                                                        # print("curCardDF" + "=" + curCardDF)
                                                        # CmdSelect2G(curCardDF, None, '9000', NOT_SAVED)

                        # Scanning EF under Dedicated File
                        for index in xrange(256):
                            curCardFileID = '6F' + hex(index)[2:].zfill(2)
                            curCardFileID = curCardFileID.upper()
                            # print("curCardFileID" + '=' + curCardFileID)
                            path = FilterHex(curCardDF)
                            i = 0
                            while i < (len(path) - 4):
                                i += 4
                            if curCardFileID != path[i:i + 4]:
                                SendAPDU(SELECT2G, curCardFileID, None, None, NOT_SAVED)
                                if (sw1 == 0x94 and sw2 == 0x04) or (sw1 == 0x6A and sw2 == 0x82):
                                    pass
                                else:
                                    curCardFilePath = curCardDF + curCardFileID
                                    # print("curCardFilePath" + '=' + curCardFilePath)
                                    CmdSelect2G(curCardFilePath, None, '9000', NOT_SAVED)
                                    curCardFileType = response[6]
                                    if curCardFileType == 0x04:
                                        CardFileList.append(curCardFilePath)
                                        pass
                                    else:
                                        WARNING("DF ID wrong!")
                                        CmdSelect2G(curCardDF, None, '9000', NOT_SAVED)

    # Card path compared with docB
    not_exist_docb = []
    tempFileList = []
    # tempCardFileList = [curCardFilePath for curCardFilePath in CardFileList if fFilePath[0] in FileList]

    for z in range(0, len(FileList)):
        tempFileList.append(FileList[z][0])
        z += 1

    for x in CardFileList:
        if x not in tempFileList:
            if OPT_USE_CLIENT:
                runlog_buffer.append(str(x) + " " + "not exist in DocB")
            else:
                print(x + " " + "not exist in DocB")
            not_exist_docb.append(x)

    ############### END OF SCANNING CARD  ################

    prevFile = ''
    curFile = ''
    curFileDescName = ''
    curOps = ''
    curRec = 0
    curLinkedFile = ''
    RecordList = []
    for file in FileList:
        # DEBUGPRINT("file: " + str(file))
        curFile = file[fiFilePathID]
        efMarker = str(curFile)
        curFileDescName = file[fiFileName]
        tmpContent = file[fiContent]
        if curFile != prevFile:
            if OPT_USE_CLIENT:
                progress(FileList.index(file), len(FileList), status=str(formatFileId(curFile)))
                runlog_buffer.append("Test Access Condition for " + str(curFile))
            else:
                print "Test Access Condition for " + curFile
                print "-----------------------------------------"
            curOps = 'Test Access Condition'
            RecordList = []  # Reset Record list if it is a new file, to track the record that has been tested
            expected = "XXXX"  # ignore first 2 bytes
            Type = FileType2G(file[fiFileType])
            if Type == "04" and file[fiFileSize] != 0:  # ignore if File size is zero
                expected += "%0.4X" % file[fiFileSize]  # check file size
            else:
                expected += "XXXX"  # ignore size for MF or DF

            expected += file[fiFilePathID][len(file[fiFilePathID]) - 4:]  # check file ID
            expected += Type  # check file type
            expected += "XX"  # ignore 1 bytes  (indicator for increase)
            if Type == "04":  # check access condition
                if file[fiRead_ACC] == []:
                    read = 'X'
                else:
                    if len(file[fiRead_ACC]) == 1:
                        read = ("%0.1X" % file[fiRead_ACC][0])
                    else:
                        if OPT_2G_ACC == 0:
                            read = ("%0.1X" % file[fiRead_ACC][0])
                        elif OPT_2G_ACC == 1:
                            read = ("%0.1X" % file[fiRead_ACC][1])
                        else:
                            read = ("%0.1X" % file[fiRead_ACC][0])

                if file[fiUpdate_ACC] == []:
                    update = 'X'
                else:
                    if len(file[fiUpdate_ACC]) == 1:
                        update = ("%0.1X" % file[fiUpdate_ACC][0])
                    else:
                        if OPT_2G_ACC == 0:
                            update = ("%0.1X" % file[fiUpdate_ACC][0])
                        elif OPT_2G_ACC == 1:
                            update = ("%0.1X" % file[fiUpdate_ACC][1])
                        else:
                            update = ("%0.1X" % file[fiUpdate_ACC][0])
                expected += read + update  # Read Update

                if file[fiIncrease_ACC] == []:
                    increase = 'X'
                else:
                    if len(file[fiIncrease_ACC]) == 1:
                        increase = ("%0.1X" % file[fiIncrease_ACC][0])
                    else:
                        if OPT_2G_ACC == 0:
                            increase = ("%0.1X" % file[fiIncrease_ACC][0])
                        elif OPT_2G_ACC == 1:
                            increase = ("%0.1X" % file[fiIncrease_ACC][1])
                        else:
                            increase = ("%0.1X" % file[fiIncrease_ACC][0])
                expected += increase + 'X'  # increase

                if file[fiRehabilitate_ACC] == []:
                    rehabilitate = 'X'
                else:
                    if len(file[fiRehabilitate_ACC]) == 1:
                        rehabilitate = ("%0.1X" % file[fiRehabilitate_ACC][0])
                    else:
                        if OPT_2G_ACC == 0:
                            rehabilitate = ("%0.1X" % file[fiRehabilitate_ACC][0])
                        elif OPT_2G_ACC == 1:
                            rehabilitate = ("%0.1X" % file[fiRehabilitate_ACC][1])
                        else:
                            rehabilitate = ("%0.1X" % file[fiRehabilitate_ACC][0])

                if file[fiInvalidate_ACC] == []:
                    invalidate = 'X'
                else:
                    if len(file[fiInvalidate_ACC]) == 1:
                        invalidate = ("%0.1X" % file[fiInvalidate_ACC][0])
                    else:
                        if OPT_2G_ACC == 0:
                            invalidate = ("%0.1X" % file[fiInvalidate_ACC][0])
                        elif OPT_2G_ACC == 1:
                            invalidate = ("%0.1X" % file[fiInvalidate_ACC][1])
                        else:
                            invalidate = ("%0.1X" % file[fiInvalidate_ACC][0])
                expected += rehabilitate + invalidate  # REH-INV
            else:
                expected += "XXXXXX"  # ignore access condition for MF or DF
            expected += "XXXX"  # ignore byte 12-13
            # structure
            structure = "FF"
            if Type == "04":
                structure = FileStructure2G(file[fiFIleStruct])
                expected += structure  # check Structure
            else:
                expected += "XX"  # ignore structure for MF or DF
            # Length of Record
            if Type == "04" and (structure == "01" or structure == "03"):
                expected += "%0.2X" % file[fiRecordSize]  # check record length
            else:
                expected += "XX"  # ignore record length for MF or DF or EF
            if not formatFileId(curFile) == None:
                OutputFile.writelines('\n; ' + formatFileId(curFile) + ': ' + curFileDescName + '\n')
            else:
                OutputFile.writelines('\n; ' + 'NoneType' + ': ' + curFileDescName + '\n')
            CmdSelect2G(file[fiFilePathID], expected, None)
            TempStatus2G = copy.deepcopy(response)  # to compare with linked file if needed
        
        if not OPT_CHECK_CONTENT_3G:
            # -------------------------------------------------------------------------------
            # Check File Content
            # -------------------------------------------------------------------------------
            # TODO HERE
            # def CmdReadBinary2G(Offset, Le, expRes, expSw):
            # def CmdUpdateBinary2G(Offset, Lc, Data, expSw):
            # def CmdReadRecord2G(RecordNumber, Mode, Le, expRes, expSw):
            # def CmdUpdateRecord2G(RecordNumber, Mode, Lc, Data, expSw):

            # Some DOC B does not define 2G access condition, so the 2G access condition are empty.
            # The 2G content are always checked for now.
            VarName = None
            TempValue = []
            # if True:
            # if file[fiRead_ACC] != [] and file[fiRead_ACC][0] != iAccNEV:
            if file[fiRead_ACC] == [] or file[fiRead_ACC][0] != iAccNEV:

                if file[fiContent].startswith('%'):
                    tempContent = file[fiContent]  # Handle variable name
                else:
                    tempContent = FilterString(file[fiContent])  # Filter content

                # if file[fiContent] != '':
                if tempContent != '':
                    if OPT_USE_CLIENT:
                        runlog_buffer.append("Test File Content for " + str(curFile))
                    else:
                        print "Test File Content for " + curFile
                        print "-----------------------------------------"
                    curOps = 'Test File Content'
                    if CheckList(file[fiFileType], sFileTypeMF) or \
                            CheckList(file[fiFileType], sFileTypeDF) or \
                            CheckList(file[fiFileType], sFileTypeADF):
                        pass
                    else:
                        # Only check content if the content is not empty and it is an EF.
                        # Rule #1: length of the content reference is less than the actual length in the EF,
                        #   The remaining value are not checked. (this already handled by SendAPDU function)
                        # Rule #2: If length of the content reference is longer than the actual length in EF,
                        #   the content reference shall be truncated up to the length in the EF.
                        #   Warning shall be issued. (handle in SendAPDU)

                        # ExpectedResponse = file[fiContent]
                        # ExpectedLength = len(file[fiContent])/2

                        VarValue = None
                        tempPercentOffset = tempContent.find('%')
                        if tempPercentOffset != -1:
                            tempSpaceOffset = tempContent.find(' ')
                            if tempSpaceOffset != -1:
                                # a variable name has been found
                                VarName = tempContent[tempPercentOffset:tempSpaceOffset]
                                DEBUGPRINT("VarName: " + str(VarName))

                                if VarName[1:] in VarList:
                                    VarValue = VarList.get(VarName[1:])
                                elif 'GSM_' + VarName[1:] in VarList:  # search GSM file in varList
                                    VarValue = VarList.get('GSM_' + VarName[1:])
                                elif 'USIM_' + VarName[1:] in VarList:  # search USIM file in varList
                                    VarValue = VarList.get('USIM_' + VarName[1:])
                                else:
                                    VarValue = ''
                                if OPT_USE_CLIENT:
                                    runlog_buffer.append('VarValue: ' + str(VarValue))
                                else:
                                    print('VarValue: ' + str(VarValue))
                            else:
                                # Ending space not found, assuming until end of the text
                                VarName = tempContent[tempPercentOffset:]
                                DEBUGPRINT("VarName: " + str(VarName))

                                if VarName[1:] in VarList:
                                    VarValue = VarList.get(VarName[1:])
                                elif 'GSM_' + VarName[1:] in VarList:
                                    VarValue = VarList.get('GSM_' + VarName[1:])
                                elif 'USIM_' + VarName[1:] in VarList:
                                    VarValue = VarList.get('USIM_' + VarName[1:])
                                else:
                                    VarValue = None

                                if VarName == '': VarName = None  # Handle if text empty
                                # VarValue = GetVarValue(VarName[1:])  # ignore the percent sign
                                if OPT_USE_CLIENT:
                                    runlog_buffer.append('VarValue: ' + str(VarValue))
                                else:
                                    print('VarValue: ' + str(VarValue))

                        # Rule #3: if the content start with %, it means variable, and followed by variable name.
                        #   The variable name are started with'%' (percent) sign followed by variable name and a space
                        #   In example 1234 %VAR1 5678. The content of variable is mentioned in VarList()
                        #   if the variable is at the end of the string, space is not required.
                        #   For example: "123456 %VAR1"
                        #   When variable is used, usually an exact value is expected. So, OPT_EXPECTED_PADDING
                        #       is not supported when a variable exist in the expected data.

                        if CheckList(file[fiFIleStruct], sFileStructLF) or \
                                CheckList(file[fiFIleStruct], sFileStructCY):
                            # Rule #4:
                            # for Linear Fixed/Cyclic, First check the files with the record number, and keep the list.
                            if VarValue == None:
                                # Padding can only be done if there is no variable at the moment
                                ExpectedResponse = tempContent
                                ExpectedLength = len(tempContent) / 2
                                if OPT_EXPECTED_PADDING:
                                    LastByte = ExpectedResponse[(ExpectedLength * 2) - 2:]
                                    while ExpectedLength < int(file[fiRecordSize]):
                                        ExpectedResponse += LastByte
                                        ExpectedLength += 1

                                if VarName:  # handle case where CSV variable name is not found in AdvSave
                                    # Need to print the variable name to aid the modification of PCOM script.
                                    if OptWrite2File:
                                        OutputFile.writelines(";; Variable Used. Original Value: ")
                                        OutputFile.writelines(tempContent)
                                        OutputFile.writelines('\n')

                            else:
                                # Replace with Value, no padding

                                ExpectedResponse = tempContent[:tempPercentOffset]
                                ExpectedResponse += VarValue
                                if tempSpaceOffset != -1:
                                    ExpectedResponse += tempContent[tempSpaceOffset + 1:]
                                ExpectedResponse = FilterString(ExpectedResponse)
                                ExpectedLength = len(ExpectedResponse) / 2

                                # Need to print the variable name to aid the modification of PCOM script.
                                if OptWrite2File:
                                    OutputFile.writelines(";; Variable Used. Original Value: ")
                                    OutputFile.writelines(tempContent)
                                    OutputFile.writelines('\n')

                            if file[fiRecordNumber] != '':
                                RecordList.append(int(file[fiRecordNumber]))  # Content Record number always decimal
                                curRec = int(file[fiRecordNumber])
                                CmdReadRecord2G(int(file[fiRecordNumber]), RECMODE2G_ABS, int(file[fiRecordSize]),
                                                ExpectedResponse, "9000")
                                TempValue = copy.deepcopy(response)
                            # Rule #5: If a content found that is without a record number,
                            #   all the record within the same file shall be checked (except those files that are already checked).
                            #   For simplicity, such content (without record number) shall be the last content in the list for the same EF.
                            #   All record content of an EF shall be in defined consecutively in the list.
                            else:
                                index = 1
                                # if OPT_USE_CLIENT:
                                #     runlog_buffer.append('NumOfRec' + str(file[fiNumberOfRecord]))
                                #     runlog_buffer.append('RecordList ' + str(RecordList))
                                # else:
                                #     print('NumOfRec' + str(file[fiNumberOfRecord]))
                                #     print('RecordList ' + str(RecordList))
                                while index <= file[fiNumberOfRecord]:
                                    Found = 0
                                    for a in RecordList:
                                        if a == index:
                                            Found = 1
                                            break
                                    # if OPT_USE_CLIENT:
                                    #     runlog_buffer.append('Found ' + str(Found))
                                    # else:
                                    #     print('Found ' + str(Found))
                                    if Found == 0:
                                        # Not tested yet, read the content
                                        curRec = index
                                        CmdReadRecord2G(index, RECMODE2G_ABS, int(file[fiRecordSize]), ExpectedResponse,
                                                        "9000")
                                        TempValue = copy.deepcopy(response)
                                    index += 1
                        else:
                            # For Transparent, just check the file content
                            if VarValue == None:
                                ExpectedResponse = tempContent
                                ExpectedLength = len(tempContent) / 2
                                # Padding can only be done if there is no variable
                                if OPT_EXPECTED_PADDING:
                                    LastByte = ExpectedResponse[(ExpectedLength * 2) - 2:]
                                    while ExpectedLength < int(file[fiFileSize]):
                                        ExpectedResponse += LastByte
                                        ExpectedLength += 1

                                if VarName:  # handle case where CSV variable name is not found in AdvSave
                                    # Need to print the variable name to aid the modification of PCOM script.
                                    if OptWrite2File:
                                        OutputFile.writelines(";; Variable Used. Original Value: ")
                                        OutputFile.writelines(tempContent)
                                        OutputFile.writelines('\n')

                            else:
                                # Replace with Value, no padding
                                ExpectedResponse = tempContent[:tempPercentOffset]
                                ExpectedResponse += VarValue
                                if tempSpaceOffset != -1:
                                    ExpectedResponse += tempContent[tempSpaceOffset + 1:]
                                ExpectedResponse = FilterString(ExpectedResponse)
                                ExpectedLength = len(ExpectedResponse) / 2

                                # Need to print the variable name to aid the modification of PCOM script.
                                if OptWrite2File:
                                    OutputFile.writelines(";; Variable Used. Original Value: ")
                                    OutputFile.writelines(tempContent)
                                    OutputFile.writelines('\n')

                            # Handle lenght more than 1 APDU
                            index = 0
                            while index < int(file[fiFileSize]):
                                if OPT_USE_CLIENT:
                                    runlog_buffer.append('Index: {}, ExpectedLength {}'.format(index, ExpectedLength))
                                else:
                                    print('Index: {}, ExpectedLength {}'.format(index, ExpectedLength))
                                if index >= ExpectedLength:
                                    WARNING("Expected Length is longer than file size")
                                    break
                                if (index + MAX_RESPONSE_LEN) > int(file[fiFileSize]):
                                    TempLen = int(file[fiFileSize]) - index
                                else:
                                    TempLen = MAX_RESPONSE_LEN

                                ##CmdReadBinary2G(index, TempLen, ExpectedResponse[(index*2):], "9000")

                                # Fix the expected data of Binary file >128 issue
                                # Method 1
                                # Buffer = ''
                                # i = 0
                                # while i<TempLen and ((index+i)*2)< len(ExpectedResponse):
                                #    #Buffer += ExpectedResponse[(index+i)*2] + ExpectedResponse[((index+i)*2)+1]
                                #    Buffer += ExpectedResponse[(index+i)*2:(index+i+1)*2]
                                #    i += 1
                                # CmdReadBinary2G(index, TempLen, Buffer, "9000")

                                # Method 2
                                curRec = 0
                                CmdReadBinary2G(index, TempLen, ExpectedResponse[(index * 2):((index + TempLen) * 2)],
                                                "9000")

                                TempValue += copy.deepcopy(response)
                                index += TempLen
                else:
                    # just read the content without checking the value
                    if curFile != prevFile:  # only check the first one for linear fixed
                        if OPT_USE_CLIENT:
                            runlog_buffer.append("Read File Content for " + curFile)
                        else:
                            print "Read File Content for " + curFile
                            print "-----------------------------------------"
                        if CheckList(file[fiFileType], sFileTypeMF) or \
                                CheckList(file[fiFileType], sFileTypeDF) or \
                                CheckList(file[fiFileType], sFileTypeADF):
                            pass
                        else:
                            if CheckList(file[fiFIleStruct], sFileStructLF) or \
                                    CheckList(file[fiFIleStruct], sFileStructCY):
                                if file[fiRecordSize] != 0:
                                    if file[fiRecordNumber] != '':
                                        curRec = int(file[fiRecordNumber])
                                        # CmdReadRecord2G(int(file[fiRecordNumber]), RECMODE2G_ABS, int(file[fiRecordSize]), None,
                                        #                 "9000", NOT_SAVED)
                                        CmdReadRecord2G(int(file[fiRecordNumber]), RECMODE2G_ABS, int(file[fiRecordSize]),
                                                        None,
                                                        "9000")
                                        TempValue = copy.deepcopy(response)
                                    else:
                                        # Not defined? Only Read Record #1
                                        curRec = 1
                                        # CmdReadRecord2G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000", NOT_SAVED)
                                        CmdReadRecord2G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000")
                                        TempValue = copy.deepcopy(response)
                                else:
                                    # zero record size
                                    pass
                            else:
                                # For Transparent, just check the file content
                                # Handle lenght more than 1 APDU
                                index = 0
                                while index < int(file[fiFileSize]):  # Todo: should check with real file size
                                    if (index + MAX_RESPONSE_LEN) > int(file[fiFileSize]):
                                        TempLen = int(file[fiFileSize]) - index
                                    else:
                                        TempLen = MAX_RESPONSE_LEN
                                    curRec = 0
                                    # CmdReadBinary2G(index, TempLen, None, "9000", NOT_SAVED)
                                    CmdReadBinary2G(index, TempLen, None, "9000")
                                    TempValue += copy.deepcopy(response)
                                    index += TempLen
                    else:
                        pass

                # check content (2g) ends here

        if not OPT_CHECK_LINK3G:
            # -------------------------------------------------------------------------------
            # Check linked file in 2G mode
            # -------------------------------------------------------------------------------
            # TODO HERE
            # If the file is linked to other files, read the current file and the other file. The content shall be the same.
            TempValue2 = []
            if file[fiLinkTo] != '' and \
                    (file[fiRead_ACC] == [] or file[fiRead_ACC][0] != iAccNEV) and \
                            curFile != prevFile:  # only check the first one for linear fixed
                if OPT_USE_CLIENT:
                    runlog_buffer.append("Check Linked File to : " + str(file[fiLinkTo]))
                else:
                    print "Check Linked File to : " + file[fiLinkTo]
                    print "-----------------------------------------"
                curOps = 'Check Linked File'
                curLinkedFile = file[fiLinkTo]
                for file2 in FileList:
                    # DEBUGPRINT("file2: " + str(file2))
                    if file[fiLinkTo] == file2[fiFilePathID]:
                        linkedfile = file2
                        CmdSelect2G(file2[fiFilePathID], None, None, NOT_SAVED)
                        if TempStatus2G != response:
                            # Note: The file ID (or some other header) of the linked file could be different.
                            #   Set as warning for now
                            #   TODO: Check the difference: File Size, record size, number of record should be the same
                            #           Access condition and File ID can be different does not need to be checked.
                            WARNING(" Different Linked file Status !!")
                            # if OPT_ERROR_FILE:
                            # appendVerifError(curFile, curLinkedFile, curOps, 'Different Linked file Status', 0, '', 0, '', curFileDescName)
                            # break
                        if CheckList(file2[fiFIleStruct], sFileStructLF) or \
                                CheckList(file2[fiFIleStruct], sFileStructCY):
                            # need to handle the empty record number
                            if file[fiRecordSize] != 0:
                                if file[fiRecordNumber] != '':
                                    # Check the original file for record number, only check if the record number exist
                                    CmdReadRecord2G(int(file[fiRecordNumber]), RECMODE2G_ABS, int(file[fiRecordSize]), None,
                                                    "9000", NOT_SAVED)
                                    TempValue2 = copy.deepcopy(response)
                                else:
                                    CmdReadRecord2G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000", NOT_SAVED)
                                    TempValue2 = copy.deepcopy(response)
                                    ##stop checking if no record number
                                    # break
                        else:
                            index = 0
                            while index < int(file2[fiFileSize]):
                                # if index >= ExpectedLength:
                                #    break
                                if (index + MAX_RESPONSE_LEN) > int(file2[fiFileSize]):
                                    TempLen = int(file2[fiFileSize]) - index
                                else:
                                    TempLen = MAX_RESPONSE_LEN
                                CmdReadBinary2G(index, TempLen, None, "9000", NOT_SAVED)
                                TempValue2 += copy.deepcopy(response)
                                index += TempLen
                        if TempValue2 != TempValue:
                            # For sure linked file must have same values. Error if not the same.
                            ERROR(" Different Linked file Value !!")
                            if OPT_ERROR_FILE:
                                appendVerifError(curFile, curLinkedFile, curOps, 'Different Linked file Value', 0, '', 0,
                                                '', curFileDescName)
                        if OPT_CHECK_LINK_UPDATE:
                            # The other file linked to shall be updated, and the current file to be selected and read again.
                            #   The content should be updated in the current file.

                            if OPT_USE_CLIENT:
                                runlog_buffer.append("Test UPDATE Linked File: " + str(file[fiLinkTo]))
                            else:
                                print "Test UPDATE Linked File: " + file[fiLinkTo]
                                print "-----------------------------------------"
                            curOps = 'Test UPDATE Linked File'
                            # print "TempValue :" + toHexString(TempValue)
                            # print "TempValue2 :" + toHexString(TempValue2)

                            # invert all data
                            # for a in TempValue2:   # Not working, value cannot be changed in for loop
                            #    a = a^0xFF
                            # for i, s in enumerate(TempValue2): TempValue2[i] = TempValue2[i]^0xFF  # This might also work
                            TempValue2[:] = [a ^ 0xFF for a in TempValue2]
                            # print toHexString(TempValue2)
                            TempValue = []  # Reset TempValue
                            if TempValue2 == []:
                                WARNING(" Linked file cannot be read/updated !!")
                                if OPT_ERROR_FILE:
                                    appendVerifError(curFile, curLinkedFile, curOps, 'Linked file cannot be read/updated',
                                                    0, '', 0, '', curFileDescName)
                            else:
                                if CheckList(file2[fiFIleStruct], sFileStructLF):
                                    if file[fiRecordSize] != 0:
                                        if file[fiRecordNumber] != '':
                                            CmdUpdateRecord2G(int(file[fiRecordNumber]), RECMODE2G_ABS,
                                                            int(file[fiRecordSize]),
                                                            TempValue2, "9000", NOT_SAVED)
                                            CmdSelect2G(file[fiFilePathID], expected, "9000",
                                                        NOT_SAVED)  # Select back the original file
                                            CmdReadRecord2G(int(file[fiRecordNumber]), RECMODE2G_ABS,
                                                            int(file[fiRecordSize]),
                                                            None, "9000", NOT_SAVED)
                                            TempValue = copy.deepcopy(response)
                                        else:
                                            CmdUpdateRecord2G(1, RECMODE2G_ABS, int(file[fiRecordSize]), TempValue2, "9000",
                                                            NOT_SAVED)
                                            CmdSelect2G(file[fiFilePathID], expected, "9000",
                                                        NOT_SAVED)  # Select back the original file
                                            CmdReadRecord2G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000",
                                                            NOT_SAVED)
                                            TempValue = copy.deepcopy(response)
                                            # break
                                elif CheckList(file2[fiFIleStruct], sFileStructCY):
                                    if file[fiRecordSize] != 0:
                                        CmdUpdateRecord2G(0, RECMODE2G_PREV, int(file[fiRecordSize]), TempValue2, "9000",
                                                        NOT_SAVED)
                                        CmdSelect2G(file[fiFilePathID], expected, "9000",
                                                    NOT_SAVED)  # Select back the original file
                                        CmdReadRecord2G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000", NOT_SAVED)
                                        TempValue = copy.deepcopy(response)
                                        # break
                                else:
                                    index = 0
                                    while index < int(file2[fiFileSize]):
                                        # if index >= ExpectedLength:
                                        #    break
                                        if (index + 255) > int(file2[fiFileSize]):
                                            TempLen = int(file2[fiFileSize]) - index
                                        else:
                                            TempLen = 255
                                        Buffer = []
                                        i = 0
                                        while i < TempLen and (index + i) < len(TempValue2):
                                            Buffer.append(TempValue2[index + i])
                                            i += 1
                                        CmdUpdateBinary2G(index, TempLen, Buffer, "9000", NOT_SAVED)
                                        # CmdUpdateBinary2G(index, TempLen, TempValue2[index:], "9000")
                                        index += TempLen

                                    CmdSelect2G(file[fiFilePathID], expected, "9000",
                                                NOT_SAVED)  # Select back the original file
                                    index = 0
                                    while index < int(file[fiFileSize]):
                                        # if index >= ExpectedLength:
                                        #    break
                                        if (index + 255) > int(file[fiFileSize]):
                                            TempLen = int(file[fiFileSize]) - index
                                        else:
                                            TempLen = 255
                                        CmdReadBinary2G(index, TempLen, None, "9000", NOT_SAVED)
                                        TempValue += copy.deepcopy(response)
                                        index += TempLen

                                # if TempValue2 == [] or TempValue == []:    # Avoid error when the linked file cannot be updated (i.e. access condition never)
                                if TempValue == []:  # Avoid error when the linked file cannot be updated (i.e. access condition never)
                                    WARNING(" Linked file cannot be read !!")
                                    if OPT_ERROR_FILE:
                                        appendVerifError(curFile, curLinkedFile, curOps, 'Linked file cannot be read', 0,
                                                        '', 0, '', curFileDescName)
                                else:
                                    if TempValue2 != TempValue:
                                        ERROR(" Different UPDATED Linked file Value !!")
                                        if OPT_ERROR_FILE:
                                            appendVerifError(curFile, curLinkedFile, curOps,
                                                            'Different UPDATED Linked file Value', 1, '', 0, '',
                                                            curFileDescName)

                                # Revert back the value to avoid issue when linked file read later
                                # -----------------------------------------------------
                                TempValue2[:] = [a ^ 0xFF for a in TempValue2]

                                TempValue = []  # Reset TempValue
                                CmdSelect2G(file2[fiFilePathID], None, "9000", NOT_SAVED)  # Select The Linked File
                                if CheckList(file2[fiFIleStruct], sFileStructLF):
                                    if file[fiRecordSize] != 0:
                                        if file[fiRecordNumber] != '':
                                            CmdUpdateRecord2G(int(file[fiRecordNumber]), RECMODE2G_ABS,
                                                            int(file2[fiRecordSize]), TempValue2, "9000", NOT_SAVED)
                                        else:
                                            CmdUpdateRecord2G(1, RECMODE2G_ABS, int(file2[fiRecordSize]), TempValue2,
                                                            "9000",
                                                            NOT_SAVED)
                                elif CheckList(file2[fiFIleStruct], sFileStructCY):
                                    # There is no point updating Cyclic file as it cannot be returned to original state without updating all record.
                                    # CmdUpdateRecord2G(0, RECMODE2G_PREV, int(file[fiRecordSize]), TempValue2, "9000")
                                    pass
                                else:
                                    index = 0
                                    while index < int(file2[fiFileSize]):
                                        # if index >= ExpectedLength:
                                        #    break
                                        if (index + 128) > int(file2[fiFileSize]):
                                            TempLen = int(file2[fiFileSize]) - index
                                        else:
                                            TempLen = 128
                                        Buffer = []
                                        i = 0
                                        while i < TempLen and (index + i) < len(TempValue2):
                                            Buffer.append(TempValue2[index + i])
                                            i += 1
                                        CmdUpdateBinary2G(index, TempLen, Buffer, "9000", NOT_SAVED)
                                        index += TempLen

                        break;  # No need to check further if already found

        # TODO:
        # Check if the files is in header and mark the file (CardFileList)
        #   If the file is not found in the File List, Return Error

        prevFile = curFile

    # TODO:
    # Check if Any files not marked in CardFileList, and produce warning.

    # -------------------------------------------------------------------------------
    # Check 3G Access condition (read ARR), shareable status, Filesize, structure, record size, SFI, and content.
    #   Reset required after 2G mode.
    # -------------------------------------------------------------------------------
    if OPT_USE_CLIENT:
        runlog_buffer.append("Test on 3G Context ...")
    else:
        print "-----------------------------------------"
        print "Test on 3G Context ..."
        print "-----------------------------------------"
    
    EXP_FROM_CARD = 1

    if InitSCard(ReaderNumber) != 0:
        return False, 'Card not inserted'

    if OPT_SELECT3G_ADF == 1:
        CmdSelect3GADF(ADF_AID_LENGTH)

    # 3G Secret Code Verification
    PINVerification3G()

    prevFile = ''
    curFile = ''
    curFileDescName = ''
    curOps = ''
    curRec = 0
    curLinkedFile = ''
    not_exist_mandatory = []
    RecordList = []
    for file in FileList:
        DEBUGPRINT("file: " + str(file))
        curFile = file[fiFilePathID]
        efMarker = str(curFile)
        curFileDescName = file[fiFileName]
        tmpContent = file[fiContent]
        if curFile != prevFile:
            if OPT_USE_CLIENT:
                progress(FileList.index(file), len(FileList), status=str(formatFileId(curFile)))
                runlog_buffer.append("\nTesting " + curFile)
                runlog_buffer.append("Test File Control Parameters for " + curFile)
            else:
                print "Test Access Condition for " + curFile
                print "-----------------------------------------"
            curOps = 'Test 3G Status'
            RecordList = []  # Reset Record list if it is a new file, to track the record that has been tested

            if not formatFileId(curFile) == None:
                OutputFile.writelines('\n; ' + formatFileId(curFile) + ': ' + curFileDescName + '\n')
            else:
                OutputFile.writelines('\n; ' + 'NoneType' + ': ' + curFileDescName + '\n')
            CmdSelect3G(file[fiFilePathID], None, None)

            FileDescriptor = SearchTLV(0x82, response[2:])
            # if OPT_USE_CLIENT:
            #     runlog_buffer.append(str(FileDescriptor))
            #     runlog_buffer.append(str(file))
            #     runlog_buffer.append(str(response[2:]))
            # else:
            #     print(FileDescriptor)
            #     print(file)
            #     print(response[2:])

            if FileDescriptor == []:
                ERROR("File Not found in the Card!!")
                if OPT_ERROR_FILE:
                    appendVerifError(curFile, '', curOps, 'File Not found in the Card', 1, '', 0, '', curFileDescName)
                prevFile = curFile
                not_exist_mandatory.append(curFile)
                if file[fiMandatory] == True:
                    ERROR("This File is Mandatory!")
                else:
                    pass
                continue  # Skip the next check if the file not found
            else:
                file[fiMandatory] = False
                WARNING("This File either Optional or Not defined")

            ARRRef = SearchTLV(0x8B, response[2:])
            # ABQ
            if ARRRef == []:
                SecurityExpanded = SearchTLV(0xAB, response[2:])
                if SecurityExpanded == []:
                    # Expanded format not supported
                    SecurityCompact = SearchTLV(0x8C, response[2:])
                    if SecurityCompact == []:
                        ERROR("No Valid Security Attribute found!!")
                        if OPT_ERROR_FILE:
                            appendVerifError(curFile, '', curOps, 'No Valid Security Attribute found', 1, '', 0, '',
                                             curFileDescName)
                    else:
                        # Compact format
                        pass
                else:
                    # Expanded format
                    pass
            else:
                iARRID = "%0.2X" % ARRRef[2] + "%0.2X" % ARRRef[3]
                iARRRec = ARRRef[4]

            # if OPT_USE_CLIENT:
            #     runlog_buffer.append(str(FileDescriptor))
            # else:
            #     print(FileDescriptor)
            if FileDescriptor[2] & 0xBF == 0x38:
                # MF, DF, or ADF
                if CheckList(file[fiFileType], sFileTypeMF) or \
                        CheckList(file[fiFileType], sFileTypeDF) or \
                        CheckList(file[fiFileType], sFileTypeADF):
                    pass
                else:
                    ERROR("Wrong File Type")
                    if OPT_ERROR_FILE:
                        appendVerifError(curFile, '', curOps, 'Wrong File Type', 1, '', 0, '', curFileDescName)
            else:
                # For EF
                if FileDescriptor[2] & 0x40:
                    # Shareable
                    # buat ngecek dari doc B seharusnya dia shareable atau engga #ini berarti di doc B YES
                    if file[fiShareable] == True:
                        pass
                    elif file[fiShareable] == None:
                        if OPT_SHAREABLE_WARNING:
                            WARNING("Undefined Shareable information")
                    else:
                        if OPT_SHAREABLE_WARNING:
                            ERROR("Wrong Shareable information")
                            if OPT_ERROR_FILE:
                                appendVerifError(curFile, '', curOps, 'Wrong Shareable information', 0, '', 0, '',
                                                 curFileDescName)
                else:
                    # get response dari kartu not shareable, trus dicek kalau dari doc gimana ?
                    # Not Shareable
                    if file[fiShareable] == True:
                        # however, if the requirement stated as shareable, but it is not shareable
                        # Should return error instead.
                        if OPT_SHAREABLE_WARNING:
                            ERROR("Wrong Shareable information")
                            if OPT_ERROR_FILE:
                                appendVerifError(curFile, '', curOps, 'Wrong Shareable information', 1, '', 0, '',
                                                 curFileDescName)
                    else:
                        pass

                # File Size
                if 0 != file[fiFileSize]:  # Only Check if the reference size is not zero
                    FileSize = SearchTLV(0x80, response[2:])
                    iFileSize = int("%0.2X" % FileSize[2] + "%0.2X" % FileSize[3], 16)
                    if iFileSize != int(file[fiFileSize]):
                        ERROR("Wrong File Size!")
                        if OPT_ERROR_FILE:
                            appendVerifError(curFile, '', curOps, 'Wrong File Size', 1, str(int(file[fiFileSize])), 0,
                                             str(iFileSize), curFileDescName)

                # File Structure
                if CheckList(file[fiFileType], sFileTypeEF):
                    pass
                else:
                    ERROR("Wrong File Type")
                    if OPT_ERROR_FILE:
                        appendVerifError(curFile, '', curOps, 'Wrong File Type', 1, '', 0, '', curFileDescName)
                # SFI
                if '' != file[fiFileSFI]:  # Only Check if the reference is not empty
                    # TODO:
                    #   - TS 102 specify that if the Tag 88 is not present,
                    #   the SFI is the 5 least significant bit of file ID.
                    #   - If TLV present but the length is zero, SFI is not supported
                    #   - If TLV is present, and length is not zero,
                    #   - the SFI is the 5 MOST SIGNIFICANT BIT of the value.
                    #   - Valid SFI value is from 1-31. Value 0 is not used.
                    if OPT_HEX_SFI:
                        RefSFI = int(file[fiFileSFI], 16)
                    else:
                        RefSFI = int(file[fiFileSFI])
                    if RefSFI != 0:
                        SFI = SearchTLV(0x88, response[2:])
                        if SFI == [] or SFI[1] == 0:
                            ERROR("SFI Not Present on Card")
                            if OPT_ERROR_FILE:
                                appendVerifError(curFile, '', curOps, 'SFI Not Present on Card', 1, str(file[fiFileSFI]), 0,
                                                '(not set)', curFileDescName)
                        else:
                            SfiFromFile = SFI[2] >> 3  # shift 3 bytes left
                            DEBUGPRINT("SFI: " + str(SFI))
                            #                         DEBUGPRINT("SfiFromFile: " + str(SfiFromFile))
                            DEBUGPRINT("SfiFromFile: " + hex(SfiFromFile)[2:].zfill(2).upper())
                            DEBUGPRINT("file[fiFileSFI]: " + str(file[fiFileSFI]))
                            DEBUGPRINT("RefSFI: " + str(RefSFI))
                            if RefSFI != SfiFromFile:
                                ERROR("Wrong SFI")
                                if OPT_ERROR_FILE:
                                    appendVerifError(curFile, '', curOps, 'Wrong SFI', 1, str(file[fiFileSFI]), 0,
                                                     hex(SfiFromFile)[2:].zfill(2).upper(), curFileDescName)

                if FileDescriptor[2] & 0x07 == 0x01:
                    # Transparent
                    if CheckList(file[fiFIleStruct], sFileStructTR):
                        # TODO: Check Content EF Transparent
                        pass
                    else:
                        ERROR(" File Structure Incorrect")
                        if OPT_ERROR_FILE:
                            appendVerifError(curFile, '', curOps, 'File Structure Incorrect', 1, '', 0, '',
                                             curFileDescName)
                elif FileDescriptor[2] & 0x07 == 0x02:
                    # Linear Fixed
                    if CheckList(file[fiFIleStruct], sFileStructLF):
                        if 0 != file[fiRecordSize]:  # Only Check if the reference size is not zero
                            if FileDescriptor[5] != file[fiRecordSize]:
                                ERROR("Wrong File Record Size")
                                if OPT_ERROR_FILE:
                                    appendVerifError(curFile, '', curOps, 'Wrong File Record Size', 1,
                                                     str(file[fiRecordSize]), 0, str(FileDescriptor[5]),
                                                     curFileDescName)
                        if 0 != file[fiNumberOfRecord]:  # Only Check if the reference size is not zero
                            if FileDescriptor[6] != file[fiNumberOfRecord]:
                                ERROR("Wrong Number of Record")
                                if OPT_ERROR_FILE:
                                    appendVerifError(curFile, '', curOps, 'Wrong Number of Record', 1,
                                                     str(file[fiNumberOfRecord]), 0, str(FileDescriptor[6]),
                                                     curFileDescName)
                                    # TODO: Check Content EF Linear Fixed
                    else:
                        ERROR(" File Structure Incorrect")
                        if OPT_ERROR_FILE:
                            appendVerifError(curFile, '', curOps, 'File Structure Incorrect', 1, '', 0, '',
                                             curFileDescName)
                elif FileDescriptor[2] & 0x07 == 0x06:
                    # Cyclic
                    if CheckList(file[fiFIleStruct], sFileStructCY):
                        if 0 != file[fiRecordSize]:  # Only Check if the reference size is not zero
                            if FileDescriptor[5] != file[fiRecordSize]:
                                ERROR("Wrong File Record Size")
                                if OPT_ERROR_FILE:
                                    appendVerifError(curFile, '', curOps, 'Wrong File Record Size', 1, '', 0, '',
                                                     curFileDescName)
                        if 0 != file[fiNumberOfRecord]:  # Only Check if the reference size is not zero
                            if FileDescriptor[6] != file[fiNumberOfRecord]:
                                ERROR("Wrong Number of Record")
                                if OPT_ERROR_FILE:
                                    appendVerifError(curFile, '', curOps, 'Wrong Number of Record', 1, '', 0, '',
                                                     curFileDescName)
                                    # TODO: Check Content EF Cyclic
                    else:
                        ERROR(" File Structure Incorrect")
                        if OPT_ERROR_FILE:
                            appendVerifError(curFile, '', curOps, 'File Structure Incorrect', 1, '', 0, '',
                                             curFileDescName)
                else:
                    ERROR(" Unidentified File Type")
                    if OPT_ERROR_FILE:
                        appendVerifError(curFile, '', curOps, 'Unidentified File Type', 1, '', 0, '', curFileDescName)

            # check 3g status ends here

            READRECORD3G = [0x00, 0xB2, 0x00, 0x04, 0x02]

            curOps = 'Test 3G Access Condition'
            runlog_buffer.append("Test access conditions for " + curFile)
            runlog_buffer.append("[DEBUG] ARR reference: " + toHexString(ARRRef))
            if ARRRef == []:
                # ERROR("No ARR reference specified in the file")
                if SecurityExpanded == []:
                    # Expanded format not supported
                    if SecurityCompact == []:
                        ERROR("No Valid Security Attribute found!!")
                        if OPT_ERROR_FILE:
                            appendVerifError(curFile, '', curOps, 'No Valid Security Attribute found', 1, '', 0, '',
                                             curFileDescName)
                    else:
                        # Compact format
                        pass
                else:
                    # Expanded format
                    CurACC = ARR2ACC(ParseARRV2(FilterHex(toHexString(SecurityExpanded))), file[fiFileType])

            elif ARRRef[1] < 3:  # Minimum length of ARR reference: 3
                ERROR("Bad ARR Reference TLV")
                if OPT_ERROR_FILE:
                    appendVerifError(curFile, '', curOps, 'Bad ARR Reference TLV', 1, '', 0, '', curFileDescName)
            else:
                toHexString(SELECT3G)
                ARRFound = False
                # Need to select the correct EF ARR:
                if ARRRef[2] == 0x2F:
                    runlog_buffer.append('ARR is under MF..')
                    # if ARR is "2Fxx", select MF first
                    Header = copy.deepcopy(SELECT3G)
                    # SendAPDU2(Header, "3F00", None, "61xx")
                    SendAPDU(Header, "3F00", None, "61xx", NOT_SAVED)
                    Header = copy.deepcopy(SELECT3G)
                    # SendAPDU2(Header, iARRID, None, "61xx")
                    SendAPDU(Header, iARRID, None, "61xx", NOT_SAVED)
                    if sw1 == 0x61:
                        ARRFound = True
                else:
                    # otherwise, loop from current DF up:
                    runlog_buffer.append('Searching for EF ARR..')
                    CurDFPathLen = len(curFile)
                    CurDFPathLen -= 4  # remove file ID
                    CurDFPath = curFile[:CurDFPathLen]
                    # ARRFound = False
                    while CurDFPathLen > 4 and not ARRFound:
                        Header = copy.deepcopy(SELECT3G)
                        Header[2] = 0x00  
                        Header[4] = 0x02
                        CurDFPathSeparated = []
                        idx1 = 0
                        idx2 = 4
                        for i in range(len(CurDFPath) / 4):
                            CurDFPathSeparated.append(CurDFPath[idx1:idx2])
                            idx1 += 4
                            idx2 += 4
                        for path_part in CurDFPathSeparated:
                            SendAPDU(Header, path_part, None, "61xx", NOT_SAVED)
                        # SendAPDU2(Header, CurDFPath, None, "61xx")
                        #SendAPDU(Header, CurDFPath, None, "61xx", NOT_SAVED)
                        if sw1 != 0x61:
                            # if not found, it means that the file structure of the card is different than expected
                            ERROR("Bad File Structure!!")
                            if OPT_ERROR_FILE:
                                appendVerifError(curFile, '', curOps, 'Bad File Structure', 1, '', 0, '',
                                                 curFileDescName)
                        Header = copy.deepcopy(SELECT3G)
                        SendAPDU(Header, iARRID, None, None,
                                 NOT_SAVED)  # Do not check the SW, as the ARR may not be in this level.
                        if sw1 == 0x61:
                            runlog_buffer.append('EF ARR found..')
                            ARRFound = True
                            break;
                        CurDFPathLen -= 4  # Go up 1 level
                        runlog_buffer.append('EF ARR not found; go up one level..')
                        CurDFPath = curFile[:CurDFPathLen]

                # if sw1 != 0x61:
                if not ARRFound:
                    ERROR("ARR File Not found!!")
                    if OPT_ERROR_FILE:
                        appendVerifError(curFile, '', curOps, 'ARR File Not found', 1, '', 0, '', curFileDescName)
                else:
                    Header = copy.deepcopy(GETRESP3G)
                    Header[4] = sw2
                    # SendAPDU2(Header,None, None, None)
                    SendAPDU(Header, None, None, None, NOT_SAVED)

                    FileDescriptor = SearchTLV(0x82, response[2:])
                    CurACC = [[], [], [], [], [], [], [], [], [], [], [], [], []]

                    Header = copy.deepcopy(READRECORD3G)
                    Header[2] = iARRRec
                    Header[3] = 0x04
                    Header[4] = FileDescriptor[5]
                    # SendAPDU2(Header, None, None, "90xx")
                    SendAPDU(Header, None, None, "90xx", NOT_SAVED)

                    CurACC = ARR2ACC(ParseARRV2(FilterHex(toHexString(response))), file[fiFileType])
            if file[fiRead3G_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siRead_ACC]) == set(file[fiRead3G_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siRead_ACC][1:]:
                        tempFound = False
                        for b in file[fiRead3G_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siRead_ACC]) == set(file[fiRead3G_ACC]):
                        found = True
                if not found:
                    ERROR("Read 3G Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        if not len(set(file[fiRead3G_ACC])) > 1:
                            exp_acc = set(file[fiRead3G_ACC]).pop()
                            exp_acc_str = getACC(exp_acc)
                        else:
                            exp_read3g_set = set(file[fiRead3G_ACC])
                            exp_read3g_list = []
                            for e in exp_read3g_set:
                                exp_read3g_list.append(getACC(e))
                            exp_acc_str = ' :: '.join(exp_read3g_list)
                        if set(CurACC[siRead_ACC]):
                            if not len(set(CurACC[siRead_ACC])) > 1:
                                exp_out = set(CurACC[siRead_ACC]).pop()
                                exp_out_str = getACC(exp_out)
                            else:
                                out_read3g_set = set(CurACC[siRead_ACC])
                                out_read3g_list = []
                                for o in out_read3g_set:
                                    out_read3g_list.append(getACC(o))
                                exp_out_str = ' :: '.join(out_read3g_list)
                        else:
                            exp_out_str = '(not defined in card)'

                        appendVerifError(curFile, '', curOps, 'Read 3G Access condition Not Correct', 1, exp_acc_str, 0,
                                         exp_out_str, curFileDescName)

            if file[fiUpdate3G_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siUpdate_ACC]) == set(file[fiUpdate3G_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siUpdate_ACC][1:]:
                        tempFound = False
                        for b in file[fiUpdate3G_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siUpdate_ACC]) == set(file[fiUpdate3G_ACC]):
                        found = True
                if not found:
                    ERROR("Update 3G Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        if not len(set(file[fiUpdate3G_ACC])) > 1:
                            exp_acc = set(file[fiUpdate3G_ACC]).pop()
                            exp_acc_str = getACC(exp_acc)
                        else:
                            exp_update3g_set = set(file[fiUpdate3G_ACC])
                            exp_update3g_list = []
                            for e in exp_update3g_set:
                                exp_update3g_list.append(getACC(e))
                            exp_acc_str = ' :: '.join(exp_update3g_list)
                        if set(CurACC[siUpdate_ACC]):
                            if not len(set(CurACC[siUpdate_ACC])) > 1:
                                exp_out = set(CurACC[siUpdate_ACC]).pop()
                                exp_out_str = getACC(exp_out)
                            else:
                                out_update3g_set = set(CurACC[siUpdate_ACC])
                                out_update3g_list = []
                                for o in out_update3g_set:
                                    out_update3g_list.append(getACC(o))
                                exp_out_str = ' :: '.join(out_update3g_list)
                        else:
                            exp_out_str = '(not defined in card)'

                        appendVerifError(curFile, '', curOps, 'Update 3G Access condition Not Correct', 1, exp_acc_str,
                                         0, exp_out_str, curFileDescName)

            if file[fiWrite3G_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siWrite3G_ACC]) == set(file[fiWrite3G_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siWrite3G_ACC][1:]:
                        tempFound = False
                        for b in file[fiWrite3G_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siWrite3G_ACC]) == set(file[fiWrite3G_ACC]):
                        found = True
                if not found:
                    ERROR("Write 3G Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        if not len(set(file[fiWrite3G_ACC])) > 1:
                            exp_acc = set(file[fiWrite3G_ACC]).pop()
                            exp_acc_str = getACC(exp_acc)
                        else:
                            exp_write3g_set = set(file[fiWrite3G_ACC])
                            exp_write3g_list = []
                            for e in exp_write3g_set:
                                exp_write3g_list.append(getACC(e))
                            exp_acc_str = ' :: '.join(exp_write3g_list)
                        if set(CurACC[siWrite3G_ACC]):
                            if not len(set(CurACC[siWrite3G_ACC])) > 1:
                                exp_out = set(CurACC[siWrite3G_ACC]).pop()
                                exp_out_str = getACC(exp_out)
                            else:
                                out_write3g_set = set(CurACC[siWrite3G_ACC])
                                out_write3g_list = []
                                for o in out_write3g_set:
                                    out_write3g_list.append(getACC(o))
                                exp_out_str = ' :: '.join(out_write3g_list)
                        else:
                            exp_out_str = '(not defined in card)'

                        appendVerifError(curFile, '', curOps, 'Write 3G Access condition Not Correct', 1, exp_acc_str,
                                         0, exp_out_str, curFileDescName)

            if file[fiIncrease3G_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siIncrease_ACC]) == set(file[fiIncrease3G_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siIncrease_ACC][1:]:
                        tempFound = False
                        for b in file[fiIncrease3G_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siIncrease_ACC]) == set(file[fiIncrease3G_ACC]):
                        found = True
                if not found:
                    ERROR("Increase 3G Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        if not len(set(file[fiIncrease3G_ACC])) > 1:
                            exp_acc = set(file[fiIncrease3G_ACC]).pop()
                            exp_acc_str = getACC(exp_acc)
                        else:
                            exp_increase3g_set = set(file[fiIncrease3G_ACC])
                            exp_increase3g_list = []
                            for e in exp_increase3g_set:
                                exp_increase3g_list.append(getACC(e))
                            exp_acc_str = ' :: '.join(exp_increase3g_list)
                        if set(CurACC[siIncrease_ACC]):
                            if not len(set(CurACC[siIncrease_ACC])) > 1:
                                exp_out = set(CurACC[siIncrease_ACC]).pop()
                                exp_out_str = getACC(exp_out)
                            else:
                                out_increase_set = set(CurACC[siIncrease_ACC])
                                out_increase_list = []
                                for o in out_increase_set:
                                    out_increase_list.append(getACC(o))
                                exp_out_str = ' :: '.join(out_increase_list)
                        else:
                            exp_out_str = '(not defined in card)'

                        appendVerifError(curFile, '', curOps, 'Increase 3G Access condition Not Correct', 1,
                                         exp_acc_str, 0, exp_out_str, curFileDescName)

            if file[fiActivate_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siActivate_ACC]) == set(file[fiActivate_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siActivate_ACC][1:]:
                        tempFound = False
                        for b in file[fiActivate_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siActivate_ACC]) == set(file[fiActivate_ACC]):
                        found = True
                if not found:
                    ERROR("Activate 3G Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        if not len(set(file[fiActivate_ACC])) > 1:
                            exp_acc = set(file[fiActivate_ACC]).pop()
                            exp_acc_str = getACC(exp_acc)
                        else:
                            exp_activate_set = set(file[fiActivate_ACC])
                            exp_activate_list = []
                            for e in exp_activate_set:
                                exp_activate_list.append(getACC(e))
                            exp_acc_str = ' :: '.join(exp_activate_list)
                        if set(CurACC[siActivate_ACC]):
                            if not len(set(CurACC[siActivate_ACC])) > 1:
                                exp_out = set(CurACC[siActivate_ACC]).pop()
                                exp_out_str = getACC(exp_out)
                            else:
                                out_activate_set = set(CurACC[siActivate_ACC])
                                out_activate_list = []
                                for o in out_activate_set:
                                    out_activate_list.append(getACC(o))
                                exp_out_str = ' :: '.join(out_activate_list)
                        else:
                            exp_out_str = '(not defined in card)'

                        appendVerifError(curFile, '', curOps, 'Activate 3G Access condition Not Correct', 1,
                                         exp_acc_str, 0, exp_out_str, curFileDescName)

            if file[fiDeactivate_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siDeactivate_ACC]) == set(file[fiDeactivate_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siDeactivate_ACC][1:]:
                        tempFound = False
                        for b in file[fiDeactivate_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siDeactivate_ACC]) == set(file[fiDeactivate_ACC]):
                        found = True
                if not found:
                    ERROR("Deactivate 3G Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        if not len(set(file[fiDeactivate_ACC])) > 1:
                            exp_acc = set(file[fiDeactivate_ACC]).pop()
                            exp_acc_str = getACC(exp_acc)
                        else:
                            exp_deactivate_set = set(file[fiDeactivate_ACC])
                            exp_deactivate_list = []
                            for e in exp_deactivate_set:
                                exp_deactivate_list.append(getACC(e))
                            exp_acc_str = ' :: '.join(exp_deactivate_list)
                        if set(CurACC[siDeactivate_ACC]):
                            if not len(set(CurACC[siDeactivate_ACC])) > 1:
                                exp_out = set(CurACC[siDeactivate_ACC]).pop()
                                exp_out_str = getACC(exp_out)
                            else:
                                out_deactivate_set = set(CurACC[siDeactivate_ACC])
                                out_deactivate_list = []
                                for o in out_deactivate_set:
                                    out_deactivate_list.append(getACC(o))
                                exp_out_str = ' :: '.join(out_deactivate_list)
                        else:
                            exp_out_str = '(not defined in card)'

                        appendVerifError(curFile, '', curOps, 'Deactivate 3G Access condition Not Correct', 1,
                                         exp_acc_str, 0, exp_out_str, curFileDescName)

            if file[fiTerminate_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siTerminate_ACC]) == set(file[fiTerminate_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siTerminate_ACC][1:]:
                        tempFound = False
                        for b in file[fiTerminate_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siTerminate_ACC]) == set(file[fiTerminate_ACC]):
                        found = True
                if not found:
                    ERROR("Terminate 3G Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        if not len(set(file[fiTerminate_ACC])) > 1:
                            exp_acc = set(file[fiTerminate_ACC]).pop()
                            exp_acc_str = getACC(exp_acc)
                        else:
                            exp_terminate_set = set(file[fiTerminate_ACC])
                            exp_terminate_list = []
                            for e in exp_terminate_set:
                                exp_terminate_list.append(getACC(e))
                            exp_acc_str = ' :: '.join(exp_terminate_list)
                        if set(CurACC[siTerminate_ACC]):
                            if not len(set(CurACC[siTerminate_ACC])) > 1:
                                exp_out = set(CurACC[siTerminate_ACC]).pop()
                                exp_out_str = getACC(exp_out)
                            else:
                                out_terminate_set = set(CurACC[siTerminate_ACC])
                                out_terminate_list = []
                                for o in out_terminate_set:
                                    out_terminate_list.append(getACC(o))
                                exp_out_str = ' :: '.join(out_terminate_list)
                        else:
                            exp_out_str = '(not defined in card)'

                        appendVerifError(curFile, '', curOps, 'Terminate 3G Access condition Not Correct', 1,
                                         exp_acc_str, 0, exp_out_str, curFileDescName)

            if file[fiResize_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siResize_ACC]) == set(file[fiResize_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siResize_ACC][1:]:
                        tempFound = False
                        for b in file[fiResize_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siResize_ACC]) == set(file[fiResize_ACC]):
                        found = True
                if not found:
                    ERROR("Resize 3G Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        if not len(set(file[fiResize_ACC])) > 1:
                            exp_acc = set(file[fiResize_ACC]).pop()
                            exp_acc_str = getACC(exp_acc)
                        else:
                            exp_resize_set = set(file[fiResize_ACC])
                            exp_resize_list = []
                            for e in exp_resize_set:
                                exp_resize_list.append(getACC(e))
                            exp_acc_str = ' :: '.join(exp_resize_list)
                        if set(CurACC[siResize_ACC]):
                            if not len(set(CurACC[siResize_ACC])) > 1:
                                exp_out = set(CurACC[siResize_ACC]).pop()
                                exp_out_str = getACC(exp_out)
                            else:
                                out_resize_set = set(CurACC[siResize_ACC])
                                out_resize_list = []
                                for o in out_resize_set:
                                    out_resize_list.append(getACC(o))
                                exp_out_str = ' :: '.join(out_resize_list)
                        else:
                            exp_out_str = '(not defined in card)'
                        appendVerifError(curFile, '', curOps, 'Resize 3G Access condition Not Correct', 1, exp_acc_str,
                                         0, exp_out_str, curFileDescName)

            # Update for checking Custom Access Condition

            if file[fiCustom_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set([CurACC[siCustom_ACC][0][4]]) == set(file[fiCustom_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in [CurACC[siCustom_ACC][0][4]]:
                        tempFound = False
                        for b in file[fiCustom_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set([CurACC[siCustom_ACC][0][4]]) == set(file[fiCustom_ACC]):
                        found = True
                if not found:
                    ERROR("Custom Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        exp_acc = set(file[fiCustom_ACC]).pop()
                        exp_acc_str = getACC(exp_acc)
                        if set(CurACC[siCustom_ACC]):
                            exp_out = set(CurACC[siCustom_ACC]).pop()
                            exp_out_str = getACC(exp_out)
                        else:
                            exp_out_str = ''

                        appendVerifError(curFile, '', curOps, 'Custom Access condition Not Correct', 1, exp_acc_str, 0,
                                         exp_out_str, curFileDescName)

                        # End of update custom access condition
            if file[fiDeleteChild_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siDeleteChild_ACC]) == set(file[fiDeleteChild_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siDeleteChild_ACC][1:]:
                        tempFound = False
                        for b in file[fiDeleteChild_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siDeleteChild_ACC]) == set(file[fiDeleteChild_ACC]):
                        found = True
                if not found:
                    ERROR("Delete Child Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        if not len(set(file[fiDeleteChild_ACC])) > 1:
                            exp_acc = set(file[fiDeleteChild_ACC]).pop()
                            exp_acc_str = getACC(exp_acc)
                        else:
                            exp_deletechild_set = set(file[fiDeleteChild_ACC])
                            exp_deletechild_list = []
                            for e in exp_deletechild_set:
                                exp_deletechild_list.append(getACC(e))
                            exp_acc_str = ' :: '.join(exp_deletechild_list)
                        if set(CurACC[siDeleteChild_ACC]):
                            if not len(set(CurACC[siDeleteChild_ACC])) > 1:
                                exp_out = set(CurACC[siDeleteChild_ACC]).pop()
                                exp_out_str = getACC(exp_out)
                            else:
                                out_deletechild_set = set(CurACC[siDeleteChild_ACC])
                                out_deletechild_list = []
                                for o in out_deletechild_set:
                                    out_deletechild_list.append(getACC(o))
                                exp_out_str = ' :: '.join(out_deletechild_list)
                        else:
                            exp_out_str = '(not defined in card)'

                        appendVerifError(curFile, '', curOps, 'Delete Child Access condition Not Correct', 1,
                                         exp_acc_str, 0, exp_out_str, curFileDescName)

            if file[fiDeleteSelf_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siDeleteSelf_ACC]) == set(file[fiDeleteSelf_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siDeleteSelf_ACC][1:]:
                        tempFound = False
                        for b in file[fiDeleteSelf_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siDeleteSelf_ACC]) == set(file[fiDeleteSelf_ACC]):
                        found = True
                if not found:
                    ERROR("Delete Self Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        if not len(set(file[fiDeleteSelf_ACC])) > 1:
                            exp_acc = set(file[fiDeleteSelf_ACC]).pop()
                            exp_acc_str = getACC(exp_acc)
                        else:
                            exp_deleteself_set = set(file[fiDeleteSelf_ACC])
                            exp_deleteself_list = []
                            for e in exp_deleteself_set:
                                exp_deleteself_list.append(getACC(e))
                            exp_acc_str = ' :: '.join(exp_deleteself_list)
                        if set(CurACC[siDeleteSelf_ACC]):
                            if not len(set(CurACC[siDeleteSelf_ACC])) > 1:
                                exp_out = set(CurACC[siDeleteSelf_ACC]).pop()
                                exp_out_str = getACC(exp_out)
                            else:
                                out_deleteself_set = set(CurACC[siDeleteSelf_ACC])
                                out_deleteself_list = []
                                for o in out_deleteself_set:
                                    out_deleteself_list.append(getACC(o))
                                exp_out_str = ' :: '.join(out_deleteself_list)
                        else:
                            exp_out_str = '(not defined in card)'

                        appendVerifError(curFile, '', curOps, 'Delete Self Access condition Not Correct', 1,
                                         exp_acc_str, 0, exp_out_str, curFileDescName)

            if file[fiCreateEF_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siCreateEF_ACC]) == set(file[fiCreateEF_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siCreateEF_ACC][1:]:
                        tempFound = False
                        for b in file[fiCreateEF_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siCreateEF_ACC]) == set(file[fiCreateEF_ACC]):
                        found = True
                if not found:
                    ERROR("Create EF Access condition Not Correct")
                    if OPT_ERROR_FILE:
                        if not len(set(file[fiCreateEF_ACC])) > 1:
                            exp_acc = set(file[fiCreateEF_ACC]).pop()
                            exp_acc_str = getACC(exp_acc)
                        else:
                            exp_createef_set = set(file[fiCreateEF_ACC])
                            exp_createef_list = []
                            for e in exp_createef_set:
                                exp_createef_list.append(getACC(e))
                            exp_acc_str = ' :: '.join(exp_createef_list)
                        if set(CurACC[siCreateEF_ACC]):
                            if not len(set(CurACC[siCreateEF_ACC])) > 1:
                                exp_out = set(CurACC[siCreateEF_ACC]).pop()
                                exp_out_str = getACC(exp_out)
                            else:
                                out_createef_set = set(CurACC[siCreateEF_ACC])
                                out_createef_list = []
                                for o in out_createef_set:
                                    out_createef_list.append(getACC(o))
                                exp_out_str = ' :: '.join(out_createef_list)
                        else:
                            exp_out_str = '(not defined in card)'

                        appendVerifError(curFile, '', curOps, 'Create EF Access condition Not Correct', 1, exp_acc_str,
                                         0, exp_out_str, curFileDescName)

            if file[fiCreateDF_ACC] != []:
                if OPT_3G_ACC_ALL_MATCH == 0:
                    found = False
                    if set(CurACC[siCreateDF_ACC]) == set(file[fiCreateDF_ACC]):
                        found = True
                elif OPT_3G_ACC_ALL_MATCH == 1:
                    found = False
                    for a in CurACC[siCreateDF_ACC][1:]:
                        tempFound = False
                        for b in file[fiCreateDF_ACC]:
                            if a == b:
                                tempFound = True
                        if tempFound == True:
                            found = True
                else:
                    found = False
                    if set(CurACC[siCreateDF_ACC]) == set(file[fiCreateDF_ACC]):
                        found = True
                if not found:
                    ERROR("Create DF Access condition Not Correct")

            # access conditions testing ends here

            
            
        ############# Add Check Content 3G ####################
        CmdSelect3G_not_recorded(file[fiFilePathID], None, None)

        if OPT_CHECK_CONTENT_3G == 1:
            # -------------------------------------------------------------------------------
            # Check File Content 3G
            # -------------------------------------------------------------------------------
            TempValue = []
            VarName = None
            # if True:
            # if file[fiRead_ACC] != [] and file[fiRead_ACC][0] != iAccNEV:
            if file[fiRead_ACC] == [] or file[fiRead_ACC][0] != iAccNEV:

                if file[fiContent].startswith('%'):
                    tempContent = file[fiContent]  # Handle variable name
                else:
                    tempContent = FilterString(file[fiContent])  # Filter content

                # if file[fiContent] != '':
                if tempContent != '':
                    if OPT_USE_CLIENT:
                        runlog_buffer.append("Test File Content for " + str(curFile))
                    else:
                        print "Test File Content for " + curFile
                        print "-----------------------------------------"
                    curOps = 'Test File Content'
                    if CheckList(file[fiFileType], sFileTypeMF) or \
                            CheckList(file[fiFileType], sFileTypeDF) or \
                            CheckList(file[fiFileType], sFileTypeADF):
                        pass
                    else:
                        # Only check content if the content is not empty and it is an EF.
                        # Rule #1: length of the content reference is less than the actual length in the EF,
                        #   The remaining value are not checked. (this already handled by SendAPDU function)
                        # Rule #2: If length of the content reference is longer than the actual length in EF,
                        #   the content reference shall be truncated up to the length in the EF.
                        #   Warning shall be issued. (handle in SendAPDU)

                        # ExpectedResponse = file[fiContent]
                        # ExpectedLength = len(file[fiContent])/2
                        VarValue = None
                        tempPercentOffset = tempContent.find('%')
                        if tempPercentOffset != -1:
                            tempSpaceOffset = tempContent.find(' ')
                            if tempSpaceOffset != -1:
                                # a variable name has been found
                                VarName = tempContent[tempPercentOffset:tempSpaceOffset]
                                DEBUGPRINT("VarName: " + str(VarName))
                                if VarName[1:] in VarList:
                                    VarValue = VarList.get(VarName[1:])
                                elif 'GSM_' + VarName[1:] in VarList:  # search GSM file in varList
                                    VarValue = VarList.get('GSM_' + VarName[1:])
                                elif 'USIM_' + VarName[1:] in VarList:  # search USIM file in varList
                                    VarValue = VarList.get('USIM_' + VarName[1:])
                                else:
                                    VarValue = ''
                                if OPT_USE_CLIENT:
                                    runlog_buffer.append('VarValue: ' + str(VarValue))
                                else:
                                    print('VarValue: ' + str(VarValue))

                            else:
                                # Ending space not found, assuming until end of the text
                                VarName = tempContent[tempPercentOffset:]
                                DEBUGPRINT("VarName: " + str(VarName))
                                if VarName[1:] in VarList:
                                    VarValue = VarList.get(VarName[1:])
                                elif 'GSM_' + VarName[1:] in VarList:
                                    VarValue = VarList.get('GSM_' + VarName[1:])
                                elif 'USIM_' + VarName[1:] in VarList:
                                    VarValue = VarList.get('USIM_' + VarName[1:])
                                else:
                                    VarValue = None

                                if VarName == '': VarName = None  # Handle if text empty
                                # VarValue = GetVarValue(VarName[1:])  # ignore the percent sign
                                if OPT_USE_CLIENT:
                                    runlog_buffer.append('VarValue: ' + str(VarValue))
                                else:
                                    print('VarValue: ' + str(VarValue))

                        # Rule #3: if the content start with %, it means variable, and followed by variable name.
                        #   The variable name are started with'%' (percent) sign followed by variable name and a space
                        #   In example 1234 %VAR1 5678. The content of variable is mentioned in VarList()
                        #   if the variable is at the end of the string, space is not required.
                        #   For example: "123456 %VAR1"
                        #   When variable is used, usually an exact value is expected. So, OPT_EXPECTED_PADDING
                        #       is not supported when a variable exist in the expected data.

                        if CheckList(file[fiFIleStruct], sFileStructLF) or \
                                CheckList(file[fiFIleStruct], sFileStructCY):
                            # Rule #4:
                            # for Linear Fixed/Cyclic, First check the files with the record number, and keep the list.
                            if VarValue == None:
                                # Padding can only be done if there is no variable at the moment
                                ExpectedResponse = tempContent
                                ExpectedLength = len(tempContent) / 2
                                if OPT_EXPECTED_PADDING:
                                    LastByte = ExpectedResponse[(ExpectedLength * 2) - 2:]
                                    while ExpectedLength < int(file[fiRecordSize]):
                                        ExpectedResponse += LastByte
                                        ExpectedLength += 1

                                if VarName:  # handle case where CSV variable name is not found in AdvSave
                                    # Need to print the variable name to aid the modification of PCOM script.
                                    if OptWrite2File:
                                        OutputFile.writelines(";; Variable Used. Original Value: ")
                                        OutputFile.writelines(tempContent)
                                        OutputFile.writelines('\n')

                            else:
                                # Replace with Value, no padding
                                ExpectedResponse = tempContent[:tempPercentOffset]
                                ExpectedResponse += VarValue
                                if tempSpaceOffset != -1:
                                    ExpectedResponse += tempContent[tempSpaceOffset + 1:]
                                ExpectedResponse = FilterString(ExpectedResponse)
                                ExpectedLength = len(ExpectedResponse) / 2

                                # Need to print the variable name to aid the modification of PCOM script.
                                if OptWrite2File:
                                    OutputFile.writelines(";; Variable Used. Original Value: ")
                                    OutputFile.writelines(tempContent)
                                    OutputFile.writelines('\n')

                            if file[fiRecordNumber] != '':
                                RecordList.append(int(file[fiRecordNumber]))  # Content Record number always decimal
                                curRec = int(file[fiRecordNumber])
                                CmdReadRecord3G(int(file[fiRecordNumber]), RECMODE2G_ABS, int(file[fiRecordSize]),
                                                ExpectedResponse, "9000")
                                TempValue = copy.deepcopy(response)
                            # Rule #5: If a content found that is without a record number,
                            #   all the record within the same file shall be checked (except those files that are already checked).
                            #   For simplicity, such content (without record number) shall be the last content in the list for the same EF.
                            #   All record content of an EF shall be in defined consecutively in the list.
                            else:
                                index = 1
                                # if OPT_USE_CLIENT:
                                #     runlog_buffer.append('NumOfRec' + str(file[fiNumberOfRecord]))
                                #     runlog_buffer.append('RecordList ' + str(RecordList))
                                # else:
                                #     print('NumOfRec' + str(file[fiNumberOfRecord]))
                                #     print('RecordList ' + str(RecordList))
                                while index <= file[fiNumberOfRecord]:
                                    Found = 0
                                    for a in RecordList:
                                        if a == index:
                                            Found = 1
                                            break
                                    # if OPT_USE_CLIENT:
                                    #     runlog_buffer.append('Found ' + str(Found))
                                    # else:
                                    #     print('Found ' + str(Found))
                                    if Found == 0:
                                        # Not tested yet, read the content
                                        curRec = index
                                        CmdReadRecord3G(index, RECMODE2G_ABS, int(file[fiRecordSize]),
                                                        ExpectedResponse,
                                                        "9000")
                                        TempValue = copy.deepcopy(response)
                                    index += 1
                        else:
                            # For Transparent, just check the file content
                            if VarValue == None:
                                ExpectedResponse = tempContent
                                ExpectedLength = len(tempContent) / 2
                                # Padding can only be done if there is no variable
                                if OPT_EXPECTED_PADDING:
                                    LastByte = ExpectedResponse[(ExpectedLength * 2) - 2:]
                                    while ExpectedLength < int(file[fiFileSize]):
                                        ExpectedResponse += LastByte
                                        ExpectedLength += 1

                                if VarName:  # handle case where CSV variable name is not found in AdvSave
                                    # Need to print the variable name to aid the modification of PCOM script.
                                    if OptWrite2File:
                                        OutputFile.writelines(";; Variable Used. Original Value: ")
                                        OutputFile.writelines(tempContent)
                                        OutputFile.writelines('\n')

                            else:
                                # Replace with Value, no padding
                                ExpectedResponse = tempContent[:tempPercentOffset]
                                ExpectedResponse += VarValue
                                if tempSpaceOffset != -1:
                                    ExpectedResponse += tempContent[tempSpaceOffset + 1:]
                                ExpectedResponse = FilterString(ExpectedResponse)
                                ExpectedLength = len(ExpectedResponse) / 2

                                # Need to print the variable name to aid the modification of PCOM script.
                                if OptWrite2File:
                                    OutputFile.writelines(";; Variable Used. Original Value: ")
                                    OutputFile.writelines(tempContent)
                                    OutputFile.writelines('\n')
                            # Handle lenght more than 1 APDU
                            index = 0
                            while index < int(file[fiFileSize]):
                                if index >= ExpectedLength:
                                    WARNING("Expected Length is longer than file size")
                                    break
                                if (index + MAX_RESPONSE_LEN) > int(file[fiFileSize]):
                                    TempLen = int(file[fiFileSize]) - index
                                else:
                                    TempLen = MAX_RESPONSE_LEN

                                ##CmdReadBinary2G(index, TempLen, ExpectedResponse[(index*2):], "9000")

                                # Fix the expected data of Binary file >128 issue
                                # Method 1
                                # Buffer = ''
                                # i = 0
                                # while i<TempLen and ((index+i)*2)< len(ExpectedResponse):
                                #    #Buffer += ExpectedResponse[(index+i)*2] + ExpectedResponse[((index+i)*2)+1]
                                #    Buffer += ExpectedResponse[(index+i)*2:(index+i+1)*2]
                                #    i += 1
                                # CmdReadBinary2G(index, TempLen, Buffer, "9000")

                                # Method 2
                                curRec = 0
                                CmdReadBinary3G(index, TempLen,
                                                ExpectedResponse[(index * 2):((index + TempLen) * 2)],
                                                "9000")

                                TempValue += copy.deepcopy(response)
                                index += TempLen
                else:
                    # just read the content without checking the value
                    if curFile != prevFile:  # only check the first one for linear fixed
                        if OPT_USE_CLIENT:
                            runlog_buffer.append("Read File Content for " + str(curFile))
                        else:
                            print "Read File Content for " + curFile
                            print "-----------------------------------------"
                        if CheckList(file[fiFileType], sFileTypeMF) or \
                                CheckList(file[fiFileType], sFileTypeDF) or \
                                CheckList(file[fiFileType], sFileTypeADF):
                            pass
                        else:
                            if CheckList(file[fiFIleStruct], sFileStructLF) or \
                                    CheckList(file[fiFIleStruct], sFileStructCY):
                                if file[fiRecordSize] != 0:
                                    if file[fiRecordNumber] != '':
                                        # CmdReadRecord3G(int(file[fiRecordNumber]), RECMODE2G_ABS,
                                        #                 int(file[fiRecordSize]), None, "9000", NOT_SAVED)
                                        CmdReadRecord3G(int(file[fiRecordNumber]), RECMODE2G_ABS,
                                                        int(file[fiRecordSize]), None, "9000")
                                        TempValue = copy.deepcopy(response)
                                    else:
                                        # Not defined? Only Read Record #1
                                        # CmdReadRecord3G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000",
                                        #                 NOT_SAVED)
                                        CmdReadRecord3G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000")
                                        TempValue = copy.deepcopy(response)
                                else:
                                    # zero record size
                                    pass
                            else:
                                # For Transparent, just check the file content
                                # Handle lenght more than 1 APDU
                                index = 0
                                while index < int(file[fiFileSize]):  # Todo: should check with real file size
                                    if (index + MAX_RESPONSE_LEN) > int(file[fiFileSize]):
                                        TempLen = int(file[fiFileSize]) - index
                                    else:
                                        TempLen = MAX_RESPONSE_LEN
                                    # CmdReadBinary3G(index, TempLen, None, "9000", NOT_SAVED)
                                    CmdReadBinary3G(index, TempLen, None, "9000")
                                    TempValue += copy.deepcopy(response)
                                    index += TempLen
                    else:
                        pass
            TempStatus3G = copy.deepcopy(response)  # to compare with linked file if needed
        
            # check content 3g ends here

        # Update Add Check Link 3G

        # -------------------------------------------------------------------------------
        # Check linked file in 3G mode
        # -------------------------------------------------------------------------------
        if OPT_CHECK_LINK3G == 1:
            TempValue2 = []
            if file[fiLinkTo] != '' and \
                    (file[fiRead_ACC] == [] or file[fiRead_ACC][0] != iAccNEV) and \
                            curFile != prevFile:  # only check the first one for linear fixed
                if OPT_USE_CLIENT:
                    runlog_buffer.append("Check Linked File to : " + str(file[fiLinkTo]))
                else:
                    print "Check Linked File to : " + file[fiLinkTo]
                    print "-----------------------------------------"
                curOps = 'Check Linked File'
                curLinkedFile = file[fiLinkTo]
                for file2 in FileList:
                    # DEBUGPRINT("file2: " + str(file2))
                    if file[fiLinkTo] == file2[fiFilePathID]:
                        linkedfile = file2
                        CmdSelect3G_not_recorded(file2[fiFilePathID], None, None)
                        # CmdSelect3G(file2[fiFilePathID], None, None,NOT_SAVED)
                        if TempStatus3G != response:
                            # Note: The file ID (or some other header) of the linked file could be different.
                            #   Set as warning for now
                            #   TODO: Check the difference: File Size, record size, number of record should be the same
                            #           Access condition and File ID can be different does not need to be checked.
                            WARNING(" Different Linked file Status !!")
                        # break
                        if CheckList(file2[fiFIleStruct], sFileStructLF) or \
                                CheckList(file2[fiFIleStruct], sFileStructCY):
                            # need to handle the empty record number
                            if file[fiRecordSize] != 0:
                                if file[fiRecordNumber] != '':
                                    # Check the original file for record number, only check if the record number exist
                                    CmdReadRecord3G(int(file[fiRecordNumber]), RECMODE2G_ABS,
                                                    int(file[fiRecordSize]),
                                                    None, "9000", NOT_SAVED)
                                    TempValue2 = copy.deepcopy(response)
                                else:
                                    CmdReadRecord3G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000",
                                                    NOT_SAVED)
                                    TempValue2 = copy.deepcopy(response)
                                    ##stop checking if no record number
                                    # break
                        else:
                            index = 0
                            while index < int(file2[fiFileSize]):
                                # if index >= ExpectedLength:
                                #    break
                                if (index + MAX_RESPONSE_LEN) > int(file2[fiFileSize]):
                                    TempLen = int(file2[fiFileSize]) - index
                                else:
                                    TempLen = MAX_RESPONSE_LEN
                                # CmdReadBinary3G(index, TempLen, None, "9000")
                                CmdReadBinary3G(index, TempLen, None, "9000", NOT_SAVED)
                                TempValue2 += copy.deepcopy(response)
                                index += TempLen
                        if TempValue2 != TempValue:
                            # For sure linked file must have same values. Error if not the same.
                            ERROR(" Different Linked file Value !!")
                            if OPT_ERROR_FILE:
					            appendVerifError(curFile, curLinkedFile, curOps, 'Different Linked file Value', 0, '', 0,
									            '', curFileDescName)
                        
                        if OPT_CHECK_LINK_UPDATE:
                            # The other file linked to shall be updated, and the current file to be selected and read again.
                            #   The content should be updated in the current file.

                            if OPT_USE_CLIENT:
                                runlog_buffer.append("Test UPDATE Linked File: " + str(file[fiLinkTo]))
                            else:
                                print "Test UPDATE Linked File: " + file[fiLinkTo]
                                print "-----------------------------------------"
                            curOps = 'Test UPDATE Linked File'
                            # print "TempValue :" + toHexString(TempValue)
                            # print "TempValue2 :" + toHexString(TempValue2)

                            # invert all data
                            # for a in TempValue2:   # Not working, value cannot be changed in for loop
                            #    a = a^0xFF
                            # for i, s in enumerate(TempValue2): TempValue2[i] = TempValue2[i]^0xFF  # This might also work
                            TempValue2[:] = [a ^ 0xFF for a in TempValue2]
                            # print toHexString(TempValue2)
                            TempValue = []  # Reset TempValue
                            if TempValue2 == []:
                                WARNING(" Linked file cannot be read/updated !!")
                                if OPT_ERROR_FILE:
						            appendVerifError(curFile, curLinkedFile, curOps, 'Linked file cannot be read/updated',
										            0, '', 0, '', curFileDescName)
                            else:
                                if CheckList(file2[fiFIleStruct], sFileStructLF):
                                    if file[fiRecordSize] != 0:
                                        if file[fiRecordNumber] != '':
                                            CmdUpdateRecord3G(int(file[fiRecordNumber]), RECMODE2G_ABS,
                                                                int(file[fiRecordSize]), TempValue2, "9000", NOT_SAVED)
                                            # CmdUpdateRecord3G(int(file[fiRecordNumber]), RECMODE2G_ABS, int(file[fiRecordSize]), TempValue2, "9000",NOT_SAVED)
                                            CmdSelect3G_not_recorded(file[fiFilePathID], None, "9000")
                                            # CmdSelect3G(file[fiFilePathID], expected, "9000",NOT_SAVED) # Select back the original file
                                            CmdReadRecord3G(int(file[fiRecordNumber]), RECMODE2G_ABS,
                                                            int(file[fiRecordSize]), None, "9000", NOT_SAVED)
                                            # CmdReadRecord3G(int(file[fiRecordNumber]), RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000",NOT_SAVED)
                                            TempValue = copy.deepcopy(response)
                                        else:
                                            CmdUpdateRecord3G(1, RECMODE2G_ABS, int(file[fiRecordSize]), TempValue2,
                                                                "9000", NOT_SAVED)
                                            # CmdUpdateRecord3G(1, RECMODE2G_ABS, int(file[fiRecordSize]), TempValue2, "9000",NOT_SAVED)
                                            CmdSelect3G_not_recorded(file[fiFilePathID], None, "9000")
                                            # CmdSelect3G(file[fiFilePathID], expected, "9000",NOT_SAVED) # Select back the original file
                                            CmdReadRecord3G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000", NOT_SAVED)
                                            # CmdReadRecord3G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000",NOT_SAVED)
                                            TempValue = copy.deepcopy(response)
                                            # break
                                elif CheckList(file2[fiFIleStruct], sFileStructCY):
                                    if file[fiRecordSize] != 0:
                                        # CmdUpdateRecord3G(0, RECMODE2G_PREV, int(file[fiRecordSize]), TempValue2, "9000")
                                        CmdUpdateRecord3G(0, RECMODE2G_PREV, int(file[fiRecordSize]), TempValue2,
                                                            "9000", NOT_SAVED)
                                        CmdSelect3G_not_recorded(file[fiFilePathID], None, "9000")
                                        # CmdSelect3G(file[fiFilePathID], expected, "9000",NOT_SAVED) # Select back the original file
                                        CmdReadRecord3G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000", NOT_SAVED)
                                        # CmdReadRecord3G(1, RECMODE2G_ABS, int(file[fiRecordSize]), None, "9000",NOT_SAVED)
                                        TempValue = copy.deepcopy(response)
                                        # break
                                else:
                                    index = 0
                                    while index < int(file2[fiFileSize]):
                                        # if index >= ExpectedLength:
                                        #    break
                                        if (index + 255) > int(file2[fiFileSize]):
                                            TempLen = int(file2[fiFileSize]) - index
                                        else:
                                            TempLen = 255
                                        Buffer = []
                                        i = 0
                                        while i < TempLen and (index + i) < len(TempValue2):
                                            Buffer.append(TempValue2[index + i])
                                            i += 1
                                        CmdUpdateBinary3G(index, TempLen, Buffer, "9000", NOT_SAVED)
                                        # CmdUpdateBinary3G(index, TempLen, Buffer, "9000",NOT_SAVED)
                                        # CmdUpdateBinary2G(index, TempLen, TempValue2[index:], "9000")
                                        index += TempLen

                                    CmdSelect3G_not_recorded(file[fiFilePathID], None, "9000")
                                    # CmdSelect3G(file[fiFilePathID], expected, "9000",NOT_SAVED) # Select back the original file
                                    index = 0
                                    while index < int(file[fiFileSize]):
                                        # if index >= ExpectedLength:
                                        #    break
                                        if (index + 255) > int(file[fiFileSize]):
                                            TempLen = int(file[fiFileSize]) - index
                                        else:
                                            TempLen = 255
                                        CmdReadBinary3G(index, TempLen, None, "9000", NOT_SAVED)
                                        # CmdReadBinary3G(index, TempLen, None, "9000",NOT_SAVED)
                                        TempValue += copy.deepcopy(response)
                                        index += TempLen

                                # if TempValue2 == [] or TempValue == []:    # Avoid error when the linked file cannot be updated (i.e. access condition never)
                                if TempValue == []:  # Avoid error when the linked file cannot be updated (i.e. access condition never)
                                    WARNING(" Linked file cannot be read !!")
                                    if OPT_ERROR_FILE:
							            appendVerifError(curFile, curLinkedFile, curOps, 'Linked file cannot be read', 0,
											            '', 0, '', curFileDescName)
                                else:
                                    if TempValue2 != TempValue:
                                        ERROR(" Different UPDATED Linked file Value !!")
                                        if OPT_ERROR_FILE:
								            appendVerifError(curFile, curLinkedFile, curOps,
												            'Different UPDATED Linked file Value', 1, '', 0, '',
												            curFileDescName)

                                # Revert back the value to avoid issue when linked file read later
                                # -----------------------------------------------------
                                TempValue2[:] = [a ^ 0xFF for a in TempValue2]

                                TempValue = []  # Reset TempValue
                                CmdSelect3G_not_recorded(file2[fiFilePathID], None, "9000")
                                # CmdSelect3G(file2[fiFilePathID], None, "9000",NOT_SAVED) # Select The Linked File
                                if CheckList(file2[fiFIleStruct], sFileStructLF):
                                    if file[fiRecordSize] != 0:
                                        if file[fiRecordNumber] != '':
                                            CmdUpdateRecord3G(int(file[fiRecordNumber]), RECMODE2G_ABS,
                                                                int(file2[fiRecordSize]), TempValue2, "9000",
                                                                NOT_SAVED)
                                        else:
                                            CmdUpdateRecord3G(1, RECMODE2G_ABS, int(file2[fiRecordSize]),
                                                                TempValue2,
                                                                "9000", NOT_SAVED)
                                elif CheckList(file2[fiFIleStruct], sFileStructCY):
                                    # There is no point updating Cyclic file as it cannot be returned to original state without updating all record.
                                    # CmdUpdateRecord2G(0, RECMODE2G_PREV, int(file[fiRecordSize]), TempValue2, "9000")
                                    pass
                                else:
                                    index = 0
                                    while index < int(file2[fiFileSize]):
                                        # if index >= ExpectedLength:
                                        #    break
                                        if (index + 128) > int(file2[fiFileSize]):
                                            TempLen = int(file2[fiFileSize]) - index
                                        else:
                                            TempLen = 128
                                        Buffer = []
                                        i = 0
                                        while i < TempLen and (index + i) < len(TempValue2):
                                            Buffer.append(TempValue2[index + i])
                                            i += 1
                                        CmdUpdateBinary3G(index, TempLen, Buffer, "9000", NOT_SAVED)
                                        # CmdUpdateBinary2G(index, TempLen, Buffer, "9000",NOT_SAVED)
                                        index += TempLen

                        break;  # No need to check further if already found


                        # TODO:
                        # Check if the files is in header and mark the file (CardFileList)
                        #   If the file is not found in the File List, Return Error

                        # prevFile = curFile

                        ############# End of Add Check Content 3G ####################

            # check link 3g ends here

        prevFile = curFile

    # ErrorFile.writelines(str(verificationErrors)) # raw error

    error_list = verificationErrors

    # print 'DEBUG ERROR LIST\n' + str(error_list) # debug
    runlog_buffer.append('DEBUG ERROR LIST\n' + str(error_list))

    # build list of file id
    ef_list_tmp = []
    for error in error_list:
        ef_list_tmp.append(error.get('fileId'))

    ef_list = set(ef_list_tmp)

    organized_errors = []

    if OPT_USE_CLIENT:
        runlog_buffer.append(str(ef_list.__len__()) + ' file(s) with errors/warnings:')
    else:
        print str(ef_list.__len__()) + ' file(s) with errors/warnings:'
    for ef in ef_list:
        for error in error_list:
            if error.get('fileId') == ef:
                fileName = error.get('fileName')
                break
        if OPT_USE_CLIENT:
            runlog_buffer.append(formatFileId(ef) + ': ' + fileName)
        else:
            print formatFileId(ef)
        error_items = []
        for error in error_list:
            if error.get('fileId') == ef:
                error_items.append(error)
        organized_errors.append({'errorFileId': ef, 'errors': error_items})
    if OPT_USE_CLIENT:
        runlog_buffer.append('')
    else:
        print ""

    # print 'DEBUG ORGANIZED ERROR\n' + str(organized_errors) # debug

    if OPT_PRINT_ERROR:
        for ef_error in organized_errors:
            errors = ef_error.get('errors')
            print formatFileId(ef_error.get('errorFileId') + ': ' + errors[0].get('fileName'))
            operation_check_link_printed = False
            operation_test_update_link_printed = False
            operation_test_content_printed = False
            operation_test_3g_acc_printed = False
            operation_test_3g_stat_printed = False
            acc_msg = []
            occurrence_check_link = 0
            occurrence_test_update_link = 0
            occurrence_test_content = 0
            occurrence_test_3g_acc = 0
            occurrence_test_3g_stat = 0
            for error_item in errors:
                if error_item.get('operation') == 'Check Linked File':
                    occurrence_check_link += 1
                if error_item.get('operation') == 'Test UPDATE Linked File':
                    occurrence_test_update_link += 1
                if error_item.get('operation') == 'Test File Content':
                    occurrence_test_content += 1
                if error_item.get('operation') == 'Test 3G Access Condition':
                    occurrence_test_3g_acc += 1
                if error_item.get('operation') == 'Test 3G Status':
                    occurrence_test_3g_stat += 1

            for error_item in errors:
                if error_item.get('operation') == 'Check Linked File':
                    if not operation_check_link_printed:
                        print 'operation   : ' + error_item.get('operation') + ' (' + str(occurrence_check_link) + ')'
                        print 'linked file : ' + error_item.get('linkedFile')
                        operation_check_link_printed = True
                    print 'message     : ' + error_item.get('errMsg')
                if error_item.get('operation') == 'Test Access Condition':
                    print 'operation   : ' + error_item.get('operation')
                    print 'message     : ' + error_item.get('errMsg')
                    print 'output      : ' + error_item.get('output')
                    print 'expected    : ' + error_item.get('expected')
                if error_item.get('operation') == 'Test File Content':
                    if not operation_test_content_printed:
                        print 'operation   : ' + error_item.get('operation') + ' (' + str(occurrence_test_content) + ')'
                        print 'message     : ' + error_item.get('errMsg')
                        operation_test_content_printed = True
                    if error_item.get('recNum') == 0:
                        pass
                    else:
                        print 'record      : ' + str(error_item.get('recNum'))
                    print 'output      : ' + error_item.get('output')
                    print 'expected    : ' + error_item.get('expected')
                if error_item.get('operation') == 'Test 3G Access Condition':
                    if not operation_test_3g_acc_printed:
                        print 'operation   : ' + error_item.get('operation') + ' (' + str(occurrence_test_3g_acc) + ')'
                        operation_test_3g_acc_printed = True
                    if not error_item.get('errMsg') in acc_msg:
                        print 'message     : ' + error_item.get('errMsg')
                        acc_msg.append(error_item.get('errMsg'))
                if error_item.get('operation') == 'Test 3G Status':
                    if not operation_test_3g_stat_printed:
                        print 'operation   : ' + error_item.get('operation') + ' (' + str(occurrence_test_3g_stat) + ')'
                        operation_test_3g_stat_printed = True
                    print 'message     : ' + error_item.get('errMsg')
                if error_item.get('operation') == 'Test UPDATE Linked File':
                    if not operation_test_update_link_printed:
                        print 'operation   : ' + error_item.get('operation') + ' (' + str(
                            occurrence_test_update_link) + ')'
                        operation_test_update_link_printed = True
                    print 'message     : ' + error_item.get('errMsg')

            print ""

    if OPT_ERROR_FILE:
        createDocumentHeader()
        ErrorFile.writelines('<div>' + str(ef_list.__len__()) + ' file(s) with errors/warnings:</div>')
        ErrorFile.writelines('<div>')
        for ef in ef_list:
            for error in error_list:
                if error.get('fileId') == ef:
                    fileName = error.get('fileName')
                    break
            if not formatFileId(ef) == None:
                ErrorFile.writelines('<a href="#' + ef + '">' + formatFileId(ef) + ': ' + fileName + '</a><br>')
            else:
                ErrorFile.writelines('<a href="#' + ef + '">' + 'NoneType' + '</a><br>')
        ErrorFile.writelines('</div>')

        for ef_error in organized_errors:
            errors = ef_error.get('errors')
            if not formatFileId(ef_error.get('errorFileId')) == None:
                ErrorFile.writelines('<div><h2 id="' + ef_error.get('errorFileId') + '">' + formatFileId(ef_error.get('errorFileId')) + ': ' + errors[0].get('fileName') + '</h2></div>')
            else:
                ErrorFile.writelines('<div><h2 id="' + ef_error.get('errorFileId') + '">' + 'NoneType' + ': ' + errors[0].get('fileName') + '</h2></div>')
            operation_check_link_printed = False
            operation_test_update_link_printed = False
            operation_test_content_printed = False
            operation_test_3g_acc_printed = False
            operation_test_3g_stat_printed = False
            acc_msg = []
            occurrence_check_link = 0
            occurrence_test_update_link = 0
            occurrence_test_content = 0
            occurrence_test_3g_acc = 0
            occurrence_test_3g_stat = 0
            for error_item in errors:
                if error_item.get('operation') == 'Check Linked File':
                    occurrence_check_link += 1
                if error_item.get('operation') == 'Test UPDATE Linked File':
                    occurrence_test_update_link += 1
                if error_item.get('operation') == 'Test File Content':
                    occurrence_test_content += 1
                if error_item.get('operation') == 'Test 3G Access Condition':
                    occurrence_test_3g_acc += 1
                if error_item.get('operation') == 'Test 3G Status':
                    occurrence_test_3g_stat += 1

            counter_check_link = 0
            counter_test_update_link = 0
            counter_test_content = 0
            counter_test_3g_acc = 0
            counter_test_3g_stat = 0
            lf_header_printed = False
            ef_not_found = False
            for error_item in errors:
                if error_item.get('operation') == 'Check Linked File':
                    counter_check_link += 1
                    if not operation_check_link_printed:
                        ErrorFile.writelines('<div><h3>' + error_item.get('operation') + '</h3></div>')
                        createTableHeader()
                        ErrorFile.writelines('<tr><td>Linked file</td>')
                        ErrorFile.writelines('<td>' + formatFileId(error_item.get('linkedFile')) + '</td></tr>')
                        operation_check_link_printed = True
                    if error_item.get('severity') == 1:
                        ErrorFile.writelines('<tr><td class="error">Error</td>')
                    else:
                        ErrorFile.writelines('<tr><td class="warning">Warning</td>')
                    ErrorFile.writelines('<td>' + error_item.get('errMsg') + '</td></tr>')
                    if counter_check_link == occurrence_check_link:
                        createTableFooter()

                if error_item.get('operation') == 'Test Access Condition':
                    ErrorFile.writelines('<div><h3>' + error_item.get('operation') + '</h3></div>')
                    createTableHeader()
                    if error_item.get('severity') == 1:
                        ErrorFile.writelines('<tr><td class="error">Error</td>')
                    else:
                        ErrorFile.writelines('<tr><td class="warning">Warning</td>')
                    ErrorFile.writelines('<td>' + error_item.get('errMsg') + '</td></tr>')
                    out = error_item.get('output')
                    exp = error_item.get('expected').replace('<', ' ')
                    ErrorFile.writelines('<tr><td>Output</td>')
                    ErrorFile.writelines('<td class="data">' + markErrorByte(out, exp) + '</td></tr>')
                    ErrorFile.writelines('<tr><td>Expected</td>')

                    # Strip variable from exp
                    ErrorFile.writelines('<td class="data">' + re.sub('Variable name:.*', ' ', exp) + '</td></tr>')

                    createTableFooter()

                if error_item.get('operation') == 'Test File Content':
                    counter_test_content += 1
                    if not operation_test_content_printed:
                        ErrorFile.writelines('<div><h3>' + error_item.get('operation') + '</h3></div>')
                        createTableHeader()
                        if error_item.get('severity') == 1:
                            ErrorFile.writelines('<tr><td class="error">Error</td>')
                        else:
                            ErrorFile.writelines('<tr><td class="warning">Warning</td>')
                        ErrorFile.writelines('<td>' + error_item.get('errMsg') + '</td></tr>')
                        operation_test_content_printed = True

                    if error_item.get('recNum') == 0:
                        out = error_item.get('output')
                        exp = error_item.get('expected').replace('<', ' ')
                        ErrorFile.writelines('<tr><td>Output</td>')
                        ErrorFile.writelines('<td class="data">' + markErrorByte(out, exp) + '</td></tr>')

                        if '%' in exp:  # #handling variable
                            varname = re.findall('%\w*', exp)[0]
                            exp = re.sub('Variable name:.*', '', exp)
                            ErrorFile.writelines('<tr><td rowspan="2">Expected</td>')
                            ErrorFile.writelines('<td class="data"> {} <tr><td>Variable name: {} </td></tr> </td> </tr>'.format(exp, '<mark class="varname">' + varname + '</mark>'))
                        else:
                            ErrorFile.writelines('<tr><td>Expected</td>')
                            ErrorFile.writelines('<td class="data">' + exp + '</td></tr>')

                        if counter_test_content == occurrence_test_content:
                            createTableFooter()
                    else:
                        if not lf_header_printed:
                            createTableFooter()
                            createTableHeader()  # table for LF files with records
                            ErrorFile.writelines('<tr><th>Record</th><th colspan="2">Data</th></tr>')
                            lf_header_printed = True

                        out = error_item.get('output')
                        exp = error_item.get('expected').replace('<', ' ')
                        if '%' in exp:
                            ErrorFile.writelines('<tr><td rowspan="3">')  # handling variable
                        else:
                            ErrorFile.writelines('<tr><td rowspan="2">')
                        ErrorFile.writelines(str(error_item.get('recNum')) + '</td>')
                        ErrorFile.writelines('<td>Output</td>')
                        ErrorFile.writelines('<td class="data">' + markErrorByte(out, exp) + '</td></tr>')

                        if '%' in exp:  # handling variable
                            varname = re.findall('%\w*', exp)[0]
                            exp = re.sub('Variable name:.*', '', exp)
                            ErrorFile.writelines('<tr><td rowspan = "2">Expected</td>')
                            ErrorFile.writelines('<td class="data">{}</td></tr> <tr><td>Variable name: {} </td></tr>'.format(exp, '<mark class="varname">' + varname + '</mark>'))
                        else:
                            ErrorFile.writelines('<tr><td>Expected</td>')
                            ErrorFile.writelines('<td class="data">' + exp + '</td></tr>')

                        if counter_test_content == occurrence_test_content:
                            createTableFooter()

                if error_item.get('operation') == 'Test 3G Status':
                    counter_test_3g_stat += 1
                    if not operation_test_3g_stat_printed:
                        ErrorFile.writelines('<div><h3>' + error_item.get('operation') + '</h3></div>')
                        createTableHeader()
                        operation_test_3g_stat_printed = True
                    if error_item.get('severity') == 1:
                        ErrorFile.writelines('<tr><td class="error">Error</td>')
                    else:
                        ErrorFile.writelines('<tr><td class="warning">Warning</td>')
                    ErrorFile.writelines('<td>' + error_item.get('errMsg') + '</td></tr>')
                    if error_item.get('errMsg') == 'Wrong File Size' or error_item.get(
                            'errMsg') == 'Wrong File Record Size' or error_item.get(
                            'errMsg') == 'Wrong Number of Record' or error_item.get('errMsg') == 'Wrong SFI' or error_item.get('errMsg') == 'SFI Not Present on Card':
                        ErrorFile.writelines('<tr><td>Output</td>')
                        ErrorFile.writelines('<td class="data">' + error_item.get('output') + '</td></tr>')
                        ErrorFile.writelines('<tr><td>Expected</td>')
                        ErrorFile.writelines('<td class="data">' + error_item.get('expected') + '</td></tr>')
                    if error_item.get('errMsg') == 'File Not found in the Card':
                        ef_not_found = True
                    if counter_test_3g_stat == occurrence_test_3g_stat:
                        createTableFooter()

                if error_item.get('operation') == 'Test 3G Access Condition':
                    if ef_not_found:
                        continue
                    counter_test_3g_acc += 1
                    if not operation_test_3g_acc_printed:
                        ErrorFile.writelines('<div><h3>' + error_item.get('operation') + '</h3></div>')
                        createTableHeader()
                        operation_test_3g_acc_printed = True
                    if not error_item.get('errMsg') in acc_msg:
                        if error_item.get('severity') == 1:
                            ErrorFile.writelines('<tr><td class="error">Error</td>')
                        else:
                            ErrorFile.writelines('<tr><td class="warning">Warning</td>')
                        ErrorFile.writelines('<td>' + error_item.get('errMsg') + '</td></tr>')
                        ErrorFile.writelines('<tr><td>Output</td>')
                        ErrorFile.writelines('<td class="data">' + str(error_item.get('output')) + '</td></tr>')
                        ErrorFile.writelines('<tr><td>Expected</td>')
                        ErrorFile.writelines('<td class="data">' + str(error_item.get('expected')) + '</td></tr>')
                        acc_msg.append(error_item.get('errMsg'))
                    if counter_test_3g_acc == occurrence_test_3g_acc:
                        createTableFooter()

                if error_item.get('operation') == 'Test UPDATE Linked File':
                    counter_test_update_link += 1
                    if not operation_test_update_link_printed:
                        ErrorFile.writelines('<div><h3>' + error_item.get('operation') + '</h3></div>')
                        createTableHeader()
                        operation_test_update_link_printed = True
                    if error_item.get('severity') == 1:
                        ErrorFile.writelines('<tr><td class="error">Error</td>')
                    else:
                        ErrorFile.writelines('<tr><td class="warning">Warning</td>')
                    ErrorFile.writelines('<td>' + error_item.get('errMsg') + '</td></tr>')
                    if counter_test_update_link == occurrence_test_update_link:
                        createTableFooter()

        if len(not_exist_docb) != 0:
            ErrorFile.writelines(
                '<div>' + str(not_exist_docb.__len__()) + ' file(s) that exist in card but not in DocB:</div>')
            ErrorFile.writelines('<div>')
            for ef in not_exist_docb:
                if not formatFileId(ef) == None:
                    ErrorFile.writelines(formatFileId(ef) + '<br>')
                else:
                    ErrorFile.writelines('NoneType' + '<br>')
            ErrorFile.writelines('</div>')

        ErrorFile.writelines('<div><i>Created on ' + datetime.now().strftime("%Y-%m-%d %H:%M") + '</i></div>')
        createDocumentFooter()

    if OptWrite2File:
        OutputFile.flush()
        OutputFile.close()
    if DEBUG_LOG:
        DebugFile.flush()
        DebugFile.close()
    if OPT_ERROR_FILE:
        ErrorFile.flush()
        ErrorFile.close()

    if SEND_TO_CARD:
        connection.disconnect()

    if OPT_USE_CLIENT:
        runlog_buffer.append("List of EF that mandatory but not exist in card : " + str(not_exist_mandatory))
        runlog_buffer.append("List of EF that exist in card but not in DocB : " + str(not_exist_docb))
    else:
        print("--------------------------------------------------")
        print("List of EF that mandatory but not exist in card : ", not_exist_mandatory)
        print("--------------------------------------------------")
        print
        print("--------------------------------------------------")
        print("List of EF that exist in card but not in DocB : ", not_exist_docb)
        print("--------------------------------------------------")
    RESULT_SUMMARY()

    if OPT_CREATE_FULL_SCRIPT:

        keystring = '; Variable Used. Original Value: '

        # read content of the output file
        with open(OutputFileName) as f:
            lines = f.readlines()
            lines.append('')  # add empty line to handle valuation at the end of the file
            for num, i in enumerate(lines):
                if keystring in i:
                    var = re.findall(keystring + r'([^\s]+)', i)  # search variable name and store in var[0]
                    # 1 APDU or multiple valuated record files
                    if lines[num + 2] == '\n' or lines[num + 2].startswith(keystring) or lines[num + 2][3:5] == 'B2':
                        lines[num + 1] = lines[num + 1][0:15] + '[' + var[0] + '] (9000)\n'
                    else:  # variable split over several APDU
                        j = 1
                        start = 1
                        while (lines[num + j] != '\n') and (lines[num + j][3:5] == 'B0'):
                            end = str(int(lines[num + j][12:14], 16))
                            lines[num + j] = lines[num + j][0:15] + '[ G({};{}) ] (9000)\n'.format(start, end)
                            start += int(end)
                            j += 1
                        lines[num + 1] = '.SET_BUFFER G {}\n'.format(var[0]) + lines[num + 1]


                        # Replace 2G VerifyCode APDU with variable
                if i.startswith('A0 20 00 00 08 '): lines[num] = i[:15] + '%ADM1 (9000)\n'
                if i.startswith('A0 20 00 01 08 ') or i.startswith(
                    '; CHV1 is disabled. No CHV1 verification required.'): lines[
                    num] = '.IFNDEF PIN1_DISABLED\n      ' + 'A0 20 00 01 08 ' + '%CHV1 (9000)\n.ENDIF\n'
                if i.startswith('A0 20 00 02 08 '): lines[num] = i[:15] + '%CHV2 (9000)\n'

                # Replace 3G VerifyCode APDU with variable
                if i.startswith('00 20 00 0A 08 '): lines[num] = i[:15] + '%ADM1 (9000)\n'
                if i.startswith('00 20 00 01 08 ') or i.startswith(
                    '; GPIN is disabled. No GPIN verification required.'): lines[
                    num] = '.IFNDEF PIN1_DISABLED\n      ' + '00 20 00 01 08 ' + '%CHV1 (9000)\n.ENDIF\n'
                if i.startswith('00 20 00 81 08 '): lines[num] = i[:15] + '%CHV2 (9000)\n'

        # Write Full Script
        with open(FullScriptFileName, 'w+') as f:
            generation_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            f.write('; Generated with VerifClient v{} on {}\n\n.CALL Mapping.txt\n.CALL Options.txt\n\n'.format(FILE_VERIF_VERSION, generation_date))
            for i in lines: f.write(i)

    ###############################################

    EXP_FROM_CARD = 0

    if OPT_USE_CLIENT:
        for line in runlog_buffer:
            if not line == None:
                runLog.writelines(line + '\n')
            else:
                runLog.writelines('NoneType' + '\n')
        runLog.flush()
        runLog.close()
        del runlog_buffer[:] # clear buffer

    ### END OF RUN BLOCK ###

    return True, 'Verification success'

# logger = logging.getLogger(__name__)

def proceed():
    parseOk, parseMsg = parseConfigXml()

    if parseOk:
        logger.info(parseMsg + '. FileVerif is executing..')
        try:
            verifStat, verifMsg = run(True)
        except Exception, e:
            logger.error('FileVerif exits with error: ' + str(e) + ' at ' + efMarker)
            return False, str(e) + ' at ' + efMarker
        
        if verifStat:
            logger.info('FileVerif finished.')
        else:
            logger.error('FileVerif exits with error: ' + verifMsg)

        return verifStat, verifMsg

    else:
        logger.error('FileVerif aborted while parsing configuration: ' + parseMsg)
        return False, 'FileVerif aborted while parsing configuration: ' + parseMsg

if __name__ == '__main__':
    run()
