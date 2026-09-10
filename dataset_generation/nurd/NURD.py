"""AVCE auto abaqus job submitter

This script allows the user to automatically submit abaqus jobs to one of the uxcs machines.

Changelog:
1.0     first version                                       Niels
1.1     functionality of multiple abaqus versions           Jos
        priority functionality                              Jos
1.2     local running option                                Jos
        abaqus version checking                             Jos
        input checks                                        Jos
1.3     live checks for abaqus versions and cpu usage       Jos
1.4     supplementary inp and odb file support              Jos
1.5     user input at top of the file                       Jos
        supplementary inp file changes (INC_ prefix)        Jos
1.6     changed some texts and added defaults               Jos
2.0     GitLab supported stable release                     Jos
2.1     Added multiple functionalities                      Jos
2.2     Adding more monitoring functions                    Jos
2.3     Add full UXCS04 support                             Jos
        Add SCRATCH directory support for faster calcs
        More priority levels
        Free disk space check
        GPU acceleration

for questions contact:
    niels.van.hoorn@nlr.nl
    jos.vroon@nlr.nl

this file should be accompanied by at least the following files:
 - NURD_uxcs.py
 - NURD.bat

for more info see the readme file
"""

__version__ = 2.3
__stable__ = True


import os
import datetime
import shutil
import time
import sys
import getpass
import subprocess
import platform

try:
    import paramiko
except ImportError:
    import pip
    os.system("%s -m pip install paramiko" % sys.executable)
    # pip.main(['install', 'paramiko'])
    import paramiko


def check_number_of_cores():
    """
    This function runs a cmd command to get the number of cores on the current machine

    :return:
        number of cores: integer
    """
    command = 'WMIC CPU Get NumberOfCores'
    out = subprocess.check_output(command, shell=True)
    lines = out.decode('ascii').split('\n')
    number_of_cores = int(lines[1])
    return number_of_cores


def abq_versions_available(host, ssh_machine):
    """
    This function checks the versions of abaqus that are available on the current machine.

    :param host:
        [int] indicates the machine [0] is current [1, 2] are the uxcs machines
    :param ssh_machine
        [paramiko class item] ssh of host machine
    :return:
        [list of strings] available versions
    """
    available_versions = []
    if host in [2, 3, 4]:
        command = "dir /local/app/abaqus/Commands"
        _, stdout, _ = ssh_machine.exec_command(command)
        versions = stdout.read().decode('ascii').split()
        for version in versions:
            if 'abq2' in version:
                available_versions.append(version)
    if host == 0:
        out = subprocess.check_output('dir C:\SIMULIA\Commands', shell=True)
        lines = out.decode('ascii').split()
        for line_out in lines:
            if 'abq_' in line_out:
                continue
            elif 'abq' in line_out:
                available_versions.append(line_out[0:-4])
    return available_versions


def c_connect(c_host_machine, username):
    """
    This function takes care of connecting to the uxcs machine.

    :param c_host_machine:
        [string] name of the host machine
    :param username:
        [string] username
    :return:
        ssh_machine - [paramiko class item] ssh of host machine
        sftp_machine - [paramiko class item] sftp of host machine
    """
    number_of_tries = 1
    while True:
        print("--> trying to connect to %s (%i/30)" % (c_host_machine, number_of_tries))
        c_password = getpass.getpass('--> Enter password: ', sys.stderr)
        try:
            ssh_machine = paramiko.SSHClient()
            ssh_machine.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_machine.connect(c_host_machine, username=username, password=c_password)
            print("--> connected to %s" % c_host_machine)
            break
        except paramiko.AuthenticationException:
            print("--> authentication failed when connecting to %s" % c_host_machine)
            number_of_tries += 1
        except:
            print("--> could not SSH to %s, waiting for it to start" % c_host_machine)
            number_of_tries += 1
            time.sleep(2)
        if number_of_tries == 30:
            print("--> could not connect to %s. Giving up" % c_host_machine)
            sys.exit(1)
    sftp_machine = ssh_machine.open_sftp()
    time.sleep(0.5)
    print('\n-----------------------------------------------------\n')
    return ssh_machine, sftp_machine


def c_exists(sftp_machine, path):
    """
    This function checks if a given file path exists on a sftp host machine

    :param sftp_machine:
        [paramiko class item] sftp of the machine
    :param path:
        [string] path to be checked
    :return:
        [Boolean] does the path exist?
    """
    try:
        sftp_machine.stat(path)
    except IOError:
        return False
    else:
        return True


def copy_file(sftp_copy, w_path_copy, c_path_copy, file_copy):
    """
    This function copies a file to a specific location on a specific machine. I prints a statement if copying has
    failed. I also prints a progress statement.

    :param sftp_copy:
        [paramiko class item] sftp of the target machine
    :param w_path_copy:
        [string] path of the source file
    :param c_path_copy:
        [string] path of the destination file
    :param file_copy:
        [string] file to copy
    :return:
    """
    global f
    f = file_copy
    success = 0
    tries = 0
    while success == 0 and tries < 10:
        try:
            sftp_copy.put(w_path_copy + file_copy, c_path_copy + file_copy, callback=progress_percent)
            success = 1
        except IOError:
            print('----> %s not available, trying again' % file_copy)
            tries += 1
            time.sleep(5)


def progress_percent(is_done, left_todo):
    """
    This function provides a printed progress update of a copy action.

    :param is_done:
        amount of bytes done
    :param left_todo:
        amount of bytes left tot do
    :return:
        print statement with a progress update
    """
    print('---> copy {} {} %'.format(f, int((is_done/left_todo)*100)), end='\r')


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
    cosim_files = []
    for file in files(path):
        if not file.endswith('.bat') and os.path.isfile(file):
            all_files.append(file)
        if file.endswith('.xml'):
            cosim_files.append(file)
        if file.endswith('.inp'):
            abaqus_files.append(file)
    # input_files = mutate_input_files_to_runnable(input_files, path)
    ref_files = abaqus_files.copy()
    for input_file in ref_files:
        if input_file.startswith('INC_'):
            abaqus_files.remove(input_file)

    for file in all_files:
        if ' ' in file:
            print('ERROR: A space is detected in the file name %s. spaces in file names are not supported. It is '
                  'recommended to change the file name. Closing in 15 seconds.' % file)
            time.sleep(15)
            sys.exit(1)

    input_files = abaqus_files
    if len(input_files) == 0:
        print('ERROR: no runnable files found')
        time.sleep(5)
        sys.exit(1)
    if len(cosim_files) > 1:
        print('I found more than one cosim file. Something went wrong.')
        time.sleep(5)
        sys.exit(1)
    if len(input_files) >= 1:
        for file in input_files:
            print('%s is found and will be submitted.' % file)
        if len(input_files) > 1:
            print('\nA total of %i files are found, they will be submitted in batch.' % len(input_files))
    if len(set(all_files) - set(input_files)) >= 1:
        for file in set(all_files) - set(input_files):
            print('Supplementary file %s is found and will be copied, but not submitted' % file)
    subroutines = check_for_subroutines(path)
    print('\n-----------------------------------------------------\n')
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


def ask_for_priority():
    """
    This function asks the user for priority input. The correct inputs are 1 or 2 otherwise the function will give a
    warning and ask again.

    :return:
        [int] priority of the job (either 1 or 2)
    """
    job_priority = 0
    while job_priority == 0:
        try:
            job_priority = int(input('Available priority levels (only for Abaqus jobs)\n'
                                     '1 = "High priority", job will be submitted in the conventional way. Only '
                                     'use this if you need results fast, at the expanse of your colleagues.\n'
                                     '2 = "Normal priority", job will suspend itself when its tokens are '
                                     'demanded by a higher priority job, it will resume when tokens become '
                                     'available again.\n'
                                     '3 = "Evenings and weekends", will behave like priority 2 but only outside '
                                     'office hours. Job is suspended on weekdays between 07:00 and 20:00.\n'
                                     '4 = "Only weekends", behaves like priority 2 but only during weekends. '
                                     'Job is suspended during work week days.\n'
                                     '5 = "Always suspended", job is always suspended. Use this only when you '
                                     'want to pause a job mid calculation but keep NURD active.\n\n'
                                     'What level of priority do you want to use? [Default: %s]: ' % defaults[0])
                               or defaults[0])
        except ValueError:
            print('WARNING: You did not enter a correct number')
            continue
        if job_priority not in range(1, 6):
            print('WARNING: You did not enter a correct number')
            job_priority = 0
            continue
    print('\n-----------------------------------------------------\n')
    return job_priority


def choose_host(hosts):
    """
    This function asks the user for host input. The correct inputs are 0, 1 or 2 otherwise the function will give a
    warning and ask again.

    :return:
        [int] the chosen host (either 0, 1 or 2)
    """
    chosen_host = 9
    if hosts == 'all':
        while chosen_host not in [0, 2, 3, 4]:
            try:
                chosen_host = int(input('Available machines: (0 = local, 2 = uxcs02, 3 = uxcs03, 4 = uxcs04)\n\n'
                                        'Which machine do you want to use? [Default: %s]: ' % defaults[1])
                                  or defaults[1])
            except ValueError:
                print('WARNING: You did not enter a correct number')
                continue
            if chosen_host not in [0, 2, 3, 4]:
                print('WARNING: You did not enter a correct number')
                chosen_host = 9
                continue

    if hosts == 'uxcs':
        while chosen_host not in [2, 3, 4]:
            try:
                chosen_host = int(input('Available machines: (2 = uxcs02, 3 = uxcs03, 4 = uxcs04)\n\n'
                                        'Which machine do you want to use? [Default: %s]: ' % defaults[1])
                                  or defaults[1])
            except ValueError:
                print('WARNING: You did not enter a correct number')
                continue
            if chosen_host not in [2, 3, 4]:
                print('WARNING: You did not enter a correct number')
                chosen_host = 9
                continue
    print('\n-----------------------------------------------------\n')
    return chosen_host


def choose_cpus(host, abq_inps):
    """
    This function will ask for the amount of cpus to be used in the job. This is based on the number of cpus available.
    After a number is chosen the function shows the amount of tokens that are needed for the job with the chosen amount
    of tokens, and will ask for confirmation.

    If incorrect input is given the function gives a warning and asks again.

    :param host:
        [int] indicator of the host of the calculation
    :return:
        [int] the number of chosen cpus
    """
    number_of_cpus = 0
    gpu_choice = 2
    cpu_agree = 0
    if host == 0:
        # max_cores = check_number_of_cores()
        max_cores = 8
    elif host == 2:
        max_cores = 20
    elif host == 3:
        max_cores = 28
    elif host == 4:
        max_cores = 64
    else:
        max_cores = 40

    while number_of_cpus not in range(1, max_cores + 1):
        try:
            job_queued, number_of_licences, number_of_used = job_in_queue('abaqus')
            number_of_cpus = int(input('\nEnter the number of cpus to be used by the job, from the range 1-%i '
                                       '[Default: %s]: '
                                       % (max_cores, defaults[3])) or defaults[3])
        except ValueError:
            print('WARNING: You did not enter a correct number of cpus')
            continue
        if number_of_cpus > max_cores or number_of_cpus < 1:
            print('WARNING: You did not enter a correct number of cpus')
            continue
        while gpu_choice not in [0, 1]:
            try:
                gpu_choice = int(input('\nGPU acceleration can significantly reduce calculation times for large implicit '
                                       'models. It will cost 1 extra token to use it. Do you want GPU acceleration? '
                                       '(0 = NO, 1 = YES) [Default: %s]: ' % defaults[6]) or defaults[6])
            except ValueError:
                print('WARNING: You did not enter a correct choice.')
                continue
            if gpu_choice not in [0, 1]:
                print('WARNING: You did not enter a correct choice.')
                continue
        while cpu_agree == 0:
            if abq_inps:
                try:
                    print('\n-----------------------------------------------------\n')
                    if job_queued:
                        print('\nThere are jobs in the queue and %s tokens are currently available.'
                                            % (number_of_licences - number_of_used))
                    else:
                        print('\nThe queue is empty and %s tokens are currently available.'
                                            % (number_of_licences - number_of_used))
                    cpu_agree = int(
                        input('\nThis job will need %i Abaqus tokens, agreed? (0 = NO, 1 = YES) [Default: %s]: '
                              % (int(5*pow((number_of_cpus + gpu_choice), 0.422)), defaults[4])) or defaults[4])
                except ValueError:
                    print('WARNING: You did not enter a correct number')
                    continue
                if cpu_agree == 0:
                    number_of_cpus = 0
                    break
                elif cpu_agree == 1:
                    continue
                else:
                    print('WARNING: You did not enter a correct number')
                    cpu_agree = 0
            cpu_agree = 1
    print('\n-----------------------------------------------------\n')
    return number_of_cpus + gpu_choice, gpu_choice


def ask_if_zip(host):
    """
    This function asks the user if the result files should be zipped.

    :param host:
        [int] indicator of the host of the calculation
    :return:
        [int] indicator of zip action (0 or 1)
    """
    zip_odb = 2
    if host in [2, 3, 4]:
        while zip_odb not in [0, 1]:
            try:
                zip_odb = int(input('Compress files after completion? (0 = NO, 1 = YES) [Default: %s]: '
                                    % defaults[7]) or defaults[7])
            except ValueError:
                print('WARNING: You did not enter a correct number')
                continue
            if zip_odb not in [0, 1]:
                print('WARNING: You did not enter a correct number')
                zip_odb = 2
                continue
    print('\n-----------------------------------------------------\n')
    return zip_odb


def pop_the_6(element):
    """
    This function is required for proper ordering oa abaqus versions

    :param element:
    :return:
    """

    if len(element) > 3:
        if element[3] == "6":
            element = element[:3] + element[4:]
    return element


def ask_for_abaqus_version(host, ssh_machine, abaqus_versions):
    """
    This function asks the user which version of abaqus must be used in the calculation. It will check the versions of
    abaqus that are available on the host machine and list them for the user.

    :param host:
        [int] indicator of the host of the calculation
    :param ssh_machine:
        [paramiko class object] ssh of the target machine
    :param abaqus_versions:
        [list of list strings] list of the versions of abaqus with their function calls and names
    :return:
    """
    abaqus_version = 0
    while abaqus_version == 0:
        versions = abq_versions_available(host, ssh_machine)
        versions.sort(key=pop_the_6, reverse=True)
        versions_text = []
        for version in versions:
            for line in abaqus_versions:
                if line[1] == version:
                    versions_text.append(line[0])
        string = ''
        for i, version_text in enumerate(versions_text):
            string = string + str(i + 1) + ' = ' + version_text + '\n'
        string = string + '\nWhich version of abaqus do you want to use? [Default: %s]: ' % defaults[5]
        try:
            abq_version_token = int(input('Available Abaqus versions on this machine:\n'
                                          '%s' % string) or defaults[5])
        except ValueError:
            print('WARNING: You did not enter a correct number')
            continue
        if abq_version_token in range(1, len(versions) + 1):
            abaqus_version = versions[abq_version_token - 1]
            print('\nAbaqus %s is selected' % versions_text[abq_version_token - 1])
        else:
            print('WARNING: You did not enter a correct number')
            continue
    print('\n-----------------------------------------------------\n')
    return abaqus_version


def copy_files_to_host(host, c_path, w_path, s_path, subroutines, current_sftp, input_files):
    """
    This function will copy the needed files to the host machine in the dedicated folder. It will print statements on
    the success and progress of the copy action(s).

    :param host:
        [int] indicator of the host of the calculation
    :param c_path:
        [string] The current path of the destination folder
    :param w_path:
        [string] The path of the source folder for the .inp and .f files
    :param s_path:
        [string] The path of the script folder
    :param subroutines:
        [strings] The .f file to be copied
    :param current_sftp:
        [paramiko class object] sftp of the host machine
    :param input_files:
        [list of strings] The list of .inp files to be copied
    :return:
    """
    print('Copy files to %s:' % c_path)
    if host in [2, 3, 4]:
        # .inp files
        for file in input_files:
            copy_file(current_sftp, w_path, c_path, file)
            print(file + ' copied.                   ')
            time.sleep(1)
        # subroutine
        # if len(subroutines) > 0:
        #     copy_file(current_sftp, w_path, c_path, subroutines)
        #     print(subroutines + ' copied.                   ')
        #     time.sleep(1)
        # submit_uxcs.py
        copy_file(current_sftp, s_path, c_path, 'NURD_uxcs.py')
        print('NURD_uxcs.py' + ' copied.                   ')
    elif host in [0]:
        # .inp files
        for file in input_files:
            shutil.copyfile(w_path + file, c_path + file)
            print(file + ' copied.                   ')
            time.sleep(1)
        # subroutine
        # if len(subroutines) > 0:
        #     shutil.copyfile(w_path + subroutines, c_path + subroutines)
        #     print(subroutines + ' copied.                   ')
        #     time.sleep(1)
        # submit_uxcs.py
        shutil.copyfile(s_path + 'NURD_uxcs.py', c_path + 'NURD_uxcs.py')
        print('NURD_uxcs.py' + ' copied.                   ')


def submit_jobs(host, current_ssh, current_path, number_of_cpus, zip_odb, job_priority, abaqus_version, gpu_choice,
                current_sftp, mail_choice):
    """
    This function submits the jobs to the host machine by starting submit_uxcs.py on the target machine.

    :param host:
        [int] indicator of the host of the calculation
    :param current_ssh:
        [paramiko class object] ssh of the target machine
    :param current_path:
        [string] path on the target machine with all the files
    :param number_of_cpus:
        [int] the chosen number of cpus for the job
    :param zip_odb:
        [int] 1 if the files are to be zipped afterwards, 0 if not.
    :param job_priority:
        [int] priority indicator of the job
    :param abaqus_version:
        [string] function call for the desired abaqus version
    :param current_sftp:
        [paramiko class object] sftp of the host machine
    :param gpu_choice:
        [int] holds the choice for gpu acceleration
    :return:
    """

    mail_adress = subprocess.check_output('whoami /upn', shell=True).decode('ascii').split()[0]
    if host in [2, 3, 4]:
        print('\nSubmit jobs')
        channel = current_ssh.invoke_shell()
        channel.send('cd %s\n' % current_path)
        time.sleep(5)
        run_command = 'nohup python3 NURD_uxcs.py %i %i %i %s %s %s %i > NURD.log \n' % (number_of_cpus, zip_odb,
                                                                                         job_priority, abaqus_version,
                                                                                         gpu_choice, mail_adress,
                                                                                         mail_choice)
        done = 0
        while done == 0:
            channel.send(run_command)
            time.sleep(5)
            try:
                current_sftp.stat(current_path + 'NURD.log')
                done = 1
            except:
                done = 0
    if host == 0:
        print('\nSubmit jobs, do not close this window!')
        os.system('cd %s\n' % current_path)
        time.sleep(5)
        done = 0
        while done == 0:
            os.chdir(current_path)
            print('"' + sys.executable + '"')
            os.system('%s NURD_uxcs.py %i %i %i %s %s %s %i > NURD.log' % ('"' + sys.executable + '"', number_of_cpus, zip_odb, job_priority,
                                                                           abaqus_version, gpu_choice,
                                                                           mail_adress, mail_choice))
            done = 1


def check_cpu_usage(host, ssh):
    """
    This function checks the usage of the cpus on the target machine and prints the information for the user.

    :param host:
        [int] indicator of the host of the calculation
    :param ssh:
        [paramiko class object] ssh of the target machine
    :return:
    """
    machine_names = ['local machine', "uxcs01", 'uxcs02', 'uxcs03', 'uxcs04']

    machine_name = machine_names[host]
    choose_another = 1
    if host == 0:
        out = subprocess.check_output('wmic cpu get loadpercentage', shell=True)
        usage = round(float(out.decode('ascii').split('\n')[1]))
        print('CPU usage for your local machine is %.1f%%.' % usage)
        choose_another = int(input('\nDo you want to choose another host machine? (1 = YES, 0 = NO) '
                               '[Default: %s]: ' %
                               defaults[2]) or defaults[2])
    if host in [2, 3, 4]:
        command = "mpstat 1 1"
        stdin, stdout, stderr = ssh.exec_command(command)
        usage = round(100 - float(stdout.read().decode('ascii').split()[-1]), 1)
        if 0 <= usage < 70:
            print('CPU usage for %s is %.1f%%. There is enough CPU power available for this job.' % (
            machine_name, usage))
            choose_another = 0
        # elif 70 <= usage < 50:
        #     print('CPU usage for %s is %.1f%%. This machine is close to multithreading, you might want to choose '
        #           'another machine if you are running a large job.' % (machine_name, usage))
        #     choose_another = int(input('\nDo you want to choose another host machine? (1 = YES, 0 = NO) '
        #                                '[Default: %s]: ' %
        #                                defaults[2]) or defaults[2])
        else:
            print('CPU usage for %s is %.1f%%. This machine is close to maximum capacity. '
                  'Consider choosing another machine.' % (machine_name, usage))
            choose_another = int(input('\nDo you want to choose another host machine? (1 = YES, 0 = NO) '
                                       '[Default: %s]: ' %
                                       defaults[2]) or defaults[2])
    return choose_another


def create_directory_string(base_path):
    """
    This function creates a string for a folder.

    :param base_path:
        [string] base path for the folder name
    :return:
        [string] complete string for the folder
    """
    now = datetime.datetime.now()
    date = '%i-%02d-%02d-%02d%02d' % (now.year, now.month, now.day, now.hour, now.minute)
    directory_string = base_path + '/NURD-' + date + '/'
    return directory_string


def make_directory(host, sftp_machine, c_base, w_path, ssh_machine):
    """
    This function makes a directory on the host machine for the calculation to be done.

    :param host:
        [string] base path for the folder name
    :param sftp_machine:
        [paramiko class object] sftp of the host machine
    :param c_base:
        [string] The current path base of the destination folder
    :param w_path:
        [string] The path of the source folder for the .inp and .f files
    :param ssh_machine:
        [paramiko class object] SSH of the host machine
    :return:
        [string] The current path of the files to be calculated
    """
    current_path = ''
    if host in [2, 3, 4]:
        current_path = create_directory_string(c_base)
        # make sure path does not exist
        while c_exists(sftp_machine, current_path):
            print('--> wait for unique path in: ' + c_base)
            time.sleep(5)
            current_path = create_directory_string(c_base)
        # create output path on cluster
        ssh_machine.exec_command('mkdir %s' % current_path)
        time.sleep(2)
    elif host in [0]:
        current_path = create_directory_string(w_path)
        while os.path.exists(current_path):
            print('--> wait for unique path in: ' + w_path)
            time.sleep(5)
            current_path = create_directory_string(w_path)
        os.mkdir(current_path)
        time.sleep(2)
    return current_path


def make_defined_directory(host, sftp_machine, c_base, w_path, ssh_machine, dir):
    """
    This function makes a directory on the host machine for the calculation to be done.

    :param host:
        [string] base path for the folder name
    :param sftp_machine:
        [paramiko class object] sftp of the host machine
    :param c_base:
        [string] The current path base of the destination folder
    :param w_path:
        [string] The path of the source folder for the .inp and .f files
    :param ssh_machine:
        [paramiko class object] SSH of the host machine
    :return:
        [string] The current path of the files to be calculated
    """
    current_path = ''
    if host in [2, 3, 4]:
        current_path = c_base + "/" + dir + "/"
        # make sure path does not exist
        while c_exists(sftp_machine, current_path):
            print('--> wait for unique path in: ' + c_base)
            time.sleep(5)
            current_path = c_base + "/" + dir + "/"
        # create output path on cluster
        ssh_machine.exec_command('mkdir %s' % current_path)
        time.sleep(2)
    elif host in [0]:
        current_path = w_path + "/" + dir + "/"
        while os.path.exists(current_path):
            print('--> wait for unique path in: ' + w_path)
            time.sleep(5)
            current_path = w_path + "/" + dir + "/"
        os.mkdir(current_path)
        time.sleep(2)
    return current_path


# def ask_for_esi_version(esi_files):
#     esi_rtm_version = 0
#     for file in esi_files:
#         if file.endswith('.vdb'):
#             versions = ['ESI-PAM RTM 2019.5', 'ESI-PAM RTM 2020.5', 'ESI-PAM RTM 2020.6']
#             while esi_rtm_version == 0:
#                 try:
#                     esi_rtm_version = int(input('Which version of ESI-PAM RTM do you want to use?\n'
#                                                 '(1 = ESI-PAM RTM 2019.5, 2 = ESI-PAM RTM 2020.5, '
#                                                 '3 = ESI-PAM RTM 2020.6) [Default: %s]: '
#                                                 % defaults[6]) or defaults[6])
#                 except ValueError:
#                     print('WARNING: You did not enter a correct number')
#                     continue
#                 if esi_rtm_version in [1, 2, 3]:
#                     esi_rtm_version_text = versions[esi_rtm_version - 1]
#                     print('\n%s is selected' % esi_rtm_version_text)
#                 else:
#                     print('WARNING: You did not enter a correct number')
#                     continue
#     return esi_rtm_version


def ask_if_mail():
    mail = 1
    print('You will receive an email when the job is finished, and an update every 24 hours while NURD is running')
    # while mail not in [0, 1]:
    #     try:
    #         mail = int(input('Would you like to receive an email when the job(s) is/are finished? (0 = NO, 1 = YES) '
    #                          '[Default: %s]: ' % defaults[8]) or defaults[8])
    #     except ValueError:
    #         print('WARNING: You did not enter a correct number')
    #         continue
    #     if mail not in [0, 1]:
    #         print('WARNING: You did not enter a correct number')
    #         zip_odb = 2
    #         continue
    print('\n-----------------------------------------------------\n')
    return mail


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
        command = 'abaqus licensing lmstat -c ' + lic + ' -f ' + feature
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



def run_input_sequence(s_path, w_path, c_base, abq_versions):
    """
    This function will run the sequence of functions to initiate the calculation.

    :param s_path:
        [string] path of the script files
    :param w_path:
        [string] path of the .inp and .f files
    :param c_base:
        [string] base of the source destination
    :param abq_versions:
        [string] base of the source destination
    :return:
    """
    ssh = None
    sftp = None
    abq_version = 0
    unused = 0

    if __stable__==True:
        print("""
    ***************************************
    **   _   _  _    _  _____   _____    ** 
    **  | \ | || |  | ||  __ \ |  __ \   **
    **  |  \| || |  | || |__) || |  | |  **
    **  | . ` || |  | ||  _  / | |  | |  **
    **  | |\  || |__| || | \ \ | |__| |  **
    **  |_| \_|\______/|_|  \_\|_____/   **
    **                                   **
    **    NLR  UXCS  Remote  Delegator   **
    **            Version 2.3            **
    **                                   **
    ***************************************""")
        print('\n-----------------------------------------------------\n')
    else:
        print("""
     _   _ _    _ _____  _____    _          _        
    | \ | | |  | |  __ \|  __ \  | |        | |       
    |  \| | |  | | |__) | |  | | | |__   ___| |_ __ _ 
    | . ` | |  | |  _  /| |  | | | '_ \ / _ \ __/ _` |
    | |\  | |__| | | \ \| |__| | | |_) |  __/ || (_| |
    |_| \_|\____/|_|  \_\_____/  |_.__/ \___|\__\__,_|
                                                    
    WARNING: This version (2.3) may contain bugs.""")
        print('\n-----------------------------------------------------\n')

    abaqus_files, all_files, subroutines = search_for_input_files(w_path)

    if len(abaqus_files) > 0:
        job_prio = ask_for_priority()
    else:
        job_prio = 1

    host_agree = 1
    while host_agree == 1:
        c_host = choose_host('uxcs')

        if c_host in [2, 3, 4]:
            ssh, sftp = c_connect('uxcs0' + str(c_host), c_username)
        host_agree = check_cpu_usage(c_host, ssh)

    n_cpus, gpu_choice = choose_cpus(c_host, abaqus_files)

    if len(abaqus_files) > 0:
        abq_version = ask_for_abaqus_version(c_host, ssh, abq_versions)

    odb_zip = ask_if_zip(c_host)

    mail_choice = ask_if_mail()

    c_path = make_directory(c_host, sftp, c_base, w_path, ssh)

    copy_files_to_host(c_host, c_path, w_path, s_path, subroutines, sftp, all_files)

    submit_jobs(c_host, ssh, c_path, n_cpus, odb_zip, job_prio, abq_version, gpu_choice, sftp, mail_choice)

    input("--> Done, press enter to close...")


def run_nohup_sequence(s_path, w_path, c_base, abq_versions, folder_name, defaults):
    """
    This function will run the sequence of functions to initiate the calculation.

    :param s_path:
        [string] path of the script files
    :param w_path:
        [string] path of the .inp and .f files
    :param c_base:
        [string] base of the source destination
    :param abq_versions:
        [string] base of the source destination
    :return:
    """
    ssh = None
    sftp = None
    abq_version = 0

    abaqus_files, all_files, subroutines = search_for_input_files(w_path)

    c_host = int(defaults[1])
    n_cpus = int(defaults[3])
    odb_zip = int(defaults[7])
    job_prio = int(defaults[0])
    abq_version = defaults[5]
    gpu_choice = int(defaults[6])
    mail_choice = int(defaults[8])

    if c_host in [2, 3, 4]:
        print("connecting")
        ssh, sftp = c_connect('uxcs0' + str(c_host), c_username)

    print(ssh, sftp)

    c_path = make_defined_directory(c_host, sftp, c_base, w_path, ssh, folder_name)

    copy_files_to_host(c_host, c_path, w_path, s_path, subroutines, sftp, all_files)

    submit_jobs(c_host, ssh, c_path, n_cpus, odb_zip, job_prio, abq_version, gpu_choice, sftp, mail_choice)


if __name__ == "__main__":
    abq_versions = [
        ['2027_6.27-7', 'abq2027hf6'],
        ['2027_6.27-6', 'abq2027hf5'],
        ['2027_6.27-5', 'abq2027hf4'],
        ['2027_6.27-4', 'abq2027hf3'],
        ['2027_6.27-3', 'abq2027hf2'],
        ['2027_6.27-2', 'abq2027hf1'],
        ['2027_6.27-1', 'abq2027'],
        ['2026_6.26-7', 'abq2026hf6'],
        ['2026_6.26-6', 'abq2026hf5'],
        ['2026_6.26-5', 'abq2026hf4'],
        ['2026_6.26-4', 'abq2026hf3'],
        ['2026_6.26-3', 'abq2026hf2'],
        ['2026_6.26-2', 'abq2026hf1'],
        ['2026_6.26-1', 'abq2026'],
        ['2025_6.25-7', 'abq2025hf6'],
        ['2025_6.25-6', 'abq2025hf5'],
        ['2025_6.25-5', 'abq2025hf4'],
        ['2025_6.25-4', 'abq2025hf3'],
        ['2025_6.25-3', 'abq2025hf2'],
        ['2025_6.25-2', 'abq2025hf1'],
        ['2025_6.25-1', 'abq2025'],
        ['2024_6.24-3', 'abq2024hf6'],
        ['2024_6.24-3', 'abq2024hf5'],
        ['2024_6.24-3', 'abq2024hf4'],
        ['2024_6.24-3', 'abq2024hf3'],
        ['2024_6.24-3', 'abq2024hf2'],
        ['2024_6.24-2', 'abq2024hf1'],
        ['2024_6.24-1', 'abq2024'],
        ['2023_6.23-4', 'abq2023hf3'],
        ['2023_6.23-3', 'abq2023hf2'],
        ['2023_6.23-2', 'abq2023hf1'],
        ['2023_6.23-1', 'abq2023'],
        ['2022_6.22-9', 'abq2022hf8'],
        ['2022_6.22-8', 'abq2022hf7'],
        ['2022_6.22-7', 'abq2022hf6'],
        ['2022_6.22-6', 'abq2022hf5'],
        ['2022_6.22-5', 'abq2022hf4'],
        ['2022_6.22-4', 'abq2022hf3'],
        ['2022_6.22-3', 'abq2022hf2'],
        ['2022_6.22-2', 'abq2022hf1'],
        ['2022_6.22-1', 'abq2022'],
        ['2021_6.21-9', 'abq2021hf8'],
        ['2021_6.21-8', 'abq2021hf7'],
        ['2021_6.21-7', 'abq2021hf6'],
        ['2021_6.21-6', 'abq2021hf5'],
        ['2021_6.21-5', 'abq2021hf4'],
        ['2021_6.21-4', 'abq2021hf3'],
        ['2021_6.21-3', 'abq2021hf2'],
        ['2021_6.21-2', 'abq2021hf1'],
        ['2021_6.21-1', 'abq2021'],
        ['2020_6.20-9', 'abq2020hf8'],
        ['2020_6.20-8', 'abq2020hf7'],
        ['2020_6.20-7', 'abq2020hf6'],
        ['2020_6.20-6', 'abq2020hf5'],
        ['2020_6.20-5', 'abq2020hf4'],
        ['2020_6.20-4', 'abq2020hf3'],
        ['2020_6.20-3', 'abq2020hf2'],
        ['2020_6.20-2', 'abq2020hf1'],
        ['2020_6.20-1', 'abq2020'],
        ['2019_6.19-5', 'abq2019hf4'],
        ['2019_6.19-4', 'abq2019hf3'],
        ['2019_6.19-3', 'abq2019hf2'],
        ['2019_6.19-2', 'abq2019hf1'],
        ['2019_6.19-1', 'abq2019'],
        ['2018_6.18-1', 'abq2018'],
        ['2017_6.17-1', 'abq2017'],
        ['2016_6.16-1', 'abq2016'],
        ['6.14-5', 'abq6145'],
        ['6.14-4', 'abq6144'],
        ['6.14-3', 'abq6143'],
        ['6.14-2', 'abq6142'],
        ['6.14-1', 'abq6141'],
        ['6.13-4', 'abq6134'],
        ['6.13-3', 'abq6133'],
        ['6.13-2', 'abq6132'],
        ['6.13-1', 'abq6131'],
        ['6.12-3', 'abq6123'],
        ['6.12-2', 'abq6122'],
        ['6.12-1', 'abq6121']
    ]

    try:
        defaults = sys.argv[4]
    except IndexError:
        defaults = "2 2 0 8 1 1 0 0 0"

    defaults = defaults.split(" ")

    c_username = sys.argv[2]
    c_pool = sys.argv[3]
    script_path = os.path.dirname(os.path.realpath(__file__)) + os.sep  # script path
    working_path = sys.argv[1] + os.sep  # working path
    current_base = '/shared/home/nlr/%s' % (c_username)  # cluster home path
    if c_username == "vroon":
        current_base = '/shared/home/nlr/%s/NO_BACKUP' % (c_username)  # cluster home path

    try:
        folder_name = sys.argv[5]
        run_nohup_sequence(script_path, working_path, current_base, abq_versions, folder_name, defaults)
    except:
        run_input_sequence(script_path, working_path, current_base, abq_versions)
