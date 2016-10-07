import cmdproxy
import getpass
import itertools
import os
import logging
import sys
import pickle
from rainbow_logging_handler import RainbowLoggingHandler

__author__ = "vmunde@microsoft.com"
__copyright__ = "copyrighted by Microsoft"
__script_name__ = os.path.basename(sys.argv[0])

class F5Loadbalancer(object):

    def __init__(self,devicename, username,password,RFC=None, result=None):
        self.devicename = devicename
        self.username = "phx\\"+username
        self.password = password
        self.result = result
        self.RFC = RFC
        self.fullversion_cmd = "show sys version"
        self.version_cmd = "show sys version | grep Version"
        self.build_cmd = "show sys version | grep Build"
        self.interface_cmd = "show net interface | grep up"
        self.devicestatus_cmd = 'show running-config /sys db failover.state | grep value'
        self.cpu_cmd = "show sys cpu"
        self.checkcpu_cmd = "show sys cpu | grep -i Utilization"
        self.memory_Cmd = "show sys memory"
        self.poollist = "show ltm pool all detail"
        self.avpoolcount_cmd = "show ltm pool all detail | grep \"Pool Member\" -A 4 | grep -c available"
        self.dispoolcount_cmd = "show ltm pool all detail | grep \"Pool Member\" -A 4 | grep -c \"disabled\\|offline\\|unknown\""
        self.hastatus_cmd = "show sys ha-status"
        self.hastatuscheck_cmd = "show sys ha-status | grep yes"
        self.vlan_cmd = "list net vlan"
        self.vlancount_cmd = "list net vlan | grep vlan -c"
        self.virtual_cmd = "list ltm virtual"
        self.virtuals_cmd = "list ltm virtual | grep \"ltm virtual\""
        self.virtualcount_cmd = "list ltm virtual | grep \"ltm virtual\" -c"
        self.virtualconnmirror_cmd = "list ltm virtual mirror | grep \"mirror enabled\" -B1"
        self.precheck_file = "/var/gnsopssus/logs/F5_device_logs/{}_{}_precheck.txt".format(self.RFC, self.devicename)
        self.postcheck_file = "/var/gnsopssus/logs/F5_device_logs/{}_{}_postcheck.txt".format(self.RFC, self.devicename)
        self.pre_pickle = "/var/gnsopssus/scripts/F5_initfiles/{}_{}_pickle.pkl".format(self.RFC,self.devicename)
        self.showsys_cmd = 'show sys software | grep no'

        self.creds = cmdproxy.Creds(username = self.username, password = self.password)
        self.connection = cmdproxy.Connection(self.devicename,self.creds)

        ###create logger for this object
        # self.logdir = os.path.join("/var/gnsopssus/logs/",'F5_logs')
        # if not os.path.exists(self.logdir):
        #     os.makedirs(self.logdir)
        # self.logger = logging.getLogger(__script_name__)
        # self.formatter = logging.Formatter("RFC"+self.RFC+" : "+__script_name__+" : "+str(getpass.getuser())+" : %(asctime)s : %(levelname)s : %(message)s",
        #                                   datefmt='%m/%d/%Y %I:%M:%S %p')
        # self.logger.setLevel(logging.INFO)
        # handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
        # handler.setFormatter(self.formatter)
        # self.logger.addHandler(handler)
        # file_path = os.path.join(self.logdir,"pre-post_summary.log")
        # filehandler = logging.FileHandler(file_path,"a")
        # self.logger.addHandler(filehandler)
        # filehandler.setFormatter(self.formatter)

    def get_disk(self):
        """

        :param device:
        :return: returns the non active empty disk
        """
        self.result = self.connection.showcmd(self.showsys_cmd).output().split(" ")
        return self.result[0]


    def version_check(self, parse = False):
        """
        function to cehck the current version on the device
        :param: device:
        :param: creds: credentials to login
        :return: current version of the device:
        """
        if parse:
            result = self.connection.showcmd(self.version_cmd).output()
            version = result.split("\n")
            result2 = self.connection.showcmd(self.build_cmd).output()
            build = result2.split("\n")
            ver = version[1].replace("\r", ""), build[0].replace("\r", "")
            self.result =  " ".join(ver[0].split()) + " " + " ".join(ver[1].split())
            return self.result
        else:

            self.result = self.connection.showcmd(self.fullversion_cmd).output()
            return self.result

    def Interfaces(self, parse = False):
        """

        :param parse:
        :return: {'3.1': 'up', '3.2': 'up', 'mgmt': 'up'}
        """
        if parse:
            interfaces = []
            interface_list = self.connection.showcmd(self.interface_cmd).output().splitlines()
            for line in interface_list:
                out = line.strip().split()
                interfaces.extend([out[0],out[1]])
            self.result = dict(itertools.izip_longest(*[iter(interfaces)] * 2, fillvalue=""))
            return self.result
        else:
            self.result = self.connection.showcmd(self.interface_cmd).output()
            return self.result

    def vlancheck(self, count= False):

        if count:
            self.result = self.connection.showcmd(self.vlancount_cmd).output()
            return self.result
        else:
            self.result = self.connection.showcmd(self.vlan_cmd).output()
            return self.result

    def hastatus(self,check = False):
        """
        Method to check the HA status on the class object
        :type self: object
        """
        if check:
            self.result = self.connection.showcmd(self.hastatuscheck_cmd).output()
            if self.result:
                return self.result
            else:
                return bool(self.result)
        else:
            self.result = self.connection.showcmd(self.hastatus_cmd).output()
            return self.result

    def poolcheck(self, count = False):
        """

        :param count: False
        :return:
        Ltm::Pool Member: scomsu5_wit_443_pl  10.21.209.41:443
        --------------------------------------------------------------
        Status
          Availability : offline
          State        : enabled
          Reason       : Pool member has been marked down by a monitor

        Traffic                ServerSide  General
          Bits In                       0        -
          Bits Out                      0        -
          Packets In                    0        -
          Packets Out                   0        -
          Current Connections           0        -
          Maximum Connections           0        -
          Total Connections             0        -
          Total Requests                -        0

         :param count: True
         :return:{'Available': '11', 'Disabled\\Offline\\Unknown': '58'}

        """
        try:
            if count:
                poolcount_dict = {}
                ava_pool = self.connection.showcmd(self.avpoolcount_cmd).output()
                dis_pool = self.connection.showcmd(self.dispoolcount_cmd).output()
                poolcount_dict['Available']=ava_pool
                poolcount_dict['Disabled\Offline\Unknown']=dis_pool
                self.result = poolcount_dict
                return self.result

            else:
                self.result = self.connection.showcmd(self.poollist).output()
                return self.result
        except Exception as e:
            print e

    def checkcpu(self, parse = False):
        """
        :param parse:
        :return: {'Current': '6', 'Max': '12', 'Average': '6'}
        """
        try:
            if parse:
                cpu_dict = {}
                cpu_out = self.connection.showcmd(self.checkcpu_cmd).output().split()
                cpu_dict['Current'] = cpu_out[1]
                cpu_dict['Average'] = cpu_out[2]
                cpu_dict['Max'] = cpu_out[3]
                self.result = cpu_dict
                return self.result
            else:
                self.result = self.connection.showcmd(self.cpu_cmd).output()
                return self.result
        except Exception as e:
            print e


    def checkvirtual(self, count = False):
        """

        :param count:True
        :return: number of virtual servers configured on the device

        """
        try:
            if count:
                self.result = self.connection.showcmd(self.virtualcount_cmd).output()
                return self.result
            else:
                self.result = self.connection.showcmd(self.virtuals_cmd).output()
                return self.result

        except Exception as e:
            print e

    def checkmirror(self):
        """

        :param count:True
        :return: retruns dictionary with virtual mirroring enabled


        """
        try:
            self.result = self.connection.showcmd(self.virtualconnmirror_cmd).output()
            return self.result

        except Exception as e:
            print e
            
    def device_Stat(self):
        """
        function to get active/standby status of the device
            :param device:
            :return Active/Standby value:
        """
        try:
            result = self.connection.showcmd(self.devicestatus_cmd).output().split("\n")[0].replace('"', '').replace('value', '')
            self.result = "".join(result.split())
            return self.result
        except Exception as e:
            print e

    def precheck(self):

        pre_dict = {}
        #mypickle_dict = {}

        pre_file = open(self.precheck_file,'a')
        pre_file.write("Devicename : {}\n\n".format(self.devicename))
        pre_file.write("RFC or Maintenance Ticket:{}\n".format(self.RFC))
        pre_file.write("Created by:{}\n\n".format(self.username))
        pre_file.write("\n"+self.fullversion_cmd+"\n")
        pre_file.write("\n"+self.version_check()+"\n")
        pre_file.write("\n"+self.interface_cmd+"\n")
        pre_file.write("\n"+self.Interfaces()+"\n")
        pre_file.write("\n"+self.cpu_cmd+"\n")
        pre_file.write("\n"+self.checkcpu()+"\n")
        pre_file.write("\n"+self.poollist+"\n")
        pre_file.write("\n"+self.poolcheck()+"\n")
        pre_file.write("\n"+self.hastatus_cmd+"\n")
        pre_file.write("\n"+self.hastatus()+"\n")
        pre_file.write("\n"+self.vlan_cmd+"\n")
        pre_file.write("\n"+self.vlancheck()+"\n")
        pre_file.write("\n"+self.virtuals_cmd+"\n")
        pre_file.write("\n"+self.checkvirtual()+"\n")
        pre_file.close()


        interface_pre = self.Interfaces(parse=True)
        cpu_pre = self.checkcpu(parse=True)
        version_pre = self.version_check(parse=True)
        pool_pre = self.poolcheck(count= True)
        virtualcount_pre = self.checkvirtual(count=True)
        ha_pre = self.hastatus(check=True)

        pre_dict['version'] = version_pre
        pre_dict['interface'] = interface_pre
        pre_dict['cpu'] = cpu_pre
        pre_dict['poolstatus'] = pool_pre
        pre_dict['virtualcount'] = virtualcount_pre
        pre_dict['HA_failure'] = ha_pre

        mypickle_pre = open(self.pre_pickle,'wb')
        pickler = pickle.Pickler(mypickle_pre)
        pickler.dump(pre_dict)
        mypickle_pre.close()
        return pre_dict

    def healthcheck(self):
        hc_dict = {}

        interface_hc = self.Interfaces(parse= True)
        cpu_hc = self.checkcpu(parse=True)
        version_hc = self.version_check(parse=True)
        pool_hc = self.poolcheck(count=True)
        virtualcount_hc = self.checkvirtual(count=True)
        ha_hc = self.hastatus(check=True)
        hastatus_hc = self.device_Stat()

        hc_dict['version'] = version_hc
        hc_dict['interface'] = interface_hc
        hc_dict['cpu'] = cpu_hc
        hc_dict['poolstatus'] = pool_hc
        hc_dict['virtualcount'] = virtualcount_hc
        hc_dict['HA_failure'] = ha_hc
        hc_dict['failover_stat'] = hastatus_hc

        return hc_dict

    def postcheck(self):

        post_file = open(self.postcheck_file,'a')
        post_file.write("Devicename : {}\n\n".format(self.devicename))
        post_file.write("RFC or Maintenance Ticket:{}\n".format(self.RFC))
        post_file.write("Created by:{}\n\n".format(self.username))
        post_file.write("\n"+self.fullversion_cmd+"\n")
        post_file.write("\n"+self.version_check()+"\n")
        post_file.write("\n"+self.interface_cmd+"\n")
        post_file.write("\n"+self.Interfaces()+"\n")
        post_file.write("\n"+self.cpu_cmd+"\n")
        post_file.write("\n"+self.checkcpu()+"\n")
        post_file.write("\n"+self.poollist+"\n")
        post_file.write("\n"+self.poolcheck()+"\n")
        post_file.write("\n"+self.hastatus_cmd+"\n")
        post_file.write("\n"+self.hastatus()+"\n")
        post_file.write("\n"+self.vlan_cmd+"\n")
        post_file.write("\n"+self.vlancheck()+"\n")
        post_file.write("\n"+self.virtuals_cmd+"\n")
        post_file.write("\n"+self.checkvirtual()+"\n")
        post_file.close()

        interface_post = self.Interfaces(parse= True)
        cpu_post = self.checkcpu(parse=True)
        version_post = self.version_check(parse=True)
        pool_post = self.poolcheck(count=True)
        virtualcount_post = self.checkvirtual(count=True)
        ha_post = self.hastatus(check=True)



        mypickle_post = open(self.pre_pickle,'rb')
        unpickler = pickle.Unpickler(mypickle_post)
        mypickle_out = unpickler.load()
        mypickle_post.close()


        ######compare pre-post#################

        compare_dict = {}

        if cmp(mypickle_out['interface'],interface_post):
            #print "interface check failed"
            compare_dict['interface_check'] = False
        else:
            #print "interface check passed"
            compare_dict['interface_check'] = True

        if cmp(mypickle_out['poolstatus'],pool_post):
            #print "Pool check failed"
            compare_dict['pool_check'] = False
        else:
            #print "pool check passed"
            compare_dict['pool_check'] = True

        if ha_post:
            compare_dict['ha_check'] = False
        else:
            compare_dict['ha_check'] = True

        if int(mypickle_out['cpu']['Current']) >= 80:
            #print "CPU test failed - high cpu - {}".format(int(mypickle_out['cpu']['Current']))
            compare_dict['cpu_check'] = False
        else:
            #print "CPU test passed - low cpu - {}".format(int(mypickle_out['cpu']['Current']))
            compare_dict['cpu_check'] = True

        if mypickle_out['virtualcount'] == virtualcount_post:
            compare_dict['virtualcount'] = True
        else:
            compare_dict['virtualcount'] = False

        return compare_dict


def main():

    device = raw_input("Enter devicename:")
    password = getpass.getpass("enter PHX pass: ")
    rfc = raw_input("enter RFC: ")
    myF5 = F5Loadbalancer(device,getpass.getuser(),password,rfc)
    # print "Number of vlans on the box is : {}".format(myF5.vlancheck(count= True))
    # print myF5.hastatus(check= True)
    myF5.poolcheck()
    print myF5.checkmirror()


    #print myF5.checkcpu(parse= True)
    #print "there are {} virtuals on this device".format(myF5.checkvirtual(count= True))
    #print myF5.checkvirtual()



if __name__ == "__main__":
    main()