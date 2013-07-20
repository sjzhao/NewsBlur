#!/usr/bin/env python

import os
import time
import select
import subprocess
import sys
from requests.exceptions import ConnectionError

sys.path.insert(0, '/srv/newsblur')
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import fabfile

IGNORE_HOSTS = [
    'push',
]

def main(role="app", role2="work", command=None, path=None):
    delay = 1

    while True:
        try:
            streams = create_streams_for_roles(role, role2, command=command, path=path)
            print " --- Loading %s App Log Tails ---" % len(streams)
            read_streams(streams)
        except UnicodeDecodeError: # unexpected end of data
            print " --- Lost connections - Retrying... ---"
            time.sleep(1)
            continue
        except ConnectionError:
            print " --- Retrying in %s seconds... ---" % delay
            time.sleep(delay)
            delay += 1
            continue
        except KeyboardInterrupt:
            print " --- End of Logging ---"
            break

def create_streams_for_roles(role, role2, command=None, path=None):
    streams = list()
    hosts = fabfile.do(split=True)
    found = set()

    if not path:
        path = "/srv/newsblur/logs/newsblur.log"
    if not command:
        command = "tail -f"
    for hostname in (hosts[role] + hosts[role2]):
        if isinstance(hostname, dict):
            address = hostname['address']
            hostname = hostname['name']
        elif ':' in hostname:
            hostname, address = hostname.split(':', 1)
        elif isinstance(hostname, tuple):
            hostname, address = hostname[0], hostname[1]
        else:
            address = hostname
        if any(h in hostname for h in IGNORE_HOSTS): continue
        if hostname in found: continue
        if 'ec2' in hostname:
            s = subprocess.Popen(["ssh", "-i", os.path.expanduser("~/.ec2/sclay.pem"), 
                                  address, "%s %s" % (command, path)], stdout=subprocess.PIPE)
        else:
            s = subprocess.Popen(["ssh", address, "%s %s" % (command, path)], stdout=subprocess.PIPE)
        s.name = hostname
        streams.append(s)
        found.add(hostname)
        
    return streams

def read_streams(streams):
    while True:
        r, _, _ = select.select(
            [stream.stdout.fileno() for stream in streams], [], [])
        for fileno in r:
            for stream in streams:
                if stream.stdout.fileno() != fileno:
                    continue
                data = os.read(fileno, 4096)
                if not data:
                    streams.remove(stream)
                    break
                combination_message = "[%-6s] %s" % (stream.name[:6], data)
                sys.stdout.write(combination_message)
                break

if __name__ == "__main__":
    main(*sys.argv[1:])
