# built in
import getpass
import time
import os
import re
import sys
import subprocess

# third party
import paramiko
from rainbow_logging_handler import RainbowLoggingHandler
import logging

# internal
from F5prepost import F5Loadbalancer
import cmdproxy
import getRFCdetails


__author__ = "vmunde@microsoft.com"
__copyright__ = "copyrighted by Microsoft"
__script_name__ = os.path.basename(sys.argv[0])
__team_email__ = "gnsopssus@microsoft.com"
__version__ = "1.1"


# logger = initialize_logger(default_argparse(), __script_name__)

class simple_log():
    class __simple_log():
        def __init__(self, RFC):
            self.RFC = RFC
            self.logdir = os.path.join("/var/gnsopssus/logs/", 'F5_logs')
            if not os.path.exists(self.logdir):
                os.makedirs(self.logdir)
            self.logger = logging.getLogger(__script_name__)
            self.formatter = logging.Formatter("RFC" + self.RFC + " : " + __script_name__ + " : " + str(
                getpass.getuser()) + " : %(asctime)s : %(levelname)s : %(message)s", datefmt='%m/%d/%Y %I:%M:%S %p')
            self.logger.setLevel(logging.INFO)
            handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
            handler.setFormatter(self.formatter)
            self.logger.addHandler(handler)
            self.file_path = os.path.join(self.logdir, "upgrade_summary.log")
            filehandler = logging.FileHandler(self.file_path, "a")
            self.logger.addHandler(filehandler)
            filehandler.setFormatter(self.formatter)

    instance = None

    def __init__(self, RFC):
        if not simple_log.instance:
            simple_log.instance = simple_log.__simple_log(RFC)

    def __getattr__(self, name):
        return getattr(self.instance, name)


class F5Upgrade(object):
    def __init__(self, devicename, phxusername, phxpassword, gmepassword, RFC=None, result=None):
        self.devicename = devicename
        self.phxusername = "phx\\" + phxusername
        self.phxpassword = phxpassword
        self.gmepassword = gmepassword
        self.RFC = RFC
        self.result = result

        self.upgrade_version = "Version 11.5.1 Build 7.40.167"
        self.Image_check = "!bash -c \"ls -ltr /shared/MSN/Images/\""
        self.HF_name = 'Hotfix-BIGIP-11.5.1.7.40.167-HF7-ENG.iso'
        self.HF_md5 = "9adda82ce9c6a0d7606d6c4ae42f1b83"
        self.base_name = "BIGIP-11.5.1.0.0.110.iso"
        self.copy_base_image = "!bash -c \" cp /shared/MSN/Images/%s /shared/images/\"" % self.base_name
        self.cpcmd = "!bash -c \"cp /shared/MSN/Images/%s /shared/images/.\"" % self.HF_name

        self.md5_Check = "!bash -c \"md5sum /shared/MSN/Images/%s | awk \'{print \$1}\'\"" % self.HF_name
        self.showsys_cmd = 'show sys software | grep no'

        self.save_cmd = "!bash -c \"tmsh /save sys config\""
        self.configsync_cmd = "!bash -c \"tmsh run /sys config-sync\""
        self.ucs_cmd = "!bash -c \"tmsh save sys ucs /shared/MSN/Backups/RFC{}_{}_preupgrade\"".format(self.RFC,
                                                                                                       self.devicename)

        self.creds = cmdproxy.Creds(username=self.phxusername, password=self.phxpassword)
        self.connection = cmdproxy.Connection(self.devicename, self.creds)
        self.check_disk = "!bash -c \"b software status show | grep %s | tail -1 | awk \'{print \$8,\$9}\'\"" % (
            self.get_disk())
        self.install_disk = "!bash -c \"tmsh install sys software hotfix {} volume {}\"".format(self.HF_name,
                                                                                                self.get_disk())
        self.log = simple_log(self.RFC)

    def connect(self, cmd):

        """
        paramiko function to connect to the device to send commands

        :param device:devicename
        :param cmd: command to execute
        :return: executes the given command on the device
        """
        self.cmd = cmd
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self.devicename, username=getpass.getuser(), password=self.gmepassword, timeout=5)
        stdin, stdout, stderr = client.exec_command(self.cmd)
        time.sleep(5)
        if self.cmd == self.check_disk or self.Image_check or self.md5_Check:
            self.result = stdout.read()
            client.close()
            return self.result
        else:
            client.close()

    def configsync(self):
        self.connect(self.save_cmd.strip())
        time.sleep(5)
        self.connect(self.configsync_cmd.strip())
        time.sleep(5)

    def saveucs(self):
        """

        :return:saves ucs backup on device
        """
        self.connect(self.ucs_cmd)

    def simple_pinger(self, retries, sleep):
        """

        :rtype :
        """
        self.retries = retries
        self.sleep = sleep

        retry = 0
        while retry <= self.retries:
            response = subprocess.Popen(['ping', '-c', '1', self.devicename], stdout=subprocess.PIPE).stdout.read()
            result = re.findall(r"1 received", response, flags=re.IGNORECASE)
            if result:
                self.log.logger.info("{} is reachable".format(self.devicename))
                return True
            else:
                retry += 1
                time.sleep(self.sleep)

    def upgradelicense(self):
        pass


    def upgrader(self):

        out_file = self.connect(self.Image_check.strip())
        if self.HF_name and self.base_name in out_file:
            self.log.logger.info(
                "{} and {} already in /shared/MSN/Images/...checking MD5 for the image file".format(self.base_name,
                                                                                                    self.HF_name))
            try:
                md5 = self.connect(self.md5_Check.strip()).strip()
                if md5 == self.HF_md5:
                    self.log.logger.info("MD5 is success full {} ... copying file to /shared/images".format(md5))
                    self.connect(self.copy_base_image.strip())
                    time.sleep(120)
                    self.connect(self.cpcmd.strip())
                    time.sleep(60)
                else:
                    self.log.logger.error("MD5 check failed for HF, uploading the OS files again")
                    os.system(
                        "python2.7 /home/vmunde/Source/F5_11x_SCP.py " + self.devicename + " " + self.phxpassword + " " + self.gmepassword + " " + getpass.getuser())
                    md5_upload = self.connect(self.md5_Check.strip()).strip()
                    time.sleep(3)
                    self.log.logger.info("now copying files from hopbox")
                    if md5_upload == self.HF_md5.strip():
                        self.log.logger.info("MD5 check successful - {}".format(md5_upload))
                        self.log.logger.info("Copying file to /shared/images...")
                        self.connect(self.copy_base_image.strip())
                        time.sleep(120)
                        self.connect(self.cpcmd.strip())
                        time.sleep(60)
            except Exception as e:
                print e
        else:
            self.log.logger.warning(
                "no {} file on /shared/MSN/Images/...Downloading files from Hopbox".format(self.HF_name))
            os.system(
                "python2.7 /home/vmunde/Source/F5_11x_SCP.py " + self.devicename + " " + self.phxpassword + " " + self.gmepassword + " " + getpass.getuser())
            try:
                md5_upload = self.connect(self.md5_Check.strip()).strip()
                if md5_upload == self.HF_md5.strip():
                    self.log.logger.info("MD5 check successful - {}".format(md5_upload))
                    self.log.logger.info("Copying file to /shared/images...")
                    self.connect(self.copy_base_image.strip())
                    time.sleep(120)
                    self.connect(self.cpcmd.strip())
                    time.sleep(60)

                else:
                    self.log.logger.error("MD5 check failed - {}".format(md5))
                    os.system(
                        "python2.7 /home/vmunde/Source/F5_11x_SCP.py " + self.devicename + " " + self.phxpassword + " " + self.gmepassword + " " + getpass.getuser())
                    md5_upload = self.connect(self.md5_Check.strip()).strip()
                    time.sleep(3)
                    self.log.logger.info("now copying files from hopbox")
                    if md5_upload == self.HF_md5.strip():
                        self.log.logger.info("MD5 check successful - {}".format(md5_upload))
                        self.log.logger.info("Copying file to /shared/images...")
                        self.connect(self.copy_base_image.strip())
                        time.sleep(120)
                        self.connect(self.cpcmd.strip())
                        time.sleep(60)
            except Exception as e:
                print e

        try:
            upgrade_disk = self.get_disk()
            self.log.logger.info("Now installing {} software on {}".format(self.base_name,upgrade_disk))
            self.connect(self.install_disk)
            time.sleep(10)
            while True:
                check1 = self.connect(self.check_disk).strip()
                self.log.logger.info("current status is" + check1)
                if check1 == "complete":
                    self.log.logger.info("Done with adding {}".format(upgrade_disk))
                    break
            return upgrade_disk
        except Exception as e:
            print e


    def get_disk(self):
        """

        :param device:
        :return: returns the non active empty disk
        """
        self.result = self.connection.showcmd(self.showsys_cmd).output().split(" ")
        return self.result[0]


def main():
    user = getpass.getuser()
    phx = getpass.getpass("Enter PHX password: ")
    gme = getpass.getpass("Enter GME password: ")
    rfc = raw_input("\nEnter the RFC number for this MW:").strip()
    A_Device = raw_input("\nEnter A device name:").strip()

    mainlog = simple_log(rfc)
    mainlog.logger.info("Upgrade logs will be stored at {}".format(mainlog.file_path))
    mainlog.logger.info("you have entered RFC{} for this maintenance, checking for affected devices... ".format(rfc))
    #A_Device = getRFCdetails.GetAssets(getRFCdetails.get_Data(rfc, user, phx))
    mainlog.logger.info("User entered {} for the upgrade finding the B side".format(A_Device))
    if ord(A_Device[-1]) % 2 == 0:
        B_Device = A_Device[:-1] + chr(ord(A_Device[-1]) - 1)
    else:
        B_Device = A_Device[:-1] + chr(ord(A_Device[-1]) + 1)

    mainlog.logger.info("B device is {}".format(B_Device))
    mainlog.logger.info("checking for Active/Standby Status")

    A_side = F5Loadbalancer(A_Device, user, phx, rfc)
    B_side = F5Loadbalancer(B_Device, user, phx, rfc)

    Active = ''
    Standby = ''
    Active_Pre = None
    Standby_Pre = None

    check_A = A_side.device_Stat()
    if check_A == 'active':
        Active = A_Device
        Active_Pre = A_side
    else:
        Standby = A_Device
        Standby_Pre = A_side

    check_B = B_side.device_Stat()
    if check_B == 'active':
        Active = B_Device
        Active_Pre = B_side
    else:
        Standby = B_Device
        Standby_Pre = B_side

    mainlog.logger.info("{} is Active and {} is standby".format(Active, Standby))
    mainlog.logger.info("starting maintenance on {}".format(Standby))

    upgradeStandby = F5Upgrade(Standby, user, phx, gme, rfc)
    upgradeActive = F5Upgrade(Active, user, phx, gme, rfc)

    current_Version_Standby = Standby_Pre.version_check(parse=True)
    mainlog.logger.info("{} is on {}..checking upgrade eligibility".format(Standby, current_Version_Standby))
    if current_Version_Standby == upgradeStandby.upgrade_version:
        mainlog.logger.info("Device is already upgraded to {}.. aborting upgrade".format(current_Version_Standby))
        sys.exit()
    else:

        mainlog.logger.info("{} device is not upgraded.. starting the upgrade".format(Standby))

        #precheck on active device
        mainlog.logger.info("Starting precheck on active device {}".format(Active))
        Active_pre_dict = Active_Pre.precheck()
        mainlog.logger.info("Checking for Interface status....")
        for key, value in Active_pre_dict['interface'].iteritems():
            mainlog.logger.info("interface {} is {} ".format(key, value))
        mainlog.logger.info("Checking HA failure status....")
        if Active_pre_dict['HA_failure'] == True:
            mainlog.logger.error("HA failures occured on device.. please check manually")
        else:
            mainlog.logger.info("No HA failures on device")
        mainlog.logger.info("Checking for Available and Offline pool counts....")
        for key, value in Active_pre_dict['poolstatus'].iteritems():
            mainlog.logger.info("Number of {} pool is {} ".format(key, value))
        mainlog.logger.info("There are {} virtuals configured on this device".format(Active_pre_dict['virtualcount']))
        mainlog.logger.info("Checking for CPU status....")
        for key, value in Active_pre_dict['cpu'].iteritems():
            mainlog.logger.info("{} cpu is {}".format(key, value))


        #precheck on Standby device
        mainlog.logger.info("Starting precheck on standby device {}".format(Standby))
        standby_pre_dict = Standby_Pre.precheck()
        mainlog.logger.info("Checking for Interface status....")
        for key, value in standby_pre_dict['interface'].iteritems():
            mainlog.logger.info("interface {} is {} ".format(key, value))
        mainlog.logger.info("Checking HA failure status....")
        if standby_pre_dict['HA_failure'] == True:
            mainlog.logger.error("HA failures occured on device.. please check manually")
        else:
            mainlog.logger.info("No HA failures on device")
        mainlog.logger.info("Checking for Available and Offline pool counts....")
        for key, value in standby_pre_dict['poolstatus'].iteritems():
            mainlog.logger.info("Number of {} pool is {} ".format(key, value))
        mainlog.logger.info("There are {} virtuals configured on this device".format(standby_pre_dict['virtualcount']))
        mainlog.logger.info("Checking for CPU status....")
        for key, value in standby_pre_dict['cpu'].iteritems():
            mainlog.logger.info("{} cpu is {}".format(key, value))

        mainlog.logger.info("Saving config and running config sync from {} to {}".format(Active, Standby))
        upgradeActive.configsync()
        mainlog.logger.info("Now taking UCS backups and storing in /shared/MSN/Backups/")
        upgradeActive.saveucs()
        upgradeStandby.saveucs()

        upgraded_volume = upgradeStandby.upgrader()
        time.sleep(5)
        mainlog.logger.info("The device will reboot into {} now. Please connect to console to collect console messages".format(upgraded_volume))
        recmd = raw_input("\n\n\n\n Do you want to Reboot the box now ? [y/n]: ")

        if recmd == 'y':
            reload_cmd = "!bash -c \"tmsh reboot volume {}\"".format(upgraded_volume)
            time.sleep(5)
            upgradeStandby.connect(reload_cmd)
            mainlog.logger.info("rebooting the volume with !bash -c \"tmsh reboot volume {}\"".format(upgraded_volume))
            mainlog.logger.info("Device rebooting .... Please wait")
            mainlog.logger.info("starting sleep for 600 sec before starting the pinger to validate connectivity ")
            time.sleep(600)
            mainlog.logger.info("checking if the device came up from reboot")
            pingAfter = upgradeStandby.simple_pinger(30,10)
            if pingAfter:
                mainlog.logger.info("checking ssh to the device...")
                while True:
                    try:
                        upgraded_version = Standby_Pre.version_check(parse=True)
                        mainlog.logger.info("SSH worked and device is upgraded to {}".format(upgraded_version))
                        break
                    except Exception as e:
                        mainlog.logger.info("Device is still coming back from reboot. Please wait")
                        time.sleep(30)
                        continue

                mainlog.logger.info("{} is up from reboot initiating final sleep for things to settle up".format(Standby))
                time.sleep(120)
                mainlog.logger.info("Initiating post check on {}".format(Standby))
                healthcheck_dict = Standby_Pre.healthcheck()
                mainlog.logger.info("{} is upgraded to {}".format(Standby, healthcheck_dict['version']))
                mainlog.logger.info("Checking for Interface status....")
                for key, value in healthcheck_dict['interface'].iteritems():
                    mainlog.logger.info("interface {} is {} ".format(key, value))
                for key, value in healthcheck_dict['poolstatus'].iteritems():
                    mainlog.logger.info("Number of {} pool is {} ".format(key, value))
                mainlog.logger.info("There are {} virtuals configured on this device".format(healthcheck_dict['virtualcount']))
                mainlog.logger.info("Checking HA failure status....")
                if healthcheck_dict['HA_failure'] == True:
                    mainlog.logger.error("HA failures occured on device.. please check manually")
                else:
                    mainlog.logger.info("No HA failures on device")
                mainlog.logger.info("Device is ready to failover from {} to {}".format(Active,Standby))
                failcmd = raw_input("\n\n\nDo you want to failover from {} to {} ?[y/n]".format(Active,Standby))


                if failcmd == 'y':
                    failover = "!bash -c \"b failover standby\""
                    temp_Active = Active
                    temp_standby = Standby
                    try:
                        upgradeActive.connect(failover.strip())
                        time.sleep(15)
                        mainlog.logger.info("Checking if the failover was successful....")
                        current_stat_Active = Active_Pre.device_Stat()
                        if current_stat_Active == 'standby':
                            Active = temp_standby
                            Standby = temp_Active
                            mainlog.logger.info("traffic failed over to {}".format(Active))

                        else:
                            mainlog.logger.error("Failover failed. Please Escalate")
                            sys.exit(mainlog.logger.error("Exiting the script now. Please escalate"))
                    except Exception as e:
                        print e

                elif failcmd == 'n':
                    "{} is upgraded to {}. Please failover to upgrade {}".format(Standby,healthcheck_dict['version'],Active)
                mainlog.logger.info("Make sure {} is healthy and the smoketest cleared.".format(Standby))
                next_upgrade = raw_input("Are you ready to continue upgrade on {} ?[y/n]: ".format(Standby))
                if next_upgrade == "y":
                    newupgradeActive = upgradeStandby
                    newupgradeStandby = upgradeActive
                    newActive_Pre = Standby_Pre
                    newStandby_Pre = Active_Pre
                    upgraded_volume_new = newupgradeStandby.upgrader()
                    time.sleep(5)
                    mainlog.logger.info("The device will reboot into {} now. Please connect to console to collect console messages".format(upgraded_volume_new))
                    recmd = raw_input("\n\n\n\n Do you want to Reboot the box now ? [y/n]: ")
                    if recmd == 'y':
                        reload_cmd = "!bash -c \"tmsh reboot volume {}\"".format(upgraded_volume_new)
                        time.sleep(5)
                        newupgradeStandby.connect(reload_cmd)
                        mainlog.logger.info("rebooting the volume with !bash -c \"tmsh reboot volume {}\"".format(upgraded_volume))
                        mainlog.logger.info("Device rebooting .... Please wait")
                        mainlog.logger.info("starting sleep for 600 sec before starting the pinger to validate connectivity ")
                        time.sleep(600)
                        mainlog.logger.info("checking if the device came up from reboot")
                        pingAfternew = newupgradeStandby.simple_pinger(30,10)
                        if pingAfternew:
                            mainlog.logger.info("checking ssh to the device...")
                            while True:
                                try:
                                    upgraded_version = newStandby_Pre.version_check(parse=True)
                                    mainlog.logger.info("SSH worked and device is upgraded to {}".format(upgraded_version))
                                    break
                                except Exception as e:
                                    mainlog.logger.info("Device is still coming back from reboot. Please wait")
                                    time.sleep(30)
                                    continue

                            mainlog.logger.info("{} is up from reboot initiating final sleep for things to settle up".format(Standby))
                            time.sleep(120)
                            mainlog.logger.info("Initiating post check on {}".format(Standby))
                            newhealthcheck_dict = newStandby_Pre.healthcheck()
                            mainlog.logger.info("{} is upgraded to {}".format(Standby, newhealthcheck_dict['version']))
                            mainlog.logger.info("Checking for Interface status....")
                            for key, value in newhealthcheck_dict['interface'].iteritems():
                                mainlog.logger.info("interface {} is {} ".format(key, value))
                            for key, value in newhealthcheck_dict['poolstatus'].iteritems():
                                mainlog.logger.info("Number of {} pool is {} ".format(key, value))
                            mainlog.logger.info("There are {} virtuals configured on this device".format(newhealthcheck_dict['virtualcount']))
                            mainlog.logger.info("Checking HA failure status....")
                            if newhealthcheck_dict['HA_failure'] == True:
                                mainlog.logger.error("HA failures occured on device.. please check manually")
                            else:
                                mainlog.logger.info("No HA failures on device")
                            mainlog.logger.info("Device is ready to failover from {} to {}".format(Active,Standby))
                            failcmd = raw_input("\n\n\nDo you want to failover from {} to {} ?[y/n]: ".format(Active,Standby))
                            if failcmd == 'y':
                                failover_11x = "run sys failover standby"
                                temp_Active = Active
                                temp_standby = Standby

                                try:
                                    newupgradeActive.connect(failover_11x.strip())
                                    time.sleep(15)
                                    mainlog.logger.info("Checking if the failover was successful....")
                                    current_stat_Active = ''
                                    current_stat_Active = newActive_Pre.device_Stat()
                                    if current_stat_Active == 'standby':
                                        Active = temp_standby
                                        Standby = temp_Active
                                        mainlog.logger.info("traffic failed over to {}".format(Active))
                                    else:
                                        mainlog.logger.error("Failover failed. Please Escalate")
                                        sys.exit(mainlog.logger.error("Exiting the script now. Please escalate"))
                                except Exception as e:
                                    print e

                            elif failcmd == 'n':
                                "{} is upgraded to {}. Please failover to upgrade {}".format(Standby,newhealthcheck_dict['version'],Active)

                            mainlog.logger.info("Please have the property smoketest ..")
                            mainlog.logger.info("Initiating post check on both the devices")
                            Active_Post = newStandby_Pre
                            Standby_Post  = newActive_Pre
                            Active_post_dict = Active_Post.postcheck()
                            Standby_post_dict = Standby_Post.postcheck()
                            for key,value in Active_post_dict.iteritems():
                                if value == True:
                                    mainlog.logger.info("{} test passed on {}".format(key,Active))
                                else:
                                    mainlog.logger.info("{} test failed on {}".format(key,Active))

                            for key,value in Standby_post_dict.iteritems():

                                if value == True:
                                    mainlog.logger.info("{} test passed on {}".format(key,Standby))
                                else:
                                    mainlog.logger.info("{} test failed on {}".format(key,Standby))






            else:
                mainlog.logger.critical("{} is not yet up from reboot.. Please check manually and Escalate".format(Standby))


        elif recmd == 'n':
            mainlog.logger.info("Reboot aborted.....")
            mainlog.logger.info("HF is installed on volume {}".format(upgraded_volume))
            mainlog.logger.info("You will need to manually enable the volume in order to upgrade the device")


if __name__ == "__main__":
    main()