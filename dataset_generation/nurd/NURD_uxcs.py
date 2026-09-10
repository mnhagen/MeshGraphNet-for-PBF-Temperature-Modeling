"""NLR Uxcs Remote Delegator (NURD)

This script allows the user to automatically submit abaqus jobs to one of the uxcs machines.
This file is the file that is copied to the uxcs machine.

19-02-2021
Version 1.6

Changelog:
1.0     first version                                       niels
1.1     functionality of multiple abaqus versions           Jos
        priority functionality                              Jos
1.2     local running option                                Jos
        checks if job was manually suspended                Jos
1.4     supplementary inp and odb file support              Jos
1.5     Bugfixing and terminate option                      Jos
1.6     ESI-PAM RTM support                                 Jos
2.1     Gitlab integration                                  Jos
2.2     Adding more monitoring options                      Jos
2.3     Add full UXCS04 support                             Jos
        Add SCRATCH directory support for faster calcs
        More priority levels
        Free disk space check
        GPU acceleration

for questions contact:
    niels.van.hoorn@nlr.nl
    jos.vroon@nlr.nl

this file should be accompanied by at least the following files:
 - NURD.py
 - NURD.bat

for more info see the readme file
"""
__version__ = 2.3
__stable__ = True

import os
import shutil
import time
import sys
import subprocess
import platform
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime


def check_if_started(abq_command, job_name):
    """
    This function will check if the job has started or if errors have occurred

    :param job_name:
    :param abq_command
    :return:    1: job is running correctly
                2: job is in pre-processing
                3: job not started due to errors
    """
    lock_file = False
    log_file = False
    dat_file = False
    msg_file = False
    sta_file = False
    found_error = False
    error_message = ''

    if os.path.isfile(c_I.replace('.inp', '.lck')):
        lock_file = True
    if os.path.isfile(c_I.replace('.inp', '.log')):
        log_file = True
    if os.path.isfile(c_I.replace('.inp', '.dat')):
        dat_file = True
    if os.path.isfile(c_I.replace('.inp', '.msg')):
        msg_file = True
    if os.path.isfile(c_I.replace('.inp', '.sta')):
        sta_file = True

    if sta_file:
        os.system('echo [%s] - Found a status file, Job is running correctly.\n' % (time.ctime()))
        return 1
    if not lock_file:
        if msg_file and not found_error:
            command = []
            if platform.system() == 'Windows':
                command = ['type ' + job_name + '.msg']
            elif platform.system() == 'Linux':
                command = ['tail ' + job_name + '.msg']
            out = subprocess.check_output(command, shell=True)
            lines = out.decode('ascii').split('\n')
            for line in lines:
                words = line.split(' ')
                for word in words:
                    if word in ('error', 'Error', 'errors', 'Errors', 'ERROR', 'ERRORS', 'error:', 'Error:'):
                        found_error = True
                        error_message = line
        if log_file and not found_error:
            command = []
            if platform.system() == 'Windows':
                command = ['type ' + job_name + '.log']
            elif platform.system() == 'Linux':
                command = ['tail ' + job_name + '.log']
            out = subprocess.check_output(command, shell=True)
            lines = out.decode('ascii').split('\n')
            for line in lines:
                words = line.split(' ')
                for word in words:
                    if word in ('error', 'Error', 'errors', 'Errors', 'ERROR', 'ERRORS', 'error:', 'Error:'):
                        found_error = True
                        error_message = line
        if dat_file and not found_error:
            command = []
            if platform.system() == 'Windows':
                command = ['type ' + job_name + '.dat']
            elif platform.system() == 'Linux':
                command = ['tail ' + job_name + '.dat']
            out = subprocess.check_output(command, shell=True)
            lines = out.decode('ascii').split('\n')
            for line in lines:
                words = line.split(' ')
                for word in words:
                    if word in ('error', 'Error', 'errors', 'Errors', 'ERROR', 'ERRORS', 'error:', 'Error:'):
                        found_error = True
                        error_message = line

    if found_error:
        os.system('echo [%s] - The job seems to have produced an error before it could start.\n' % (time.ctime()))
        os.system('echo [%s] - The error message is: %s\n' % (time.ctime(), error_message))
        if lock_file:
            os.system('%s terminate job=%s \n' % (abq_command, job_name))
        return 3
    return 2


def check_if_running(abq_command, job_name):
    """
    This function will check if the job is still running or if errors have occurred or the job is finished

    :param job_name:
    :param abq_command
    :return: true or false
    """
    lock_file = False
    log_file = False
    dat_file = False
    msg_file = False
    sta_file = False
    found_error = False
    error_message = ''
    job_completed = False
    job_converged = False

    if os.path.isfile(c_I.replace('.inp', '.lck')):
        lock_file = True
    if os.path.isfile(c_I.replace('.inp', '.log')):
        log_file = True
        command = []
        if platform.system() == 'Windows':
            command = ['type ' + job_name + '.log']
        elif platform.system() == 'Linux':
            command = ['tail ' + job_name + '.log']
        out = subprocess.check_output(command, shell=True)
        lines = out.decode('ascii').split('\n')
        for line in lines:
            words = line.split(' ')
            for word in words:
                if word in ('error', 'Error', 'errors', 'Errors', 'ERROR', 'ERRORS', 'error:', 'Error:'):
                    found_error = True
                    error_message = line
    if os.path.isfile(c_I.replace('.inp', '.dat')):
        dat_file = True
        if not lock_file:
            command = []
            if platform.system() == 'Windows':
                command = ['type ' + job_name + '.dat']
            elif platform.system() == 'Linux':
                command = ['tail ' + job_name + '.dat']
            out = subprocess.check_output(command, shell=True)
            lines = out.decode('ascii').split('\n')
            for line in lines:
                words = line.split(' ')
                for word in words:
                    if word in ('error', 'Error', 'errors', 'Errors', 'ERROR', 'ERRORS', 'error:', 'Error:'):
                        found_error = True
                        error_message = line
    if os.path.isfile(c_I.replace('.inp', '.msg')):
        msg_file = True
    if os.path.isfile(c_I.replace('.inp', '.sta')):
        sta_file = True
        command = []
        if platform.system() == 'Windows':
            command = ['type ' + job_name + '.sta']
        elif platform.system() == 'Linux':
            command = ['tail ' + job_name + '.sta']
        out = subprocess.check_output(command, shell=True)
        lines = out.decode('ascii').split('\n')
        for line in lines:
            words = line.split(' ')
            for word in words:
                if word == 'COMPLETED':
                    job_completed = True
                if word == 'SUCCESSFULLY':
                    job_converged = True

    if lock_file and log_file and dat_file and msg_file and sta_file and not found_error and not job_completed:
        os.system('echo [%s] - Lock, log, data, message and status files are found. The job is running correctly.\n' % (time.ctime()))
    if lock_file and job_completed:
        os.system('echo [%s] - The job seems to be completed but the lock file is still there. The job is stuck, sending terminate command.\n' % (time.ctime()))
        os.system('%s terminate job=%s \n' % (abq_command, job_name))
        if job_converged:
            return [False, 1]
    if found_error:
        os.system('echo [%s] - The job seems to have produced an error.\n' % (time.ctime()))
        os.system('echo [%s] - The error message is: %s\n' % (time.ctime(), error_message))
        if lock_file:
            os.system('%s terminate job=%s \n' % (abq_command, job_name))
        return [False, 2]
    if job_completed and not job_converged:
        os.system('echo [%s] - The job is not converging.\n' % (time.ctime()))
        return [False, 4]
    if not lock_file and job_completed:
        os.system('echo [%s] - The job seems to be completed.\n' % (time.ctime()))
        return [False, 1]
    return [True, 0]


def job_in_queue(feature):
    """
    This function checks if a job is queued for a certain feature.

    :param feature:
        this parameter is a string that describes the software that needs to be queried
    :return:
        job_queued: boolean value that is positive if a job is queued
        numlics: the number of licences available
        numused: the number of licences that are in use
    """
    # check os
    operating_system = platform.system()

    lic = '26001@licsrv07'
    tag = 'licsrv07/26001'
    command = ['license_abaqus']
    if operating_system == 'Windows':
        command = '/local/app/abaqus/Commands/abaqus licensing lmstat -c ' + lic + ' -f ' + feature
    elif operating_system == 'Linux':
        command = '/local/app/abaqus/Commands/abaqus licensing lmstat -c ' + lic + ' -f ' + feature
    # startupinfo = subprocess.STARTUPINFO()
    # startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        out = subprocess.check_output(command, shell=True)
    except:
        out = ''.encode('ascii')
        os.system('echo [%s] - Failed to read license info from server, no action will be taken. \n' % time.ctime())
    lines = out.decode('ascii').split('\n')
    job_is_queued = False
    numlics, numuse = [0, 0]
    for line in lines:
        if tag in line:
            if 'queued' in line:
                job_is_queued = True
        if 'Users' in line:
            package = line.split(' ')[2].strip(':')
            if package in ['abaqus']:
                numlics = int(line.split(' ')[6])
                numuse = int(line.split(' ')[12])
    return [job_is_queued, numlics, numuse]


def mutate_input_files_to_runnable(input_files, path):
    """

    :param input_files:
    :param path:
    :return:
    """
    included_files = []
    for file in input_files:
        if "INC_" in file:
            included_files.append(file)
        # This part is more complete but needs the code to search every line in every file.
        # Because of time reasons (file of 200 mb takes minutes) this is not used.
        """
        with open(path + file) as inp:
            for line in inp.readlines():
                if '*include' in line:
                    included_files.append(line.split('=')[-1].split('\\')[-1][:-1])
                elif '*INCLUDE' in inp.readlines():
                    included_files.append(line.split('=')[-1].split('\\')[-1][:-1])
                    """
    runnable_input_files = set(input_files) - set(included_files)
    return runnable_input_files


def files(path):
    for file in os.listdir(path):
        if os.path.isfile(os.path.join(path, file)):
            yield file


def search_for_input_files(path):
    """
    This function looks for and lists input (.inp) files. if none are found it throws a system exit.

    :param path:
        [string] path to search for .inp files
    :return:
        [list of strings] all .inp files in the path directory
    """
    abaqus_files = []
    all_files = []
    for file in files(path):
        if not file.endswith('.bat') and os.path.isfile(file):
            all_files.append(file)
        if file.endswith('.inp'):
            abaqus_files.append(file)
    abaqus_files = mutate_input_files_to_runnable(abaqus_files, path)
    subroutines = check_for_subroutines(path)
    return abaqus_files, all_files, subroutines


def check_for_subroutines(path):
    """
    This function looks for user subroutine (.f) files. Only one user subroutine file can be present in a single
    directory or this function will throw an error.

    :param path:
        [string] path to search for .f files
    :return:
        [string] the .f file in the path directory, if present, otherwise empty string
    """
    subroutine = ''
    for file in os.listdir(path):
        if ((file.endswith('.f') or file.endswith('.o') or
            file.endswith('.for') or file.endswith('.f90') or
            file.endswith('.f95') or file.endswith('.f03')) and
            len(subroutine) == 0 and not file.startswith('INC_')):
            print('** User subroutine %s found\n' % file)
            subroutine = file
        elif ((file.endswith('.f') or file.endswith('.o') or
            file.endswith('.for') or file.endswith('.f90') or
            file.endswith('.f95') or file.endswith('.f03')) and
            len(subroutine) > 1 and not file.startswith('INC_')):
            print('ERROR: make sure only one subroutine file is present in this directory')
            time.sleep(5)
            sys.exit(1)
    return subroutine


def job_prio():
    """

    :return:
    """
    if os.path.exists("PRIORITY_IS_1"):
        return 1
    elif os.path.exists("PRIORITY_IS_2"):
        return 2
    elif os.path.exists("PRIORITY_IS_3"):
        return 3
    elif os.path.exists("PRIORITY_IS_4"):
        return 4
    elif os.path.exists("PRIORITY_IS_5"):
        return 5
    else:
        f = open("PRIORITY_IS_2", "w+")
        f.close()
        os.system('echo [%s] - Job priority is reset to 2. \n' % time.ctime())
        return 2


def send_mail(mail_adress, calculationtime, error, status):
    sender = 'NURD@nlr.nl'

    bcc_receivers = ['jos.vroon@nlr.nl']
    receiver_name = mail_adress.split('@')[0].split('.')

    message = MIMEMultipart("alternative")
    message["Subject"] = 'NURD status report'
    message["From"] = sender
    message["To"] = mail_adress


    total_time = time.time() - time_start

    job_list = ', \r\n<br>'.join(inp)
    string0 = '<p>Hi %s,</p>' % (' '.join(receiver_name).title())

    if __stable__:
        string1 = '<p> Your job(s) finished running with NURD %s. It took %s in total and took %s of calculation time. It was calculated with priority of %s.</p>' % (__version__, convert(total_time), convert(calculationtime), job_prio())
    else:
        string1 = '<p> Your job(s) finished running with NURD beta %s. It took %s in total and took %s of calculation time. It was calculated with priority of %s.</p>' % (__version__, convert(total_time), convert(calculationtime), job_prio())
    string11 = ''
    for job, exit_code in status:
        if exit_code == 1:
            string11 += '%s finished successfully.<br>' % job
        if exit_code == 2:
            string11 += '%s finished with errors.<br>' % job
        if exit_code == 3:
            string11 += '%s could not start because of errors.<br>' % job
        if exit_code == 4:
            string11 += '%s stopped during calculation and did not finish.<br>' % job
    string11 += '<p>'


    string2 = '<p>You can find the files here: <a href="%s">%s</a>.</p>' % ('\\\\smb-nop01\\homes\\' + c_path.split(os.sep)[-1],
                                                                     '\\\\smb-nop01\\homes\\' + c_path.split(os.sep)[-1])
    if error:
        string25 = '<p>ALERT! An error seems to have occurred. Check the log files for more information.</p>'
    else:
        string25 = ''
    if odb_zip == 1:
        string3 = '<p>The files have been zipped and the zip file is placed here: <a href="\\\\smb-nop01\\homes\\">' \
                  '\\\\smb-nop01\\homes\\</a>.</p>'
    else:
        string3 = ''

    string4 = '<p style="color:white;">>%s %s %s %s %s</p>' % (receiver_name[0].capitalize(), receiver_name[1].capitalize(), job_prio(), total_time, calculationtime)

    payload = string0 + string1 + string11 + string2 + string25 + string3 + string4
    part1 = MIMEText(payload, "html")
    message.attach(part1)

    if mail_choice == 1:
        s = smtplib.SMTP('smtp-server.nlr.nl', 25)
        s.sendmail(sender, [mail_adress] + bcc_receivers, message.as_string())
        os.system('echo [%s] - Sent an email to %s. \n' % (time.ctime(), mail_adress))
    else:
        s = smtplib.SMTP('smtp-server.nlr.nl', 25)
        s.sendmail(sender, [bcc_receivers] + bcc_receivers, message.as_string())


def send_update_mail(mail_adress, runtime):
    sender = 'NURD@nlr.nl'

    bcc_receivers = ['jos.vroon@nlr.nl']
    receiver_name = mail_adress.split('@')[0].split('.')

    message = MIMEMultipart("alternative")
    message["Subject"] = 'NURD status update'
    message["From"] = sender
    message["To"] = mail_adress

    string0 = '<p>Hi %s,</p>' % (' '.join(receiver_name).title())

    string1 = '<p>A NURD process has been running for %i days. If you did not expect this, check if the process has failed or is stuck.</p>' % runtime

    string2 = '<p>You can find the files here: <a href="%s">%s</a>.</p>' % ('\\\\smb-nop01\\homes\\' + c_path.split(os.sep)[-1],
                                                                     '\\\\smb-nop01\\homes\\' + c_path.split(os.sep)[-1])

    payload = string0 + string1 + string2
    part1 = MIMEText(payload, "html")
    message.attach(part1)


    s = smtplib.SMTP('smtp-server.nlr.nl', 25)
    s.sendmail(sender, [mail_adress] + bcc_receivers, message.as_string())
    os.system('echo [%s] - Sent an email to %s. \n' % (time.ctime(), mail_adress))


def convert(seconds):
    day = seconds // (24 * 3600)
    seconds %= (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    if day == 0 and hour == 0 and minutes == 0:
        return "%02d seconds" % seconds
    elif day == 0 and hour == 0:
        return "%02d minutes and %02d seconds" % (minutes, seconds)
    elif day == 0:
        return "%02d hours, %02d minutes and %02d seconds" % (hour, minutes, seconds)
    else:
        return "%d days, %02d hours, %02d minutes and %02d seconds" % (day, hour, minutes, seconds)


def check_for_exit(abq_command, I):
    if not os.path.isfile("DELETE_THIS_TO_TERMINATE_CODE"):
        os.system('echo [%s] - Manual system exit is detected. \n' % time.ctime())
        if I=="":
            sys.exit()
        else:
            os.system('%s terminate job=%s \n' % (abq_command, I[:-4]))
            sys.exit()
    pass


def job_green_light(priority, running):
    check_for_exit(abq_command, I)
    os.system('echo [%s] - Job priority is %s\n' % (time.ctime(), priority))
    if priority == 1:
        return True
    if priority == 3:
        if not (datetime.datetime.today().hour in [0, 1, 2, 3, 4, 5, 6, 20, 21, 22, 23] or
                datetime.datetime.today().weekday() not in [0, 1, 2, 3, 4]):
            os.system('echo [%s] - It is office hours right now, no green light for the job. \n' % time.ctime())
            return False
    if priority == 4:
        if datetime.datetime.today().weekday() in [0, 1, 2, 3, 4]:
            os.system('echo [%s] - Today is not weekend, no green light for the job. \n' % time.ctime())
            return False
    if priority == 5:
        os.system('echo [%s] - No green light for the job.\n' % time.ctime())
        return False
    if running:
        os.system('echo [%s] - Checking if a job is in the queue. \n' % time.ctime())
        job_queued, number_of_licences, number_of_used = job_in_queue('abaqus')
        if job_queued:
            os.system('echo [%s] - A job is in the queue. No green light for the job. \n' % time.ctime())
            return False
        else:
            os.system('echo [%s] - No job is in the queue. Green light for the job. \n' % time.ctime())
            return True
    if not running:
        os.system('echo [%s] - Checking if enough tokens are available for job %s. \n' % (time.ctime(), I[:-4]))
        job_queued, number_of_licences, number_of_used = job_in_queue('abaqus')
        os.system('echo [%s] - %i tokens available, %i/%i. \n' %
                  (time.ctime(), number_of_licences - number_of_used, number_of_licences, number_of_used))
        if n_tokens > (number_of_licences - number_of_used):
            os.system('echo [%s] - Not enough tokens are available, checking again in 30 seconds. \n' %
                      time.ctime())
            return False
        if n_tokens <= (number_of_licences - number_of_used):
            os.system('echo [%s] - Enough tokens are available. Green light for the job\n' % time.ctime())
            return True
    else:
        return False


def check_free_disk_space(username):
    path = '/shared/home/nlr/' + username + '/'
    return shutil.disk_usage(path).free / 1024**3


def set_priority_to_5():
    if os.path.exists("PRIORITY_IS_1"):
        os.remove("PRIORITY_IS_1")
    elif os.path.exists("PRIORITY_IS_2"):
        os.remove("PRIORITY_IS_2")
    elif os.path.exists("PRIORITY_IS_3"):
        os.remove("PRIORITY_IS_3")
    elif os.path.exists("PRIORITY_IS_4"):
        os.remove("PRIORITY_IS_4")
    elif os.path.exists("PRIORITY_IS_5"):
        os.remove("PRIORITY_IS_5")
    f = open("PRIORITY_IS_5", "w+")
    f.close()
    pass


def send_no_space_mail(mail_adress):
    sender = 'NURD@nlr.nl'

    bcc_receivers = ['jos.vroon@nlr.nl']
    receiver_name = mail_adress.split('@')[0].split('.')

    message = MIMEMultipart("alternative")
    message["Subject"] = 'NURD status update'
    message["From"] = sender
    message["To"] = mail_adress

    string0 = '<p>Hi %s,</p>' % (' '.join(receiver_name).title())

    string1 = '<p>A NURD process has been suspended because NURD detected low disk space. Please check the disk usage and reset the priority of the job.</p>'

    string2 = '<p>You can find the files here: <a href="%s">%s</a>.</p>' % ('\\\\smb-nop01\\homes\\' + c_path.split(os.sep)[-1],
                                                                     '\\\\smb-nop01\\homes\\' + c_path.split(os.sep)[-1])

    payload = string0 + string1 + string2
    part1 = MIMEText(payload, "html")
    message.attach(part1)


    s = smtplib.SMTP('smtp-server.nlr.nl', 25)
    s.sendmail(sender, [mail_adress] + bcc_receivers, message.as_string())
    os.system('echo [%s] - Sent an email to %s. \n' % (time.ctime(), mail_adress))


def initiate_job(abq_command, c_I, job, n_cpus, gpu_choice, username, subr, priority):
    if len(subr) == 0:
        if gpu_choice == 1:
            os.system('%s input="%s" job=%s double=both cpus=%i gpus=1 output_precision=full scratch=/home/%s/\n' %
                      (abq_command, c_I, job, n_cpus, username))
        else:
            os.system('%s input="%s" job=%s double=both cpus=%i output_precision=full scratch=/home/%s/\n' %
                     (abq_command, c_I, job, n_cpus, username))
        os.system('echo [%s] - Job %s is submitted to abaqus %s with priority %s. \n' %
                  (time.ctime(), job, abq_version, priority))
    else:
        if gpu_choice == 1:
            os.system('%s input="%s" job=%s user=%s double=both cpus=%i gpus=1 output_precision=full scratch=/home/%s/\n' %
                      (abq_command, c_I, job, subr, n_cpus, username))
        else:
            os.system('%s input="%s" job=%s user=%s double=both cpus=%i output_precision=full scratch=/home/%s/\n' %
                  (abq_command, c_I, job, subr, n_cpus, username))
        os.system('echo [%s] - Job %s is submitted to abaqus %s with subroutine %s with priority %s. \n' %
                  (time.ctime(), job, abq_version, subr, priority))
    pass


def cleanup_completed_job(job_name):
    """Remove the Abaqus files for a successfully postprocessed job."""
    keep_files = {
        job_name + '.csv',
        job_name + '_edges.csv',
        job_name + '_global.json',
        job_name + '_metadata.json',
    }

    for file_name in os.listdir(c_path):
        if file_name in keep_files:
            continue

        if os.path.splitext(file_name)[0] != job_name:
            continue

        file_path = os.path.join(c_path, file_name)

        if os.path.isfile(file_path):
            os.remove(file_path)

    os.system('echo [%s] - Cleaned Abaqus files for job %s. \n' %
              (time.ctime(), job_name))


# initialise the script
time_start = time.time()
os.system('echo [%s] - Starting submition procedure. \n' % time.ctime())

# Define variables
n_cpus = int(sys.argv[1])
odb_zip = int(sys.argv[2])
job_priority = int(sys.argv[3])
abq_version = str(sys.argv[4])
gpu_choice = int(sys.argv[5])
mail_adress = str(sys.argv[6])
mail_choice = int(sys.argv[7])
n_tokens = 0
abq_command = '/local/app/abaqus/Commands/' + abq_version
c_path = os.getcwd()
error_happened = False
username = os.getlogin()

# # old ESI stuff
# esi_commands = [0,'/local/app/esi/pamrtm/2019.5/Linux_x86_64_2.29/bin/pamcmxdmp.sh',
#                 '/local/app/esi/pamrtm/2020.5/Linux_x86_64_2.31/bin/pamcmxdmp.sh',
#                 '/local/app/esi/pamrtm/2020.6/Linux_x86_64_2.32/bin/pamcmxdmp.sh']
# esi_versions_text = [0, 'ESI-PAM RTM 2019.5', 'ESI-PAM RTM 2020.5', 'ESI-PAM RTM 2020.6']
# esi_command = esi_commands[esi_version]

# print info about job like nr. of cpus, nr. of tokens and demanded software
os.system('echo [%s] - %i cpus are demanded. \n' % (time.ctime(), n_cpus))
if abq_version != 0:
    n_tokens = int(5*pow((n_cpus + gpu_choice), 0.422))
    os.system('echo [%s] - %i Abaqus tokens are demanded. \n' % (time.ctime(), n_tokens))
    if gpu_choice == 1:
        os.system('echo [%s] - GPU acceleration is demanded. \n' % time.ctime())
    os.system('echo [%s] - Abaqus %s is demanded. \n' % (time.ctime(), abq_version))
os.system('echo [%s] - Job priority is %i. \n' % (time.ctime(), job_priority))

# search for .inp files to submit
abq, all, subr = search_for_input_files(c_path)
inp = sorted(abq)
for file in all:
    if file in inp:
        os.system('echo [%s] - Input file %s is found and will be submitted. \n' % (time.ctime(), file))
    elif file in subr:
        os.system('echo [%s] - Subroutine %s is found and will be used. \n' % (time.ctime(), file))
    else:
        os.system('echo [%s] - Supplementary file %s is found and will be skipped. \n' % (time.ctime(), file))

# create informative files for user info and manual exit
f = open("DELETE_THIS_TO_TERMINATE_CODE", "w+")
f.close()
prio_file_name = 'PRIORITY_IS_%i' % job_priority
f = open(prio_file_name, "w+")
f.close()

check_for_exit(abq_command, "")

# ----------------------------------------------------------------------------
# SUBMITTING HAPPENS FROM HERE
# ----------------------------------------------------------------------------

calc_time = 0
mails_sent = 0
jobs_status = []

# this command is needed for functioning subroutines
# os.system('source /shared/app/export/linux/RHEL7_64/intel.init')

for I in inp:
    # This part is for ESI jobs
    # if I.endswith('.vdb'):
    #     os.system('echo [%s] - Job %s initialized. \n' % (time.ctime(), I[:-4]))
    #     check_for_exit(abq_command, "")
    #     c_I = c_path + os.sep + I
    #     os.system('echo [%s] - Job %s is submitted to %s with high priority. \n' %
    #               (time.ctime(), I[:-4], esi_versions_text[esi_version]))
    #     os.system('%s -np %i -restart %s\n' %
    #               (esi_command, n_cpus, I))

    if I.endswith('.inp'):
        os.system('echo [%s] - Job %s initialized. \n' % (time.ctime(), I[:-4]))
        check_for_exit(abq_command, I)
        c_I = c_path + os.sep + I
        running = False
        #
        # os.system('echo [%s] - Running extra command for explicit. \n' % time.ctime())
        # os.system('UCX_TLS=ud,sm,self \n')

        # As long as the job has not started, perform this loop
        while not running:
            if job_green_light(job_prio(), running):
                initiate_job(abq_command, c_I, I[:-4], n_cpus, gpu_choice, username, subr, job_prio())
                running = True
            running_time = int((time.time() - time_start) / 86400)
            if running_time > mails_sent:
                send_update_mail(mail_adress, running_time)
                os.system('echo [%s] - Sending status update email. \n' % time.ctime())
                mails_sent += 1
            time.sleep(30)

        started = False
        start_status = 0

        while not started:
            check_for_exit(abq_command, I)
            start_status = check_if_started(abq_command, I[:-4])
            os.system('echo [%s] - Waiting for job %s to start. \n' % (time.ctime(), I[:-4]))
            time.sleep(5)
            calc_time += 5
            if start_status == 1:
                os.system('echo [%s] - Job %s is successfully running. \n' % (time.ctime(), I[:-4]))
                started = True
            if start_status == 2:
                os.system('echo [%s] - Job %s is still pre-processing. \n' % (time.ctime(), I[:-4]))
            if start_status == 3:
                error_happened = True
                jobs_status.append([I, start_status])
                break
            running_time = int((time.time() - time_start) / 86400)
            if running_time > mails_sent:
                send_update_mail(mail_adress, running_time)
                os.system('echo [%s] - Sending status update email. \n' % time.ctime())
                mails_sent += 1


        # wait until finished if prio is 1
        os.system('echo [%s] - Monitoring job %s. \n' % (time.ctime(), I[:-4]))

        # as long as the job is correctly running, perform this loop
        job_status = check_if_running(abq_command, I[:-4])
        while job_status[0] and start_status < 3:
            running_time = int((time.time() - time_start) / 86400)
            if running_time > mails_sent:
                send_update_mail(mail_adress, running_time)
                os.system('echo [%s] - Sending status update email. \n' % time.ctime())
                mails_sent += 1
            check_for_exit(abq_command, I)
            if check_free_disk_space(username) < 10 and not job_prio() == 5:
                set_priority_to_5()
                send_no_space_mail(mail_adress)
            if job_green_light(job_prio(), running):
                if running:
                    job_status = check_if_running(abq_command, I[:-4])
                    os.system('echo [%s] - Job %s is still running check again in 30 seconds. \n' % (time.ctime(), I[:-4]))
                if not running:
                    os.system('%s resume job=%s \n' % (abq_command, I[:-4]))
                    running = True
            else:
                if running:
                    os.system('%s suspend job=%s \n' % (abq_command, I[:-4]))
                    running = False
                else:
                    os.system('echo [%s] - Job remains suspended.' % time.ctime())
            calc_time += 30
            time.sleep(30)
        if started:
            final_status = job_status[1]

            if final_status == 1:
                job_name = I[:-4]
                postprocess_command = [
                    abq_command,
                    'python',
                    os.path.join(c_path, 'postprocess_sample.py'),
                    job_name,
                ]

                os.system('echo [%s] - Postprocessing job %s. \n' %
                          (time.ctime(), job_name))

                postprocess_status = subprocess.call(
                    postprocess_command,
                    cwd=c_path,
                )

                if postprocess_status == 0:
                    cleanup_completed_job(job_name)
                    os.system('echo [%s] - Job %s was postprocessed successfully. \n' %
                              (time.ctime(), job_name))
                else:
                    final_status = 2
                    error_happened = True
                    os.system('echo [%s] - Postprocessing job %s failed with exit code %i. Files were retained. \n' %
                              (time.ctime(), job_name, postprocess_status))

            jobs_status.append([I, final_status])

        os.system('echo [%s] - Job %s has finished, monitoring has stopped. \n' % (time.ctime(), I[:-4]))


# zip odb if required
if odb_zip == 1:
    os.system('echo [%s] - Zipping jobs. \n' % time.ctime())
    tar_name = c_path.split(os.sep)[-1]
    os.system('echo %s\n' % c_path)
    os.system('echo %s\n' % tar_name)
    parent_path = os.sep.join(c_path.split(os.sep)[0:-1])
    os.system('tar -cvf - %s | xz -zT0 - > %s.tar.xz' % ('..' + os.sep + tar_name, tar_name))
    os.system('mv %s.tar.xz %s' % (tar_name, parent_path))

send_mail(mail_adress, calc_time, error_happened, jobs_status)

os.remove("DELETE_THIS_TO_TERMINATE_CODE")

os.system('echo [%s] - End of logging. Goodbye. \n' % time.ctime())
# ----------------------------------------------------------------------------
# END
# ----------------------------------------------------------------------------    
