#!/usr/local/bin/python2.7
import os
import pexpect
from pexpect import *
import sys
import time
import getpass
import subprocess
import paramiko

__author__ = "vmunde@microsoft.com"
__copyright__ = "copyrighted by Microsoft"
__script_name__ = os.path.basename(sys.argv[0])





base = "E:/TFTP-root/images/BigIP/11.5.1/BIGIP-11.5.1.0.0.110.iso*"
#base_md5 = "E:/TFTP-root/images/BigIP/11.5.1/BIGIP-11.5.1.0.0.110.iso.md5"
HF_Path = "E:/TFTP-root/images/BigIP/11.5.1/Hotfixes/"
base_name = "BIGIP-11.5.1.0.0.110.iso"
base_md5_name = "BIGIP-11.5.1.0.0.110.iso.md5"
HF_name = "Hotfix-BIGIP-11.5.1.7.40.167-HF7-ENG.iso*"
HF_fname = "Hotfix-BIGIP-11.5.1.7.40.167-HF7-ENG.iso"
#logger.info("The HF being copied is {}".format(HF_fname))
HF_md5 = "Hotfix-BIGIP-11.5.1.7.40.167-HF7-ENG.iso.md5"
local = "/shared/MSN/Images/."

device = sys.argv[1].strip()


#device = raw_input("Enter device name:")

phx_pass = sys.argv[2].strip()

#phx_pass = getpass.getpass(prompt="Enter your phx password:")

password = sys.argv[3].strip()
#password = getpass.getpass("Enter GME creds:").strip()

user = sys.argv[4].strip()
#user = getpass.getuser()


dc = device.split("-")
datacenter = dc[0]
url ="http://subtool/ordered_nethop_list.cgi?"+datacenter
creds = user+":"+phx_pass
get_page = subprocess.check_output(["curl","-s","--ntlm","--user",creds,url]).strip()
get_page = get_page.split('\r')
MOP_hop = get_page[0].split(':')
hopbox = MOP_hop[2].replace(' ','')
#logger.info("copying from Hopbox {}".format(hopbox))

cp_base = "scp %s@%s:"%(user,hopbox)+base+" "+local
#cp_base_md5 = "scp %s@%s:"%(user,hopbox)+base_md5+" "+local
HF_cmd = "scp %s@%s:"%(user,hopbox)+HF_Path+HF_name+" "+local
#HF_md5_cmd = "scp %s@%s:"%(user,hopbox)+HF_Path+HF_md5+" "+local


command1='ssh %s@%s'%(user,device)
child=pexpect.spawn(command1,timeout=20)

i = child.expect(['assword:', r"yes/no"], timeout=10)
if i == 0:
  child.sendline(password)
  child.sendline('\r')
  child.expect('bp>')
  child.sendline('!bash')
  child.sendline('\r')
  child.expect('#')
  child.sendline(cp_base)
  i = child.expect(['password:', r"yes/no"])

  if i == 0:
    child.sendline(phx_pass)

    child.sendline('\r')
    #logger.info("copying base Image File....please wait")
    child.expect("#", timeout=36000)

# copy Hotfix image and Md5

    child.sendline(HF_cmd)
    child.expect("assword:", timeout=10)
    child.sendline(phx_pass)
    child.sendline('\r')
    #logger.info("copying HotFix File....please wait")
    child.expect("#", timeout=36000)

    child.sendline('exit')

  elif i == 1:
    child.sendline("yes")
    child.sendline('\r')
    child.expect("assword:", timeout=10)
    child.sendline(phx_pass)
    child.sendline('\r')
    #logger.info("copying base Image File....please wait")
    child.expect("#", timeout=36000)

# copy Hotfix image and Md5

    child.sendline(HF_cmd)
    child.expect("assword:", timeout=10)
    child.sendline(phx_pass)
    child.sendline('\r')
    #logger.info("copying HotFix File....please wait")
    child.expect("#", timeout=36000)

    child.sendline('exit')
elif i == 1:
  child.sendline("yes")
  child.sendline('\r')
  child.expect("assword:", timeout=10)
  child.sendline(password)
  child.sendline('\r')
  child.expect('bp>')
  child.sendline('!bash')
  child.sendline('\r')
  child.expect('#')
  child.sendline(cp_base)
  i = child.expect(["assword:", r"yes/no"])
  if i == 0:
    child.sendline(phx_pass)
    child.sendline('\r')
    #logger.info("copying base Image File....please wait")
    child.expect("#", timeout=3600)

# copy Hotfix image and Md5

    child.sendline(HF_cmd)
    child.expect("assword:", timeout=10)
    child.sendline(phx_pass)
    child.sendline('\r')
    #logger.info("copying HotFix File....please wait")
    child.expect("#", timeout=36000)
    child.sendline('exit')


  elif i == 1:
    child.sendline("yes")
    child.sendline('\r')
    child.expect("assword:", timeout=10)
    child.sendline(phx_pass)
    child.sendline('\r')
    #logger.info("copying base Image File....please wait")
    child.expect("#", timeout=3600)
    # copy Hotfix image and Md5

    child.sendline(HF_cmd)
    child.expect("assword:", timeout=10)
    child.sendline(phx_pass)
    child.sendline('\r')
    #logger.info("copying HotFix File....please wait")
    child.expect("#", timeout=36000)
    child.sendline('exit')
child.close()


# check MD5

md5_useri = raw_input("\n\nDO you want to check MD5 for this device:[y/n]:")

if md5_useri == 'y':
  client = paramiko.SSHClient()
  client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  cmd = ["!bash -c \"md5sum /shared/MSN/Images/%s | awk \'{print \$1}\'\""%base_name,"!bash -c \"cat /shared/MSN/Images/%s | awk \'{print \$1}\'\""%base_md5_name]
  result = []
  for c in cmd:
    client.connect(device, username=user, password=password)
    stdin, stdout, stderr = client.exec_command(c)
    time.sleep(10)
    out = stdout.read()
    result.append(out)
    if result[0].replace('\n','') == result[1].replace('\n',''):
      print "Base Image MD5 OK !!!"
    else:
      print "Base Image MD5 Failed Please retry copy"
      cmd1 = ["!bash -c \"md5sum /shared/MSN/Images/%s | awk \'{print \$1}\'\""%HF_fname,"!bash -c \"cat /shared/MSN/Images/%s | awk \'{print \$1}\'\""%HF_md5]
      result1 = []
      for c in cmd1:
        client.connect(device, username=user, password=password)
        stdin, stdout, stderr = client.exec_command(c)
        time.sleep(10)
        out1 = stdout.read()
        result1.append(out1)
        if result1[0].replace('\n','') == result1[1].replace('\n',''):
          print "HotFix MD5 OK!!!"
        else:
          print "HotFix MD5 Failed Please retry copy"

elif md5_useri == 'n':
    print "Its important to check MD5, please check manually......"

