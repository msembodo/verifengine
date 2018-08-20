'''
Converts ex-Morpho technical report to csv as input for BOTS file verification tool
Author: Martyono Sembodo
Last update: 14.07.2018
Description: add ability to parse multiple access conditions with 2 or more operands
'''

from __future__ import print_function
from xml.dom.minidom import parse
import sys
import logging

logging.basicConfig(level=logging.INFO,
                    format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
                    datefmt="%H:%M:%S", stream=sys.stdout)

logger = logging.getLogger(__name__)

docName = '1504ES049V03__P49.xml'
csvName = '1504ES049V03__P49.csv'

run_as_module = False

class MorphoDocParser:
    _fileName = ''
    _csvFileName = ''

    _converter_log_buffer = []
    
    # constants
    _ERR_WARNING = 10
    _ERR_ERROR = 11
    _ERR_FATAL = 12
    
    def __init__(self, doc, csv):
        self._fileName = doc
        self._csvFileName = csv
    
    def _printErr(self, errObj, errMsg, severity):
        if severity == self._ERR_WARNING:
            self._print_log('WARNING >>> ' + errObj + ': ' + errMsg)
        if severity == self._ERR_ERROR:
            self._print_log('ERROR >>> ' + errObj + ': ' + errMsg)
        if severity == self._ERR_FATAL:
            self._print_log('FATAL >>> ' + errObj + ': ' + errMsg)
    
    def _filterHex(self, String):
        temp = ''
        # print ("Original :" + String)
        String = String.upper()
        # print ("To Upper :" + String)
        for a in String:
            if a >= '0' and a <= '9':
                temp = temp + a
            elif a >= 'A' and a <= 'F':
                temp = temp + a
        return temp

    def _translateAcc(self, strAcc):
        if strAcc.__contains__('-or-'):
            acc_multi_tmp = strAcc.replace('(', '')
            acc_multi_tmp = acc_multi_tmp.replace(')', '')
            acc_multi_tmp = acc_multi_tmp.replace('-or-', '')
            acc_multi = acc_multi_tmp.split('  ')
            acc_multi2 = []
            for single_acc in acc_multi:
                if single_acc == 'APIN1':
                    single_acc = 'GPIN1'
                if single_acc == '2APIN1':
                    single_acc = 'LPIN1'
                acc_multi2.append(single_acc)
            acc_multi_str = ''
            multi_acc_index = 0
            for single_acc2 in acc_multi2:
                acc_multi_str += single_acc2
                if multi_acc_index < (len(acc_multi2) - 1):
                    acc_multi_str += ' OR '
                multi_acc_index += 1
            return acc_multi_str
        
        if strAcc == 'APIN1':
            translatedAcc = 'GPIN1'
        elif strAcc == '2APIN1':
            translatedAcc = 'LPIN1'
        else:
            translatedAcc = strAcc
        return translatedAcc

    def _fixData(self, data):
        dataBytes = data.split(' ')
        dataBytes2 = []
        for i in dataBytes:
            if i.__contains__('('):
                openBracketIndex = i.index('(')
                closeBracketIndex = i.index(')')
                multiplicationFactorStr = i[openBracketIndex + 1:closeBracketIndex - 1]
                multiplicationFactorInt = int(multiplicationFactorStr)
                dataByte = i[:openBracketIndex]
                for j in range(0, multiplicationFactorInt):
                    dataBytes2.append(dataByte)
                continue
            dataBytes2.append(i)
        return ''.join(dataBytes2)

    def _fixContent(self, rawContent):
        fixedContent = []
        for i in rawContent:
            i = i[5:]
            colonIndex = i.index(':')
            recNum = i[:colonIndex]
            if recNum.__contains__('-'):
                rangeIndex = recNum.split(' - ')
                # rangeIndex is the start/end of same data
                for k in range(int(rangeIndex[0]) - 1, (int(rangeIndex[1]) - 1) + 1):
                    fixedContent.append(i[colonIndex + 2:])
                continue

            fixedContent.append(i[colonIndex + 2:])

        # clean contents from valuations
        index = 0
        for c in fixedContent:
            if c.__contains__('['):
                fixedContent[index] = 'FF'
            index += 1

        # format contents
        index = 0
        for c in fixedContent:
            fixedContent[index] = self._fixData(c)
            index += 1

        return fixedContent

    def _print_log(self, log_message):
        if run_as_module:
            self._converter_log_buffer.append(log_message)
        else:
            print(log_message)

    def proceed(self):
        # switches
        OPT_VERBOSE = 1
        OPT_DEBUG = 0

        # Open XML document using minidom parser
        # try:
        DOMTree = parse(self._fileName)
        # except IOError:
            # self._printErr(self._fileName, 'Error opening/reading file', self._ERR_FATAL)
            # sys.exit(1)
        
        workbook = DOMTree.documentElement
        worksheets = workbook.getElementsByTagName('Worksheet')
        sharedDataExist = False
        for sheet in worksheets:
            if sheet.getAttribute('ss:Name') == 'FileData':
                fileDataSheet = sheet
            if sheet.getAttribute('ss:Name') == 'FileAccessRights DF\'s':
                acc_df_sheet = sheet
            if sheet.getAttribute('ss:Name') == 'FileAccessRights EF\'s':
                acc_ef_sheet = sheet
            if sheet.getAttribute('ss:Name') == 'SharedData':
                sharedDataExist = True
                sharedDataSheet = sheet
        
        # extract data from sheet 'FileData'
        fileDataTable = fileDataSheet.getElementsByTagName('Table')[0]
        fileDataRows = fileDataTable.getElementsByTagName('Row')
        
        # extract data from sheet 'FileAccessRights DF's'
        accDFTable = acc_df_sheet.getElementsByTagName('Table')[0]
        accDFRows = accDFTable.getElementsByTagName('Row')

        # extract data from sheet 'FileAccessRights EF's'
        accEFTable = acc_ef_sheet.getElementsByTagName('Table')[0]
        accEFRows = accEFTable.getElementsByTagName('Row')

        # extract data from sheet 'SharedData'
        if sharedDataExist:
            sharedDataTable = sharedDataSheet.getElementsByTagName('Table')[0]
            sharedDataRows = sharedDataTable.getElementsByTagName('Row')

        # list of populated DFs
        definedDF = []
        
        # getting DF name & path from the sheet
        for i in range(1, len(accDFRows)):
            dataRow = accDFRows[i]
            idCell = dataRow.getElementsByTagName('Cell')[0]
            idData = idCell.getElementsByTagName('Data')[0].childNodes[0].data
            pathCell = dataRow.getElementsByTagName('Cell')[1]
            pathData = pathCell.getElementsByTagName('Data')[0].childNodes[0].data
            pathDataSet = False
            if idData == '3F00':
                pathData = ''
                pathDataSet = True
            if idData != '3F00' and pathData == '-':
                pathData = '3F00'
                pathDataSet = True
            if not pathDataSet:
                if pathData[:4] != '3F00':
                    pathData = '3F00' + self._filterHex(pathData)
                else:
                    pathData = self._filterHex(pathData)
            
            definedDF.append(str(pathData + idData))
        
        self._print_log('definedDF: ' + str(definedDF)) # debug
        self._print_log('shared data tab exist: %s' % (sharedDataExist))
            
        # cell indexes
        ciFileId = 0        # File ID
        ciFileName = 1      # File Name
        ciType = 2          # Type
        ciLinkStatus = 3    # Link Status
        ciRecNb = 4         # Rec Nb
        ciRecSize = 5       # Rec Size
        ciBodyFileSize = 6  # Body File Size
        ciContent = 7       # Contents
        ciDescription = 8   # Description
        
        filesInCard = [] # master data in dictionaries
        
        if len(definedDF) != 0:
            predefinedDF = definedDF
        else:
            predefinedDF = ['3F00', '3F007F10', '3F007F20', '3F007F105F3A', \
                            '3F007FF0', '3F007FF05F3B', \
                            '3F007FBC', '3F007FBB']
        
        for dataRow in fileDataRows:
            if dataRow.hasChildNodes():
                rowCell = dataRow.getElementsByTagName('Cell')[0]
                if rowCell.getElementsByTagName('Data'):
                    cellData = rowCell.getElementsByTagName('Data')[0].childNodes[0].data
                    if cellData == '3F00':
                        mfRowIndex = fileDataRows.index(dataRow)
                        break
        
        # read start from MF row
        lfMarker = ''
        filePath = ''
        self._print_log('%-10s%-30s%-5s%-4s%-5s%-5s%s' % ('efid', 'name', 'type', 'rec', 'lgth', 'size', 'content'))
        for i in range(mfRowIndex, len(fileDataRows)):
            dataRow = fileDataRows[i]
            dataFields = []
            tmpDataDict = {}
            nextRecord = False
            for i in range(9):
                dataFields.append('')
            dataCells = dataRow.getElementsByTagName('Cell')
#             if dataCells[0].hasAttribute('ss:Index'):
            if len(dataCells) == 1:
                continue # skip blank row
            else:
                if dataCells[ciFileId].getElementsByTagName('Data'):
                    dataFields[ciFileId] = dataCells[ciFileId].getElementsByTagName('Data')[0].childNodes[0].data
                    if str(dataCells[ciType].getElementsByTagName('Data')[0].childNodes[0].data) == 'MF' or \
                            str(dataCells[ciType].getElementsByTagName('Data')[0].childNodes[0].data) == 'DF' or \
                            str(dataCells[ciType].getElementsByTagName('Data')[0].childNodes[0].data) == 'ADF':
                        for df in predefinedDF:
                            if len(df) == 4:
                                filePath = df
                            if len(df) == 8:
                                if str(dataFields[ciFileId]) == df[4:]:
                                    filePath = df
                            if len(df) == 12:
                                if str(dataFields[ciFileId]) == df[8:]:
                                    filePath = df
                    if str(dataFields[ciFileId])[:4] == filePath[-4:]:
                        tmpDataDict['fileId'] = filePath
                    else:
                        tmpDataDict['fileId'] = filePath + str(dataFields[ciFileId])
                    lfMarker = tmpDataDict['fileId']
                else:
                    nextRecord = True
                if dataCells[ciFileName].getElementsByTagName('Data'):
                    dataFields[ciFileName] = dataCells[ciFileName].getElementsByTagName('Data')[0].childNodes[0].data
                    tmpDataDict['fileName'] = str(dataFields[ciFileName])
                if dataCells[ciType].getElementsByTagName('Data'):
                    dataFields[ciType] = dataCells[ciType].getElementsByTagName('Data')[0].childNodes[0].data
                    if str(dataFields[ciType]) == 'ADF':
                        tmpDataDict['type'] = 'DF'
                    else:
                        tmpDataDict['type'] = str(dataFields[ciType])
                if dataCells[ciRecNb].getElementsByTagName('Data'):
                    dataFields[ciRecNb] = dataCells[ciRecNb].getElementsByTagName('Data')[0].childNodes[0].data
                    tmpDataDict['recNb'] = str(dataFields[ciRecNb])
                if dataCells[ciRecSize].getElementsByTagName('Data'):
                    dataFields[ciRecSize] = dataCells[ciRecSize].getElementsByTagName('Data')[0].childNodes[0].data
                    tmpDataDict['recSize'] = str(dataFields[ciRecSize])
                if dataCells[ciBodyFileSize].getElementsByTagName('Data'):
                    if dataCells[ciBodyFileSize].getElementsByTagName('Data')[0].hasChildNodes():
                        dataFields[ciBodyFileSize] = dataCells[ciBodyFileSize].getElementsByTagName('Data')[0].childNodes[0].data
                        tmpDataDict['fileSize'] = str(dataFields[ciBodyFileSize])
                if dataCells[ciContent].getElementsByTagName('Data'):
                    if dataCells[ciContent].getElementsByTagName('Data')[0].hasChildNodes():
                        dataFields[ciContent] = dataCells[ciContent].getElementsByTagName('Data')[0].childNodes[0].data
                        if not nextRecord:
                            contentList = [str(dataFields[ciContent])]
                            tmpDataDict['content'] = contentList
                        else:
                            indexCount = 0
                            for fileIncard in filesInCard:
                                if fileIncard['fileId'] == lfMarker:
                                    efIndex = indexCount
                                    break
                                indexCount += 1
                            filesInCard[efIndex]['content'].append(str(dataFields[ciContent]))
            
            if not nextRecord:
                filesInCard.append(tmpDataDict)
                
            self._print_log('%-10s%-30s%-5s%-4s%-5s%-5s%s' %
                  (dataFields[ciFileId], dataFields[ciFileName], dataFields[ciType], dataFields[ciRecNb], dataFields[ciRecSize], 
                   dataFields[ciBodyFileSize], dataFields[ciContent]))

        # restructuring master data
        for dict in filesInCard:
            if dict['type'] == 'T':
                dict['type'] = 'TR'
            if dict['type'] == 'C':
                dict['type'] = 'CY'
            if dict['fileId'].__contains__('/'):
                dict['sfi'] = dict['fileId'][-2:]
                dict['fileId'] = dict['fileId'][:-3]

        # get access conditions for DFs
        for i in range(1, len(accDFRows)):
            dataRow = accDFRows[i]
            idCell = dataRow.getElementsByTagName('Cell')[0]
            idData = idCell.getElementsByTagName('Data')[0].childNodes[0].data
            # Delete File (Child)
            accDeleteChildCell = dataRow.getElementsByTagName('Cell')[7]
            if accDeleteChildCell.getElementsByTagName('Data')[0].hasChildNodes():
                accDeleteChildData = self._translateAcc(accDeleteChildCell.getElementsByTagName('Data')[0].childNodes[0].data)
            else:
                accDeleteChildData = ''
            # Delete File (Self)
            accDeleteSelfCell = dataRow.getElementsByTagName('Cell')[8]
            if accDeleteSelfCell.getElementsByTagName('Data')[0].hasChildNodes():
                accDeleteSelfData = self._translateAcc(accDeleteSelfCell.getElementsByTagName('Data')[0].childNodes[0].data)
            else:
                accDeleteSelfData = ''
            # Create File (EF)
            accCreateEFCell = dataRow.getElementsByTagName('Cell')[9]
            if accCreateEFCell.getElementsByTagName('Data')[0].hasChildNodes():
                accCreateEFData = self._translateAcc(accCreateEFCell.getElementsByTagName('Data')[0].childNodes[0].data)
            else:
                accCreateEFData = ''
            # Create File (DF)
            accCreateDFCell = dataRow.getElementsByTagName('Cell')[10]
            if accCreateDFCell.getElementsByTagName('Data')[0].hasChildNodes():
                accCreateDFData = self._translateAcc(accCreateDFCell.getElementsByTagName('Data')[0].childNodes[0].data)
            else:
                accCreateDFData = ''
            # Deactivate
            accDeactivateCell = dataRow.getElementsByTagName('Cell')[11]
            if accDeactivateCell.getElementsByTagName('Data')[0].hasChildNodes():
                accDeactivateData = self._translateAcc(accDeactivateCell.getElementsByTagName('Data')[0].childNodes[0].data)
            else:
                accDeactivateData = ''
            # Activate
            accActivateCell = dataRow.getElementsByTagName('Cell')[12]
            if accActivateCell.getElementsByTagName('Data')[0].hasChildNodes():
                accActivateData = self._translateAcc(accActivateCell.getElementsByTagName('Data')[0].childNodes[0].data)
            else:
                accActivateData = ''

            for dict in filesInCard:
                if dict['fileId'][-4:] == str(idData):
                    dict['accDeleteChild'] = str(accDeleteChildData)
                    dict['accDeleteSelf'] = str(accDeleteSelfData)
                    dict['accCreateEF'] = str(accCreateEFData)
                    dict['accCreateDF'] = str(accCreateDFData)
                    dict['accDeactivate'] = str(accDeactivateData)
                    dict['accActivate'] = str(accActivateData)

        # print(filesInCard) # debug

        # get access conditions for EFs
        for i in range(1, len(accEFRows)):
            skipForDf = False
            dataRow = accEFRows[i]
            idCell = dataRow.getElementsByTagName('Cell')[0]
            dfCell = dataRow.getElementsByTagName('Cell')[1]
            idData = idCell.getElementsByTagName('Data')[0].childNodes[0].data
            try:
                dfData = dfCell.getElementsByTagName('Data')[0].childNodes[0].data
                dfPath = dfData.replace('/', '')
                id_df = dfPath[-4:]
            except IndexError:
                skipForDf = True
            isDF = False
            for df in definedDF:
                if str(idData) == df[-4:]:
                    isDF = True
                    break
            if not isDF:
                # Read Search
                accReadCell = dataRow.getElementsByTagName('Cell')[12]
                if accReadCell.getElementsByTagName('Data')[0].hasChildNodes():
                    accReadData = self._translateAcc(accReadCell.getElementsByTagName('Data')[0].childNodes[0].data)
                else:
                    accReadData = ''
                # Update
                accUpdateCell = dataRow.getElementsByTagName('Cell')[13]
                if accUpdateCell.getElementsByTagName('Data')[0].hasChildNodes():
                    accUpdateData = self._translateAcc(accUpdateCell.getElementsByTagName('Data')[0].childNodes[0].data)
                else:
                    accUpdateData = ''
                # Deactivate File
                accDeactivateFileCell = dataRow.getElementsByTagName('Cell')[15]
                if accDeactivateFileCell.getElementsByTagName('Data')[0].hasChildNodes():
                    accDeactivateFileData = self._translateAcc(accDeactivateFileCell.getElementsByTagName('Data')[0].childNodes[0].data)
                else:
                    accDeactivateFileData = ''
                # Activate File
                accActivateFileCell = dataRow.getElementsByTagName('Cell')[16]
                if accActivateFileCell.getElementsByTagName('Data')[0].hasChildNodes():
                    accActivateFileData = self._translateAcc(accActivateFileCell.getElementsByTagName('Data')[0].childNodes[0].data)
                else:
                    accActivateFileData = ''
                # Delete File
                accDeleteFileCell = dataRow.getElementsByTagName('Cell')[17]
                if accDeleteFileCell.getElementsByTagName('Data')[0].hasChildNodes():
                    accDeleteFileData = self._translateAcc(accDeleteFileCell.getElementsByTagName('Data')[0].childNodes[0].data)
                else:
                    accDeleteFileData = ''
                # Increase
                accIncreaseCell = dataRow.getElementsByTagName('Cell')[18]
                if accIncreaseCell.getElementsByTagName('Data')[0].hasChildNodes():
                    accIncreaseData = self._translateAcc(accIncreaseCell.getElementsByTagName('Data')[0].childNodes[0].data)
                else:
                    accIncreaseData = ''
                # Resize
                accResizeCell = dataRow.getElementsByTagName('Cell')[19]
                if accResizeCell.getElementsByTagName('Data')[0].hasChildNodes():
                    accResizeData = self._translateAcc(accResizeCell.getElementsByTagName('Data')[0].childNodes[0].data)
                else:
                    accResizeData = ''

                for dict in filesInCard:
                    # if dict['fileId'][-4:] == str(idData)[:4]:
                    if not skipForDf:
                        if dict['fileId'][-8:] == (id_df + str(idData)[:4]):
                            self._print_log('debug file -- ' + dict['fileId'] + ': ' + dict['fileName'])
                            dict['accRead'] = str(accReadData)
                            dict['accUpdate'] = str(accUpdateData)
                            dict['accDeactivate'] = str(accDeactivateFileData)
                            dict['accActivate'] = str(accActivateFileData)
                            dict['accDeleteSelf'] = str(accDeleteFileData)
                            dict['accIncrease'] = str(accIncreaseData)
                            dict['accResize'] = str(accResizeData)

        # print(filesInCard) # debug

        # get shared data / linked files
        if sharedDataExist:
            skipNextRow = False
            self._print_log('\nshared data:')
            self._print_log('%-40s%-20s%s' % ('name', 'link', 'target'))
            for i in range(2, len(sharedDataRows)):
                if skipNextRow:
                    skipNextRow = False
                    continue
                else:
                    dataRow = sharedDataRows[i]
                    sdName = dataRow.getElementsByTagName('Cell')[0].getElementsByTagName('Data')[0].childNodes[0].data
                    sdPath = dataRow.getElementsByTagName('Cell')[2].getElementsByTagName('Data')[0].childNodes[0].data
                    nextSdName = sharedDataRows[i+1].getElementsByTagName('Cell')[0].getElementsByTagName('Data')[0].childNodes[0].data
                    if nextSdName == sdName:
                        nextSdPath = sharedDataRows[i+1].getElementsByTagName('Cell')[2].getElementsByTagName('Data')[0].childNodes[0].data
                        nextSdPath = self._filterHex(nextSdPath)
                        if nextSdPath[:4] != '3F00':
                            nextSdPath = '3F00' + nextSdPath
                        sdPath = self._filterHex(sdPath)
                        if sdPath[:4] != '3F00':
                            sdPath = '3F00' + sdPath
                        sdLink = sdPath
                        sdTarget = nextSdPath
                        self._print_log('%-40s%-20s%s' % (sdName, sdLink, sdTarget))
                        # update filesInCard
                        for dict in filesInCard:
                            if dict['fileId'] == sdLink:
                                dict['type'] = 'Link'
                                if dict.has_key('recNb'):
                                    del dict['recNb']
                                if dict.has_key('recSize'):
                                    del dict['recSize']
                                if dict.has_key('fileSize'):
                                    del dict['fileSize']
                                if dict.has_key('content'):
                                    del dict['content']
                                dict['linkto'] = str(sdTarget)
                    else:
                        continue

                    skipNextRow = True

        for dict in filesInCard:
            if dict.has_key('content'):
                if dict['type'] == 'LF' or dict['type'] == 'CY':
                    dict['content'] = self._fixContent(dict['content'])
                if dict['type'] == 'TR':
                    if dict['content'][0].__contains__('['):
                        dict['content'][0] = 'FF'
                    else:
                        dict['content'][0] = self._fixData(dict['content'][0])

        if OPT_DEBUG:
            self._print_log('')
            self._print_log(filesInCard)

        if OPT_VERBOSE:
            self._print_log('\n%s file objects in list:' % (str(len(filesInCard))))
            for dict in filesInCard:
                # print(dict) # debug
                self._print_log('\nfileId: ' + dict['fileId'])
                self._print_log('fileName: ' + dict['fileName'])
                self._print_log('type: ' + dict['type'])
                if dict['type'] == 'Link':
                    self._print_log('linkto: ' + dict['linkto'])
                if dict['type'] != 'Link':
                    if dict['type'] == 'LF' or dict['type'] == 'CY':
                        self._print_log('recNb: ' + dict['recNb'])
                        self._print_log('recSize: ' + dict['recSize'])
                    if dict['type'] != 'MF':
                        if dict['type'] != 'DF':
                            self._print_log('fileSize: ' + dict['fileSize'])
                        else:
                            pass

                if dict.has_key('sfi'):
                    self._print_log('sfi: ' + dict['sfi'])
                self._print_log('accActivate: ' + dict['accActivate'])
                self._print_log('accDeactivate: ' + dict['accDeactivate'])
                self._print_log('accDeleteSelf: ' + dict['accDeleteSelf'])
                if dict['type'] == 'MF' or dict['type'] == 'DF':
                    self._print_log('accCreateDF: ' + dict['accCreateDF'])
                    self._print_log('accCreateEF: ' + dict['accCreateEF'])
                    self._print_log('accDeleteChild: ' + dict['accDeleteChild'])
                else:
                    self._print_log('accRead: ' + dict['accRead'])
                    self._print_log('accUpdate: ' + dict['accUpdate'])
                    self._print_log('accIncrease: ' + dict['accIncrease'])
                    self._print_log('accResize: ' + dict['accResize'])
                if dict.has_key('content'):
                    self._print_log('content:')
                    if dict['type'] == 'TR':
                        if dict['content'][0]:
                            self._print_log(dict['content'][0])
                        else:
                            self._print_log('(valuated)')
                    if dict['type'] == 'LF' or dict['type'] == 'CY':
                        recNum = 1
                        for c in dict['content']:
                            if c:
                                self._print_log('%-6s%s' % (recNum, c))
                            else:
                                self._print_log('%-6s%s' % (recNum, '(valuated)'))
                            recNum += 1

        # create buffer for csv
        csv_buffer = []  # contains lines/rows of data

        # csv indexes
        fiFileName = 0
        fiFilePath = 1
        fiFileID = 2
        fiFileType = 3
        fiSFI = 4
        fiFileRecordSize = 5
        fiNumberOfRecord = 6
        fiFileSize = 7

        fiRead_ACC = 8
        fiUpdate_ACC = 9
        fiInvalidate_ACC = 10
        fiRehabilitate_ACC = 11
        fiDeleteSelf_ACC = 12
        fiIncrease_ACC = 13
        fiResize3G_ACC = 14
        # exclusive to DF/ADF
        fiDeleteChild_ACC = 15
        fiCreateEF_ACC = 16
        fiCreateDF_ACC = 17
        fiDeactivate_ACC = 18
        fiActivate_ACC = 19

        fiLinkTo = 20
        fiRecordNumber = 21
        fiContent = 22

        # build csv header
        csv_header = []
        csv_header.append('FileName')           # 0
        csv_header.append('FilePath')           # 1
        csv_header.append('FileID')             # 2
        csv_header.append('FileType')           # 3
        csv_header.append('SFI')                # 4
        csv_header.append('FileRecordSize')     # 5
        csv_header.append('NumberOfRecord')     # 6
        csv_header.append('FileSize')           # 7

        csv_header.append('Read_ACC')           # 8
        csv_header.append('Update_ACC')         # 9
        csv_header.append('Invalidate_ACC')     # 10
        csv_header.append('Rehabilitate_ACC')   # 11
        csv_header.append('DeleteSelf_ACC')     # 12
        csv_header.append('Increase_ACC')       # 13
        csv_header.append('Resize_ACC')         # 14
        csv_header.append('DeleteChild_ACC')    # 15
        csv_header.append('CreateEF_ACC')       # 16
        csv_header.append('CreateDF_ACC')       # 17
        csv_header.append('Deactivate_ACC')     # 18
        csv_header.append('Activate_ACC')       # 19

        csv_header.append('LinkTo')             # 20
        csv_header.append('RecordNumber')       # 21
        csv_header.append('Content')            # 22

        # add header to csv
        csv_buffer.append(csv_header)

        # start filling rows with values
        for dict in filesInCard:
            field_list = []
            # initiate row with empty string
            for i in range(23):
                field_list.append('')

            next_record = False

            # getting values from dictionaries
            field_list[fiFileName] = dict['fileName']
            field_list[fiFilePath] = dict['fileId'][:-4]
            field_list[fiFileID] = dict['fileId'][-4:]
            field_list[fiFileType] = dict['type']
            if dict.has_key('sfi'):
                field_list[fiSFI] = dict['sfi']
            if dict.has_key('recSize'):
                if dict['recSize'] != '0':
                    field_list[fiFileRecordSize] = dict['recSize']
            if dict.has_key('recNb'):
                if dict['recNb'] != '0':
                    field_list[fiNumberOfRecord] = dict['recNb']
            if dict.has_key('fileSize'):
                field_list[fiFileSize] = dict['fileSize']

            if not dict['type'] == 'MF':
                if not dict['type'] == 'DF':
                    field_list[fiRead_ACC] = dict['accRead']
                    field_list[fiUpdate_ACC] = dict['accUpdate']
                    field_list[fiInvalidate_ACC] = dict['accDeactivate']
                    field_list[fiRehabilitate_ACC] = dict['accActivate']
                    field_list[fiDeleteSelf_ACC] = dict['accDeleteSelf']
                    field_list[fiIncrease_ACC] = dict['accIncrease']
                    field_list[fiResize3G_ACC] = dict['accResize']
            if dict['type'] == 'MF' or dict['type'] == 'DF':
                field_list[fiDeleteChild_ACC] = dict['accDeleteChild']
                field_list[fiDeleteSelf_ACC] = dict['accDeleteSelf']
                field_list[fiCreateEF_ACC] = dict['accCreateEF']
                field_list[fiCreateDF_ACC] = dict['accCreateDF']
                field_list[fiDeactivate_ACC] = dict['accDeactivate']
                field_list[fiActivate_ACC] = dict['accActivate']

            if dict['type'] == 'Link':
                field_list[fiLinkTo] = dict['linkto']

            # EF content
            if not dict['type'] == 'Link':
                if dict['type'] != 'MF' or dict['type'] != 'DF':
                    if dict['type'] == 'TR':
                        field_list[fiContent] = dict['content'][0]
                    if dict['type'] == 'LF' or dict['type'] == 'CY':
                        next_record = True
                        field_list[fiRecordNumber] = str(1)
                        field_list[fiContent] = dict['content'][0] # first record
                        csv_buffer.append(field_list)
                        # add next record(s)
                        for i in range(1, len(dict['content'])):
                            field_list_tmp = []
                            for k in range(23):
                                field_list_tmp.append('')
                            field_list_tmp[fiRecordNumber] = str(i + 1)
                            field_list_tmp[fiContent] = dict['content'][i]
                            csv_buffer.append(field_list_tmp)
            
            # add row to csv
            if not next_record:
                csv_buffer.append(field_list)

            # write to file
            csv_file = open(self._csvFileName, 'w')
            for row in csv_buffer:
                line = ''
                for col in row:
                    line += col + ','  # comma as field separator
                csv_file.writelines(line + '\n')

            csv_file.flush()
            csv_file.close()

        # write converter log
        converter_log_file = open('converter.log', 'w')
        for row in self._converter_log_buffer:
            converter_log_file.writelines(row + '\n')
    
        del self._converter_log_buffer[:] # empty log buffer

        converter_log_file.flush()
        converter_log_file.close()

def runAsModule(docPath):
    global run_as_module
    run_as_module = True

    logger.info('source: %s' % (docPath))
    baseFilePath = docPath[:-4]
    destinationPath = baseFilePath + '.csv'
    try:
        converter = MorphoDocParser(docPath, destinationPath)
        converter.proceed()
        logger.info('destination: %s' % (destinationPath))
        return True, 'ex-Morpho doc converted successfully', destinationPath
    except Exception, e:
        logger.error(str(e))
        return False, 'ERROR: %s' % (str(e)), ''

# main program
if __name__ == '__main__':
    converter = MorphoDocParser(docName, csvName)
    converter.proceed()