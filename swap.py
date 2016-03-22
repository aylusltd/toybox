#!/usr/bin/env python

# Copyright 2016 Datawire. All rights reserved.

"""swap.py

Performs the green/blue infrastructure swap.

Usage:
    swap.py [-n] start <image-id>
    swap.py [-n] finish
    swap.py [-n] abort
    swap.py status

    swap.py (-h | --help)
    swap.py --version

Options:
    -n                              Dry run.
    --version                       Show the version.
"""

import sys

#import colorama
#import boto3
import json
import logging
import os
import shlex
import shutil
import subprocess

from docopt import docopt

from datawire.utils.state import DataWireState, DataWireError

#    autoscaling = boto3.client('autoscaling', tfvars['region'])

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter('--->  %(levelname)s: %(name)s - %(asctime)s - %(message)s'))

logger = logging.getLogger('swap')
logger.addHandler(ch)

SCALING_PROCESSES = ['Launch', 'Terminate', 'HealthCheck', 'ReplaceUnhealthy', 'AZRebalance', 'AlarmNotification',
                     'ScheduledActions', 'AddToLoadBalancer']

def is_deployed(service_name):
    logger.info()
    pass


def run_command(command, show_output=False):
    process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
    result = ""
    while process.poll() is None:
        line = str.encode(process.stdout.readline(), 'utf-8').strip()
        result += line + "\n"
        if show_output:
            print(" | " + line)

    return process.poll(), result.strip()

def terraform_output(output_name):
    exit_code, out = run_command("terraform output {}".format(output_name))
    return out.strip()

def terraform_plan(args, planfile):
    code = 0
    result = '(not run)'

    if not args.get('-n', False):
        cmd = 'terraform plan -detailed-exitcode -out={}'.format(planfile)

        code, result = run_command(cmd, show_output=True)

    return code        

def terraform_apply(args, planfile):
    code = 0
    result = '(not run)'

    if not args.get('-n', False):
        code, result = run_command("terraform apply {}".format(planfile),
                                   show_output=True)

    print("CODE {}".format(code))
    # print("RESULT {}".format(result))
    return code

def terraform_check_apply(args):
    if args.get('-n', False):
        print("Not actually applying")
        return 0

    code = terraform_plan(args, "/tmp/swap.plan")

    if code == 0:
        print("No changes to apply")
        dwState.smite()
    elif code == 2:
        while True:
            sys.stdout.write("Continue? ")
            sys.stdout.flush()

            onward = sys.stdin.readline().strip()

            if onward.startswith('y') or onward.startswith('Y'):
                return terraform_apply(args, "/tmp/swap.plan")
            elif onward.startswith('n') or onward.startswith('N'):
                return 1

    return code

def set_color(tfvars, new_color):
    print("setting future color (color: {})".format(new_color))
    tfvars['color'] = new_color

def set_image(tfvars, color, image_id):
    print("setting future color image ID (color: {}, image: {})".format(color, image_id))
    tfvars['{}_image_id'.format(color)] = image_id

def get_cluster_min_and_max(tfvars, color):
    return (int(tfvars['{}_cluster_min_size'.format(color)]),
            int(tfvars['{}_cluster_max_size'.format(color)]))

def set_cluster_min_and_max(tfvars, color, minimum, maximum):
    print("setting future color cluster capacity (color: {}, capacity: {}..{})".format(color, minimum, maximum))
    tfvars['{}_cluster_min_size'.format(color)] = minimum
    tfvars['{}_cluster_max_size'.format(color)] = maximum

def swap_status(dwState, args):
    print(dwState.toJSON())

def swap_start(dwState, args):
    if 'future_color' in dwState:
        print("""
A swap to {} is already active. Use 'swap finish' to complete the swap or
'swap abort' to cancel it.""".format(dwState['future_color']))
        return 1

    # Grab terraform.tfvars...
    tfvars = {}
    with open('terraform.tfvars') as file:
        tfvars = json.load(file)

#    current_color = terraform_output('color')
    current_color = tfvars.get('color', None)

    if not current_color:
        print("Deployment is not live")
        return 1

    future_color = None

    if current_color == 'blue':
        future_color = 'green'
    elif current_color == 'green':
        future_color = 'blue'

    if not future_color:
        print("Not sure what comes after color {}".format(current_color))
        return 1

    current_image = tfvars['{}_image_id'.format(current_color)]
    future_image = args['<image-id>']

    if current_image == future_image:
        print("swap not needed because images are same (current: {}, future: {})".format(current_image, future_image))
        return 1

    # OK. Save info about the current swap.
    dwState['current_color'] = current_color
    dwState['future_color'] = future_color
    dwState['current_image'] = current_image
    dwState['future_image'] = future_image

    if not args.get('-n', False):
        dwState.save()

        if dwState.dirty:
            print("ABORTING, cannot save current swap information")
            return 1

    # Update info in tfvars...
    set_color(tfvars, future_color)
    set_image(tfvars, future_color, future_image)

    current_min, current_max = get_cluster_min_and_max(tfvars, current_color)
    print("{} counts: {}..{}".format(current_color, current_min, current_max))

    set_cluster_min_and_max(tfvars, future_color, current_min, current_max)

    print("writing backup configuration")

    if not args.get('-n', False):
        shutil.copyfile('terraform.tfvars', 'terraform.tfvars.bak')
        with open('terraform.tfvars', 'w') as file:
            json.dump(tfvars, file, indent=2, sort_keys=True)

    return terraform_check_apply(args)

def swap_finish(dwState, args):
    if 'current_color' not in dwState:
        print("No swap is currently active. Use 'swap start' to start one.")
        return 1

    # Grab terraform.tfvars...
    tfvars = {}
    with open('terraform.tfvars') as file:
        tfvars = json.load(file)

    current_color = dwState['current_color']

    set_cluster_min_and_max(tfvars, current_color, 0, 0)

    print("writing backup configuration")

    if not args.get('-n', False):
        shutil.copyfile('terraform.tfvars', 'terraform.tfvars.bak')
        with open('terraform.tfvars', 'w') as file:
            json.dump(tfvars, file, indent=2, sort_keys=True)

    status = terraform_check_apply(args)

    if not args.get('-n', False):
        if status == 0:
            dwState.smite()

    return status

def swap_abort(dwState, args):
    if 'future_color' not in dwState:
        print("No swap is currently active. Use 'swap start' to start one.")
        return 1

    # Grab terraform.tfvars...
    tfvars = {}
    with open('terraform.tfvars') as file:
        tfvars = json.load(file)

    future_color = dwState['future_color']
    current_color = dwState['current_color']
    current_image = dwState['current_image']

    set_cluster_min_and_max(tfvars, future_color, 0, 0)
    set_image(tfvars, future_color, current_image)
    set_color(tfvars, current_color)

    print("writing backup configuration")

    if not args.get('-n', False):
        shutil.copyfile('terraform.tfvars', 'terraform.tfvars.bak')
        with open('terraform.tfvars', 'w') as file:
            json.dump(tfvars, file, indent=2, sort_keys=True)


    status = terraform_check_apply(args)

    if not args.get('-n', False):
        dwState.smite()

    return status

def main():
    args = docopt(__doc__, version="swap {0}".format("1.0"))

    dwState = DataWireState(os.path.join(os.path.expanduser('~'), '.datawire', 'swap.json'))

    # print(args)

    if args.get('start', False):
        return swap_start(dwState, args)
    elif args.get('finish', False):
        return swap_finish(dwState, args)
    elif args.get('abort', False):
        return swap_abort(dwState, args)
    elif args.get('status', False):
        return swap_status(dwState, args)
    else:
        print("No command given??")

if __name__ == "__main__":
    try:
#        colorama.init()
        sys.exit(main())
    finally:
#        colorama.deinit()
        pass

