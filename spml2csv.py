'''
Converts SIMPML standard costumer specification document into CSV as input for BOTS verification tool.
Author: Martyono Sembodo
Last update: 15.07.2018
Description: 
* updated as some .uxp of eUICC profiles does not have 2G access condition
* modified to be executed as verif module
'''

from __future__ import print_function
from xml.dom.minidom import parse
import sys
import logging

logging.basicConfig(level=logging.INFO,
                    format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
                    datefmt="%H:%M:%S", stream=sys.stdout)

logger = logging.getLogger(__name__)

# input - output
uxp = 'O2_128.24_LTE_24_OTA_PostPay_4.uxp'
csv = 'O2_128.24_LTE_24_OTA_PostPay_4.csv'

run_as_module = False

class SIMPMLParser:
    file_name = ''
    csv_filename = ''

    converter_log_buffer = []
    
    # constants
    ERR_WARNING = 10
    ERR_ERROR = 11
    ERR_FATAL = 12
    
    def __init__(self, uxp, csv):
        self.file_name = uxp
        self.csv_filename = csv
    
    def print_err(self, err_obj, err_msg, severity):
        if severity == self.ERR_WARNING:
            self.print_log('WARNING >>> ' + err_obj + ': ' + err_msg)
        if severity == self.ERR_ERROR:
            self.print_log('ERROR >>> ' + err_obj + ': ' + err_msg)
        if severity == self.ERR_FATAL:
            self.print_log('FATAL >>> ' + err_obj + ': ' + err_msg)   
    
    def formatFileId(self, fileId):
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
    
    def getMultipleACC(self, acc_3g, acc_str):
        acc_all = acc_3g.getElementsByTagName(acc_str)
        if len(acc_all) > 1:
            operator = ''
            for acc in acc_all:
                if acc.hasAttribute('Operator'):
                    operator = acc.getAttribute('Operator')
            acc_result = '%s %s %s' % (acc_all[0].childNodes[0].data, operator, acc_all[1].childNodes[0].data)
        else:
            acc_result = acc_3g.getElementsByTagName(acc_str)[0].childNodes[0].data
        return acc_result
    
    def print_log(self, log_message):
        if run_as_module:
            self.converter_log_buffer.append(log_message)
        else:
            print(log_message)

    def proceed(self):
        # switches
        OPT_VERBOSE = 1 # print each file with details
        OPT_MULTIPLE_ACC_SUPPORT = 1
        
        # Open XML document using minidom parser
        # try:
        DOMTree = parse(self.file_name)
        # except IOError:
            # self.print_err(self.file_name, 'Error opening/reading file', self.ERR_FATAL)
            # sys.exit(1)
        
        cardProfile = DOMTree.documentElement
        
        # document info
        if cardProfile.hasAttribute('xmlns'):
            self.print_log("Document scheme -- %s" % cardProfile.getAttribute('xmlns'))
        
        customerInfo = cardProfile.getElementsByTagName('Header')[0].getElementsByTagName('SIMCardProfileReference')[0]
        customerName = customerInfo.getElementsByTagName('Issuer')[0].childNodes[0].data
        profileName = customerInfo.getElementsByTagName('ProfileName')[0].childNodes[0].data
        self.print_log("Issuer : %s" % customerName)
        self.print_log("Profile: %s" % profileName)
        
        # card file system
        cardBody = cardProfile.getElementsByTagName('CardBody')[0]
        mf = '3F00'
        
        # indexes of columns
        fiFileName = 0
        fiFilePath = 1
        fiFileID = 2
        fiFileType = 3
        fiSFI = 4 # optional
        fiFileRecordSize = 5
        fiNumberOfRecord = 6
        fiFileSize = 7
        
        fiRead_ACC = 8
        fiUpdate_ACC = 9
        fiIncrease_ACC = 10 # optional
        # fiResize_ACC = 11 # skipped because MCC does not define 'resize' for 2G
        fiRehabilitate_ACC = 11
        fiInvalidate_ACC = 12
        fiRead3G_ACC = 13
        fiUpdate3G_ACC = 14
        fiIncrease3G_ACC = 15 # optional
        fiResize3G_ACC = 16
        fiActivate_ACC = 17
        fiDeactivate_ACC = 18
        fiDeleteSelf_ACC = 19
        # exclusive to DF/ADF
        fiCreate_ACC = 20
        fiDelete_ACC = 21
        fiTerminateDF_ACC = 22
        fiCreateDF_ACC = 23
        fiCreateEF_ACC = 24
        fiDeleteChild_ACC = 25
        
        fiLinkTo = 26
        fiRecordNumber = 27
        fiContent = 28
        
        fiShareable = 29 # optional
        
        csv_buffer = [] # contains lines/rows of data
        
        # build csv header
        csv_header = []                         # index       
        csv_header.append('FileName')           # 0
        csv_header.append('FilePath')           # 1
        csv_header.append('FileID')             # 2
        csv_header.append('FileType')           # 3
        csv_header.append('SFI')                # 4
        csv_header.append('FileRecordSize')     # 5
        csv_header.append('NumberOfRecord')     # 6
        csv_header.append('FileSize')           # 7
        
        # 2G access conditions
        csv_header.append('Read_ACC')           # 8
        csv_header.append('Update_ACC')         # 9
        csv_header.append('Increase_ACC')       # 10 (optional)
        csv_header.append('Rehabilitate_ACC')   # 11
        csv_header.append('Invalidate_ACC')     # 12
        
        # 3G access conditions
        csv_header.append('Read3G_ACC')         # 13
        csv_header.append('Update3G_ACC')       # 14
        csv_header.append('Increase3G_ACC')     # 15 (optional)
        csv_header.append('Resize_ACC')         # 16
        csv_header.append('Activate_ACC')       # 17 (also applies to DF/ADF)
        csv_header.append('Deactivate_ACC')     # 18 (also applies to DF/ADF)
        csv_header.append('DeleteSelf_ACC')     # 19 (also applies to DF/ADF)
        # exclusive to DF/ADF
        csv_header.append('Dummy')              # 20 ('Create_ACC' not evaluated)
        csv_header.append('Dummy')              # 21 ('Delete_ACC' not evaluated)
        csv_header.append('Terminate_ACC')      # 22
        csv_header.append('CreateDF_ACC')       # 23
        csv_header.append('CreateEF_ACC')       # 24
        csv_header.append('DeleteChild_ACC')    # 25
        
        csv_header.append('LinkTo')             # 26
        csv_header.append('RecordNumber')       # 27
        csv_header.append('Content')            # 28
        # csv_header.append('Shareable')          # 29 (optional)
        
        # add header to csv
        csv_buffer.append(csv_header)
        
        # start filling rows with values
        
        # DF
        self.print_log('\nList of DF/ADF in card:\n')
        df_list = cardBody.getElementsByTagName('MF_DF')
        for df in df_list:
            field_list = []
            # initiate list with empty string
            for i in range(29):
                field_list.append('')
            
            # getting values from document
            file_name = df.getAttribute('FileName')
            
            if df.getAttribute('FilePath')[:4] != mf:
                abs_path = mf + df.getAttribute('FilePath')
            else:
                abs_path = df.getAttribute('FilePath')
            
            if df.getAttribute('FileType') == 'MF':
                file_path = ''
            else:
                file_path = abs_path[:len(abs_path)-4]
            
            df_id = df.getAttribute('FileID')
            file_type = df.getAttribute('FileType')
            
            field_list[fiFileName] = file_name
            field_list[fiFilePath] = file_path
            field_list[fiFileID] = df_id
            field_list[fiFileType] = file_type
            
            if df.getElementsByTagName('AccessConditions2G'):
                acc_2g = df.getElementsByTagName('AccessConditions2G')[0]
                acc_2g_not_defined = False
                if len(acc_2g.childNodes) > 0:
                    df_acc_2g = acc_2g.getElementsByTagName('DFAccessConditions2GType')[0]
                    # 2G's create & delete will not be processed by the verification script anyway
                    pass
                else:
                    acc_2g_not_defined = True
            else:
                acc_2g_not_defined = True
            
            acc_3g = df.getElementsByTagName('AccessConditions3G')[0]
            acc_3g_not_defined = False
            if len(acc_3g.childNodes) > 0:
                df_acc_3g = acc_3g.getElementsByTagName('DFAccessConditions3GType')[0]
                if OPT_MULTIPLE_ACC_SUPPORT:
                    acc_delete_self = self.getMultipleACC(df_acc_3g, 'DeleteSelf')
                    acc_terminate = self.getMultipleACC(df_acc_3g, 'TerminateDF')
                    acc_activate = self.getMultipleACC(df_acc_3g, 'Activate')
                    acc_deactivate = self.getMultipleACC(df_acc_3g, 'Deactivate')
                    acc_create_df = self.getMultipleACC(df_acc_3g, 'CreateChildDF')
                    acc_create_ef = self.getMultipleACC(df_acc_3g, 'CreateChildEF')
                    acc_delete_child = self.getMultipleACC(df_acc_3g, 'DeleteChild')
                else:
                    acc_delete_self = df_acc_3g.getElementsByTagName('DeleteSelf')[0].childNodes[0].data
                    acc_terminate = df_acc_3g.getElementsByTagName('TerminateDF')[0].childNodes[0].data
                    acc_activate = df_acc_3g.getElementsByTagName('Activate')[0].childNodes[0].data
                    acc_deactivate = df_acc_3g.getElementsByTagName('Deactivate')[0].childNodes[0].data
                    acc_create_df = df_acc_3g.getElementsByTagName('CreateChildDF')[0].childNodes[0].data
                    acc_create_ef = df_acc_3g.getElementsByTagName('CreateChildEF')[0].childNodes[0].data
                    acc_delete_child = df_acc_3g.getElementsByTagName('DeleteChild')[0].childNodes[0].data
                
                field_list[fiDeleteSelf_ACC] = acc_delete_self
                field_list[fiTerminateDF_ACC] = acc_terminate
                field_list[fiActivate_ACC] = acc_activate
                field_list[fiDeactivate_ACC] = acc_deactivate
                field_list[fiCreateDF_ACC] = acc_create_df
                field_list[fiCreateEF_ACC] = acc_create_ef
                field_list[fiDeleteChild_ACC] = acc_delete_child
            else:
                acc_3g_not_defined = True
            
            self.print_log(self.formatFileId(file_path + df_id) + ': ' + file_name)
            if OPT_VERBOSE:
                if df.getAttribute('FileDescription'):
                    self.print_log('FileDescription: ' + df.getAttribute('FileDescription'))
                self.print_log('FileType: ' + file_type)
                if acc_2g_not_defined:
                    self.print_err(file_path + df_id, '2G ACC not defined', self.ERR_WARNING)
                else:
                    self.print_log('Create: ' + df_acc_2g.getElementsByTagName('Create')[0].childNodes[0].data)
                    self.print_log('Delete: ' + df_acc_2g.getElementsByTagName('Delete')[0].childNodes[0].data)
                    
                if acc_3g_not_defined:
                    self.print_err(file_path + df_id, '3G ACC not defined', self.ERR_WARNING)
                else:
                    self.print_log('DeleteSelf: ' + acc_delete_self)
                    self.print_log('TerminateDF: ' + acc_terminate)
                    self.print_log('Activate: ' + acc_activate)
                    self.print_log('Deactivate: ' + acc_deactivate)
                    self.print_log('CreateChildDF: ' + acc_create_df)
                    self.print_log('CreateChildEF: ' + acc_create_ef)
                    self.print_log('DeleteChild: ' + acc_delete_child)
                
                self.print_log('')
            
            # add row to csv
            csv_buffer.append(field_list)
        
        # ADF
        adf_list = cardBody.getElementsByTagName('ADF')
        for adf in adf_list:
            field_list = []
            # initiate list with empty string
            for i in range(29):
                field_list.append('')
            
            # getting values from document
            file_name = adf.getAttribute('FileName')
            abs_path = mf + adf.getAttribute('FilePath')
            file_path = abs_path[:len(abs_path)-4]
            adf_id = adf.getAttribute('FileID')
            file_type = 'DF'
            
            field_list[fiFileName] = file_name
            field_list[fiFilePath] = file_path
            field_list[fiFileID] = adf_id
            field_list[fiFileType] = file_type
            
            if adf.getElementsByTagName('AccessConditions2G'):
                acc_2g = adf.getElementsByTagName('AccessConditions2G')[0]
                acc_2g_not_defined = False
                if len(acc_2g.childNodes) > 0:
                    adf_acc_2g = acc_2g.getElementsByTagName('DFAccessConditions2GType')[0]
                    # 2G's create & delete will not be processed by the verification script anyway
                    pass
                else:
                    acc_2g_not_defined = True
            else:
                acc_2g_not_defined = True
            
            acc_3g = adf.getElementsByTagName('AccessConditions3G')[0]
            acc_3g_not_defined = False
            if len(acc_3g.childNodes) > 0:
                adf_acc_3g = acc_3g.getElementsByTagName('DFAccessConditions3GType')[0]
                if OPT_MULTIPLE_ACC_SUPPORT:
                    acc_delete_self = self.getMultipleACC(adf_acc_3g, 'DeleteSelf')
                    acc_terminate = self.getMultipleACC(adf_acc_3g, 'TerminateDF')
                    acc_activate = self.getMultipleACC(adf_acc_3g, 'Activate')
                    acc_deactivate = self.getMultipleACC(adf_acc_3g, 'Deactivate')
                    acc_create_df = self.getMultipleACC(adf_acc_3g, 'CreateChildDF')
                    acc_create_ef = self.getMultipleACC(adf_acc_3g, 'CreateChildEF')
                    acc_delete_child = self.getMultipleACC(adf_acc_3g, 'DeleteChild')
                else:
                    acc_delete_self = adf_acc_3g.getElementsByTagName('DeleteSelf')[0].childNodes[0].data
                    acc_terminate = adf_acc_3g.getElementsByTagName('TerminateDF')[0].childNodes[0].data
                    acc_activate = adf_acc_3g.getElementsByTagName('Activate')[0].childNodes[0].data
                    acc_deactivate = adf_acc_3g.getElementsByTagName('Deactivate')[0].childNodes[0].data
                    acc_create_df = adf_acc_3g.getElementsByTagName('CreateChildDF')[0].childNodes[0].data
                    acc_create_ef = adf_acc_3g.getElementsByTagName('CreateChildEF')[0].childNodes[0].data
                    acc_delete_child = adf_acc_3g.getElementsByTagName('DeleteChild')[0].childNodes[0].data
                
                field_list[fiDeleteSelf_ACC] = acc_delete_self
                field_list[fiTerminateDF_ACC] = acc_terminate
                field_list[fiActivate_ACC] = acc_activate
                field_list[fiDeactivate_ACC] = acc_deactivate
                field_list[fiCreateDF_ACC] = acc_create_df
                field_list[fiCreateEF_ACC] = acc_create_ef
                field_list[fiDeleteChild_ACC] = acc_delete_child
            else:
                acc_3g_not_defined = True
            
            self.print_log(self.formatFileId(file_path + adf_id) + ': ' + file_name)
            if OPT_VERBOSE:
                if adf.getAttribute('FileDescription'):
                    self.print_log('FileDescription: ' + adf.getAttribute('FileDescription'))
                self.print_log('FileType: ' + file_type)
                
                if acc_2g_not_defined:
                    self.print_err(file_path + adf_id, '2G ACC not defined', self.ERR_WARNING)
                else:
                    self.print_log('Create: ' + adf_acc_2g.getElementsByTagName('Create')[0].childNodes[0].data)
                    self.print_log('Delete: ' + adf_acc_2g.getElementsByTagName('Delete')[0].childNodes[0].data)
                    
                if acc_3g_not_defined:
                    self.print_err(file_path + adf_id, '3G ACC not defined', self.ERR_WARNING)
                else:
                    self.print_log('DeleteSelf: ' + acc_delete_self)
                    self.print_log('TerminateDF: ' + acc_terminate)
                    self.print_log('Activate: ' + acc_activate)
                    self.print_log('Deactivate: ' + acc_deactivate)
                    self.print_log('CreateChildDF: ' + acc_create_df)
                    self.print_log('CreateChildEF: ' + acc_create_ef)
                    self.print_log('DeleteChild: ' + acc_delete_child)
                
                self.print_log('')
            
            # add row to csv
            csv_buffer.append(field_list)
        
        # EF
        self.print_log('\nList of EF in card:\n')
        ef_list = cardBody.getElementsByTagName('EF')
        for ef in ef_list:
            field_list = []
            # initiate list with empty string
            for i in range(29):
                field_list.append('')
            
            next_record = False
            
            # getting values from document
            file_name = ef.getAttribute('FileName')
            
            if ef.getAttribute('FilePath')[:4] != mf:
                abs_path = mf + ef.getAttribute('FilePath')
            else:
                abs_path = ef.getAttribute('FilePath')
            
            file_path = abs_path[:len(abs_path)-4]
            ef_id = ef.getAttribute('FileID')
            file_type = ef.getAttribute('FileType')
            
            field_list[fiFileName] = file_name
            field_list[fiFilePath] = file_path
            field_list[fiFileID] = ef_id
            field_list[fiFileType] = file_type
            
            if file_type == 'Link':
                if ef.getAttribute('LinkFilePath')[:4] != mf:
                    link_to = mf + ef.getAttribute('LinkFilePath')
                else:
                    link_to = ef.getAttribute('LinkFilePath')
                field_list[fiLinkTo] = link_to
            
            if ef.hasAttribute('SFI'):
                sfi = ef.getAttribute('SFI')
                field_list[fiSFI] = sfi
            else:
                sfi = ''
            
            if ef.getElementsByTagName('AccessConditions2G'):
                acc_2g = ef.getElementsByTagName('AccessConditions2G')[0]
                acc_2g_not_defined = False
                if len(acc_2g.childNodes) > 0:
                    ef_acc_2g = acc_2g.getElementsByTagName('EFAccessConditions2GType')[0]
                    acc_read = ef_acc_2g.getElementsByTagName('Read')[0].childNodes[0].data
                    acc_update = ef_acc_2g.getElementsByTagName('Update')[0].childNodes[0].data
                    # 'increase' is optional
                    hasIncrease2g = False
                    for node in ef_acc_2g.childNodes:
                        if node.nodeType == 1:
                            if node.nodeName == 'Increase':
                                hasIncrease2g = True
                                break
                    if hasIncrease2g:
                        acc_increase = ef_acc_2g.getElementsByTagName('Increase')[0].childNodes[0].data
                    #acc_resize = ef_acc_2g.getElementsByTagName('Resize')[0].childNodes[0].data
                    acc_rehabilitate = ef_acc_2g.getElementsByTagName('Rehabilitate')[0].childNodes[0].data
                    acc_invalidate = ef_acc_2g.getElementsByTagName('Invalidate')[0].childNodes[0].data
                    
                    field_list[fiRead_ACC] = acc_read
                    field_list[fiUpdate_ACC] = acc_update
                    if hasIncrease2g:
                        field_list[fiIncrease_ACC] = acc_increase
                    field_list[fiRehabilitate_ACC] = acc_rehabilitate
                    field_list[fiInvalidate_ACC] = acc_invalidate
                else:
                    acc_2g_not_defined = True
            else:
                acc_2g_not_defined = True
            
            acc_3g = ef.getElementsByTagName('AccessConditions3G')[0]
            acc_3g_not_defined = False
            if len(acc_3g.childNodes) > 0:
                ef_acc_3g = acc_3g.getElementsByTagName('EFAccessConditions3GType')[0]
                if OPT_MULTIPLE_ACC_SUPPORT:
                    acc_read3g = self.getMultipleACC(ef_acc_3g, 'Read')
                    acc_update3g = self.getMultipleACC(ef_acc_3g, 'Update')
                    # 'increase' is optional
                    hasIncrease3g = False
                    for node in ef_acc_3g.childNodes:
                        if node.nodeType == 1:
                            if node.nodeName == 'Increase':
                                hasIncrease3g = True
                                break
                    if hasIncrease3g:
                        acc_increase3g = self.getMultipleACC(ef_acc_3g, 'Increase')
                    acc_resize = self.getMultipleACC(ef_acc_3g, 'Resize')
                    acc_activate = self.getMultipleACC(ef_acc_3g, 'Activate')
                    acc_deactivate = self.getMultipleACC(ef_acc_3g, 'Deactivate')
                    acc_delete_self = self.getMultipleACC(ef_acc_3g, 'DeleteItself')
                else:
                    acc_read3g = ef_acc_3g.getElementsByTagName('Read')[0].childNodes[0].data
                    acc_update3g = ef_acc_3g.getElementsByTagName('Update')[0].childNodes[0].data
                    # 'increase' is optional
                    hasIncrease3g = False
                    for node in ef_acc_3g.childNodes:
                        if node.nodeType == 1:
                            if node.nodeName == 'Increase':
                                hasIncrease3g = True
                                break
                    if hasIncrease3g:
                        acc_increase3g = ef_acc_3g.getElementsByTagName('Increase')[0].childNodes[0].data
                    acc_resize = ef_acc_3g.getElementsByTagName('Resize')[0].childNodes[0].data
                    acc_activate = ef_acc_3g.getElementsByTagName('Activate')[0].childNodes[0].data
                    acc_deactivate = ef_acc_3g.getElementsByTagName('Deactivate')[0].childNodes[0].data
                    acc_delete_self = ef_acc_3g.getElementsByTagName('DeleteItself')[0].childNodes[0].data
                
                field_list[fiRead3G_ACC] = acc_read3g
                field_list[fiUpdate3G_ACC] = acc_update3g
                if hasIncrease3g:
                    field_list[fiIncrease3G_ACC] = acc_increase3g
                field_list[fiResize3G_ACC] = acc_resize
                field_list[fiActivate_ACC] = acc_activate
                field_list[fiDeactivate_ACC] = acc_deactivate
                field_list[fiDeleteSelf_ACC] = acc_delete_self
            else:
                acc_3g_not_defined = True
            
            # EF content
            if file_type != 'Link':
                data_value = ''
                ef_content = ef.getElementsByTagName('EFContent')[0].getElementsByTagName('EFContentType')[0]
                if file_type == 'TR':
                    # transparent EF
                    file_size = ef_content.getAttribute('FileSize')
                    # fill content field only if data is not valuated
                    # if ef_content.getAttribute('DataGenerationType') == 'Static':
                    if ef_content.getAttribute('DataGenerationType') == 'Dynamic':
                        data_value = 'FF'
                    else:   
                        if ef_content.getElementsByTagName('DataValue')[0].childNodes: 
                            data_value = ef_content.getElementsByTagName('DataValue')[0].childNodes[0].data
                        else:
                            data_value = ''
                    number_of_record = ''
                    record_size = ''
                else:
                    # linear fixed / cyclic EF
                    number_of_record = ef_content.getAttribute('NbOfRecords')
                    record_size = ef_content.getAttribute('RecordSize')
                    file_size = str(int(number_of_record) * int(record_size))
                    # fill content field only if data is not valuated
                    # if ef_content.getAttribute('DataGenerationType') == 'Static':
                    data_value_list = ef_content.getElementsByTagName('DataValue')
                    lf_content = []
                    for value in data_value_list:
                        if value.nodeType == 1:
                            if value.nodeName == 'DataValue':
                                if value.childNodes:
                                    lf_content.append(value.childNodes[0].data)
            
                field_list[fiFileSize] = file_size
                field_list[fiNumberOfRecord] = number_of_record
                field_list[fiFileRecordSize] = record_size
                if file_type == 'TR':
                    field_list[fiContent] = data_value
                else:
                    next_record = True
                    field_list[fiRecordNumber] = str(1)
                    if lf_content:
                        field_list[fiContent] = lf_content[0] # first record
                    csv_buffer.append(field_list)
                    # add next record(s)
                    for i in range(1, len(lf_content)):
                        field_list_tmp = []
                        for k in range(29):
                            field_list_tmp.append('')
                        field_list_tmp[fiRecordNumber] = str(i + 1)
                        field_list_tmp[fiContent] = lf_content[i]
                        csv_buffer.append(field_list_tmp)
            else:
                # link will not have content/body
                file_size = ''
                record_size = ''
                number_of_record = ''
            
            self.print_log(self.formatFileId(file_path + ef_id) + ': ' + file_name)
            if OPT_VERBOSE:
                if ef.getAttribute('FileDescription'):
                    self.print_log('FileDescription: ' + ef.getAttribute('FileDescription'))
                if sfi:
                    self.print_log('SFI: ' + sfi)
                self.print_log('FileType: ' + file_type)
                if file_type == 'Link':
                    self.print_log('LinkFilePath: ' + self.formatFileId(link_to))
                if file_size:
                    self.print_log('FileSize: ' + file_size)
                if record_size:
                    self.print_log('RecordSize: ' + record_size)
                if number_of_record:
                    self.print_log('NbOfRecords: ' + number_of_record)
                if acc_2g_not_defined:
                    self.print_err(file_path + ef_id, '2G ACC not defined', self.ERR_WARNING)
                else:
                    self.print_log('Read: ' + acc_read)
                    self.print_log('Update: ' + acc_update)
                    if hasIncrease2g:
                        self.print_log('Increase: ' + acc_increase)
                    self.print_log('Rehabilitate: ' + acc_rehabilitate)
                    self.print_log('Invalidate: ' + acc_invalidate)
                    
                if acc_3g_not_defined:
                    self.print_err(file_path + ef_id, '3G ACC not defined', self.ERR_WARNING)
                else:
                    self.print_log('Read3G: ' + acc_read3g)
                    self.print_log('Update3G: ' + acc_update3g)
                    if hasIncrease3g:
                        self.print_log('Increase3G: ' + acc_increase3g)
                    self.print_log('Resize: ' + acc_resize)
                    self.print_log('Activate: ' + acc_activate)
                    self.print_log('Deactivate: ' + acc_deactivate)
                    self.print_log('DeleteItself: ' + acc_delete_self)
                
                if file_type != 'Link':
                    self.print_log('EFContent:')
                    if file_type == 'TR':
                        self.print_log(data_value)
                    else:
                        rec_num = 1
                        for content in lf_content:
                            self.print_log('rec %-3s: %s' % (rec_num, content))
                            rec_num += 1
                
                self.print_log('')
            
            # add row to csv
            if not next_record:
                csv_buffer.append(field_list)
            
            # clear values
            file_name = ''
            file_path = ''
            ef_id = ''
            file_type = ''
            link_to = ''
            sfi = ''
            number_of_record = ''
            record_size = ''
            file_size = ''
            acc_read = ''
            acc_update = ''
            acc_increase = ''
            acc_rehabilitate = ''
            acc_invalidate = ''
            acc_read3g = ''
            acc_update3g = ''
            acc_increase3g = ''
            acc_resize = ''
            acc_activate = ''
            acc_deactivate = ''
            acc_delete_self = ''
            data_value = ''
            lf_content = []

        # write converter log
        converter_log_file = open('converter.log', 'w')
        for row in self.converter_log_buffer:
            converter_log_file.writelines(row + '\n')
        
        del self.converter_log_buffer[:] # empty log buffer

        converter_log_file.flush()
        converter_log_file.close()

        # write to file
        csv_file = open(self.csv_filename, 'w')
        for row in csv_buffer:
            line = ''
            for col in row:
                line += str(col) + ',' # comma as field separator
            csv_file.writelines(line + '\n')
        
        csv_file.flush()
        csv_file.close()

def runAsModule(docPath):
    global run_as_module
    run_as_module = True

    logger.info('source: %s' % (docPath))
    baseFilePath = docPath[:-4]
    destinationPath = baseFilePath + '.csv'
    try:
        converter = SIMPMLParser(docPath, destinationPath)
        converter.proceed()
        logger.info('destination: %s' % (destinationPath))
        return True, 'UXP converted successfully', destinationPath
    except Exception, e:
        for line in converter.converter_log_buffer:
            print(line)
        logger.error(str(e))
        return False, 'ERROR: %s' % (str(e)), ''

# main program
if __name__ == '__main__':
    converter = SIMPMLParser(uxp, csv)
    converter.proceed()

