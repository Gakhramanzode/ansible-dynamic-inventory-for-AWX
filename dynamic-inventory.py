#!/usr/bin/env python
import json
import re
import requests
import yaml
import configparser
import os

with open('inventories/my-project/group_vars/all/vars.yml', 'r') as file:
    variables = yaml.safe_load(file)

# Replace these values with your own
GITLAB_TOKEN = os.environ['gitlab_private_token']
GITLAB_URL = variables['gitlab_url']
PROJECT_ID = variables['project_id']
INVENTORY_FILE_PATH = variables['inventory_file_path']
HOST_VARS_PATH = variables['host_vars_path']
BRANCH_NAME =  variables['branch_name']

# Creating a URL for a request to the GitLab API
url = f'{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/repository/commits'
params = {
    'private_token': GITLAB_TOKEN,
    # Uncomment for testing
    # 'path': HOST_VARS_PATH,
    'ref_name': BRANCH_NAME,
    # Setting the number of results per page
    'per_page': 100,
    # Setting the page number
    'page': 1,
}

all_data = []

while True:
    # Getting commit data from GitLab
    response = requests.get(url, params=params)
    data = response.json()
    all_data.extend(data)

    if "next" not in response.links:
        break

    params["page"] += 1

# We leave only the last commit in the list
all_data = all_data[:1]

# Initialize a variable to store the changed hosts
changed_hosts = set()

# Processing each commit in the list
for commit in all_data:
    # We receive data about changes in the commit
    url = f'{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/repository/commits/{commit["id"]}/diff'
    params = {
        'private_token': GITLAB_TOKEN,
        # Setting the number of results per page
        'per_page': 100,
        # Setting the page number
        'page': 1,
    }
    response = requests.get(url, params=params)
    changes = response.json()

    all_changes = []

    while True:
        response = requests.get(url, params=params)
        changes = response.json()
        all_changes.extend(changes)

        if "next" not in response.links:
            break

        params["page"] += 1

    # Looking for changes in the host_vars directory
    for change in all_changes:
        if change['new_path'].startswith(HOST_VARS_PATH):
            # Extract the folder name from the file path
            folder_name = change['new_path'].split('/')[-2]
            # Adding the folder name to the list of changed hosts
            changed_hosts.add(folder_name)

config = configparser.ConfigParser(allow_no_value=True)
config.read('inventories/my-project/hosts.ini')

def get_parent_changed_hosts(changed_hosts, config):
    # Initialize the dictionary to save the group name for each host
    host_groups = {}

    # Pass through all sections in the file
    for section in config.sections():
        # Checking whether a section is a host group
        if ':children' not in section:
            # Passage by all parameters in the section
            for option in config.options(section):
                # Getting the host name from the parameter
                host = option.split()[0]
                # Saving group information for the host
                host_groups[host] = section

    # Initialize the dictionary to store the parent group for each group
    parent_groups = {}

    # Pass through all sections in the file
    for section in config.sections():
        # Checking whether a section is a parent group
        if ':children' in section:
            # Getting the name of the parent group from the section name
            parent_group_name = section.split(':')[0]
            # Passage by all parameters in the section
            for option in config.options(section):
                # Getting the group name from a parameter
                group = option.strip()
                # Checking if there is such a group in the host_groups dictionary
                if group in host_groups.values():
                    # Saving parent group information for a group
                    parent_groups[group] = parent_group_name

    # Initialize the dictionary to store the changed hosts for each parent group
    parent_changed_hosts = {}

    # Grouping the modified hosts by their parent group
    for host in changed_hosts:
        # Getting the name of the parent group for this host
        parent_group = parent_groups.get(host_groups.get(host))
        if parent_group is not None:
            # Adding this host to the list of changed hosts for this parent group
            if parent_group not in parent_changed_hosts:
                parent_changed_hosts[parent_group] = []
            parent_changed_hosts[parent_group].append(host)

    return parent_changed_hosts

# Uncomment for testing
# Initialize a variable to store the changed hosts
# changed_hosts = set()

if not changed_hosts:
    # Initialize the set to store all hosts
    all_hosts = set()
    # Pass through all sections in the file
    for section in config.sections():
        # Checking whether a section is a host group
        if ':children' not in section:
            # Passage by all parameters in the section
            for option in config.options(section):
                # Getting the host name from the parameter
                host = option.split()[0]
                # Adding a host to a set
                all_hosts.add(host)
    changed_hosts = all_hosts
    parent_changed_hosts = get_parent_changed_hosts(changed_hosts, config)
else:
    parent_changed_hosts = get_parent_changed_hosts(changed_hosts, config)

# Creating a dictionary to store information about host parameters
host_vars = {}

# Function for converting a string to the corresponding value
def parse_value(value):
    if value.lower() == 'true':
        return True
    elif value.lower() == 'false':
        return False
    elif value.isdigit():
        return int(value)
    else:
        try:
            return float(value)
        except ValueError:
            return value

# Pass through all sections in the file
for section in config.sections():
    # Checking whether a section is a host group
    if ':children' not in section:
        # Passage by all parameters in the section
        for option in config.options(section):
            # Getting the host name from the parameter
            host = option.split()[0]
            # Checking whether this host is changed
            if host in changed_hosts:
                # Getting the parameter value
                value = config.get(section, option)
                # Saving parameter information for the host
                if value is not None:
                    if host not in host_vars:
                        host_vars[host] = {}
                    # Using only the parameter name without the hostname
                    option_parts = option.split('=')[0].split()
                    if len(option_parts) > 1:
                        param_name = option_parts[1].strip()
                    else:
                        param_name = option_parts[0].strip()
                    # Splitting the value into separate parameters
                    value_parts = re.split(r'\s+#\s+', value)[0].split()
                    for value_part in value_parts:
                        if '=' in value_part:
                            param_name, param_value = value_part.split('=', 1)
                            host_vars[host][param_name.strip()] = parse_value(param_value.strip())
                        else:
                            host_vars[host][param_name] = parse_value(value_part.strip())


# Updating dynamic inventory data
inventory = {
    "_meta": {
        "hostvars": host_vars
    },
    "all": {
        "children": list(parent_changed_hosts.keys())
    }
}

# Initialize the dictionary to save the group name for each host
host_groups = {}

# Pass through all sections in the file
for section in config.sections():
    # Checking whether a section is a host group
    if ':children' not in section:
        # Passage by all parameters in the section
        for option in config.options(section):
            # Getting the host name from the parameter
            host = option.split()[0]
            # Saving group information for the host
            host_groups[host] = section

for parent_group, hosts in parent_changed_hosts.items():
    inventory[parent_group] = {
        "children": []
    }
    for host in hosts:
        group = host_groups.get(host)
        if group not in inventory[parent_group]["children"]:
            inventory[parent_group]["children"].append(group)
        if group not in inventory:
            inventory[group] = {
                "hosts": []
            }
        inventory[group]["hosts"].append(host)

# Output data in JSON format
print(json.dumps(inventory))
