# coding: utf-8
#
# This file comes from Impacket & CrackMapExec project
# Slightly modified for Spraykatz.


# Imports
import os, sys, logging, ntpath, time
from core.Utils import *
from impacket.dcerpc.v5.dcomrt import DCOMConnection
from impacket.dcerpc.v5.dcom import wmi
from impacket.dcerpc.v5.dtypes import NULL


class WMIEXEC:
    def __init__(self, target, share_name, username, password, domain, smbconnection, hashes=None, share=None, port="80"):
        self.__target = target
        self.__username = username
        self.__password = password
        self.__domain = domain
        self.__lmhash = ''
        self.__nthash = ''
        self.__share = share
        self.__smbconnection = smbconnection
        self.__output = None
        self.__outputBuffer = ''
        self.__share_name = share_name
        self.__shell = 'cmd.exe /Q /c '
        self.__pwd = 'C:\\'
        self.__aesKey = None
        self.__doKerberos = False
        self.__retOutput = True
        self.__port = port

        if hashes is not None:
            if hashes.find(':') != -1:
                self.__lmhash, self.__nthash = hashes.split(':')
            else:
                self.__nthash = hashes

        if self.__password is None:
            self.__password = ''

        self.__dcom = DCOMConnection(self.__target, self.__username, self.__password, self.__domain, self.__lmhash, self.__nthash, self.__aesKey, oxidResolver = True, doKerberos=self.__doKerberos)
        iInterface = self.__dcom.CoCreateInstanceEx(wmi.CLSID_WbemLevel1Login,wmi.IID_IWbemLevel1Login)
        iWbemLevel1Login = wmi.IWbemLevel1Login(iInterface)
        iWbemServices= iWbemLevel1Login.NTLMLogin('//./root/cimv2', NULL, NULL)
        iWbemLevel1Login.RemRelease()

        self.__win32Process,_ = iWbemServices.GetObject('Win32_Process')


    def execute(self, command, output=False):
        self.__retOutput = output
        if self.__retOutput:
            self.__smbconnection.setTimeout(100000)
        self.execute_handler(command)
        self.__dcom.disconnect()
        return self.__outputBuffer

    def cd(self, s):
        self.execute_remote('cd ' + s)
        if len(self.__outputBuffer.strip('\r\n')) > 0:
            self.__outputBuffer = ''
        else:
            self.__pwd = ntpath.normpath(ntpath.join(self.__pwd, s))
            self.execute_remote('cd ')
            self.__pwd = self.__outputBuffer.strip('\r\n')
            self.__outputBuffer = ''

    def output_callback(self, data):
        self.__outputBuffer += data

    def execute_handler(self, data):
        if self.__retOutput:
            try:
                self.execute_fileless(data)
            except:
                self.cd('\\')
                self.execute_remote(data)
        else:
            self.execute_remote(data)

    def execute_remote(self, data):
        self.__output = '\\Windows\\Temp\\' + gen_random_string(6)
        command = self.__shell + data
        if self.__retOutput:
            command += ' 1> ' + '\\\\127.0.0.1\\%s' % self.__share + self.__output  + ' 2>&1'
        logging.debug('Executing command: ' + command)
        self.__win32Process.Create(command, self.__pwd, None)
        self.get_output_remote()

    def execute_fileless(self, data):
        self.__output = gen_random_string(6)
        local_ip = self.__smbconnection.getSMBServer().get_socket().getsockname()[0]
        command = self.__shell + data + ' 1> tmp\\{} 2>&1 & popd'.format(self.__output)
        #command = self.__shell + data + ' 1> \\\\{}@{}\\misc\\tmp\\{} 2>&1'.format(local_ip, self.__port, self.__output)
        logging.debug('Executing command: ' + command)
        self.__win32Process.Create(command, self.__pwd, None)
        self.get_output_fileless()

    def get_output_fileless(self):
        while True:
            try:
                with open(os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), 'misc', 'tmp', self.__output), 'r') as output:
                    out = output.read()
                    if "TOTHEMOON" in out:
                        self.output_callback(output.read())
                        break
            except IOError:
                time.sleep(1)

    def get_output_remote(self):
        if self.__retOutput is False:
            self.__outputBuffer = ''
            return

        while True:
            try:
                self.__smbconnection.getFile(self.__share, self.__output, self.output_callback)
                break
            except Exception as e:
                if str(e).find('STATUS_SHARING_VIOLATION') >=0:
                    time.sleep(2)
                    pass
                else:
                    pass

        self.__smbconnection.deleteFile(self.__share, self.__output)

    def __str__(self):
        return "wmiexec"
