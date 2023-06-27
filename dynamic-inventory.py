#!/usr/bin/env python
import json
import os
import re
import requests
import base64
import yaml

with open('inventories/my-project/group_vars/all/my-role.yml', 'r') as file:
    variables = yaml.safe_load(file)

# Заменить эти значения на свои
GITLAB_TOKEN = variables['my_role_gitlab_private_token']
GITLAB_URL = variables['gitlab_url']
PROJECT_ID = variables['project_id']
INVENTORY_FILE_PATH = variables['inventory_file_path']
HOST_VARS_PATH = variables['host_vars_path']
BRANCH_NAME =  variables['branch_name']

# Формируем URL для запроса к API GitLab
url = f'{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/repository/commits'
params = {
    'private_token': GITLAB_TOKEN,
    # Раскомментировать для теста
    # 'path': HOST_VARS_PATH,
    'ref_name': BRANCH_NAME,
}

# Получаем данные о коммитах из GitLab
response = requests.get(url, params=params)
data = response.json()
# print(data)

# Оставляем только два последних коммита в списке
data = data[:2]
# print(data)

# Инициализируем переменную для хранения измененных хостов
changed_hosts = set()

# Обрабатываем каждый коммит в списке
for commit in data:
    # Получаем данные о изменениях в коммите
    url = f'{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/repository/commits/{commit["id"]}/diff'
    params = {
        'private_token': GITLAB_TOKEN,
    }
    response = requests.get(url, params=params)
    changes = response.json()

    # Ищем изменения в каталоге host_vars
    for change in changes:
        if change['new_path'].startswith(HOST_VARS_PATH):
            # Извлекаем имя папки из пути к файлу
            folder_name = change['new_path'].split('/')[-2]
            # Добавляем имя папки в список измененных хостов
            changed_hosts.add(folder_name)

# Формируем URL для запроса к API GitLab
url = f'{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/repository/files/inventories%2Fmy-project%2Fhosts.ini?ref={BRANCH_NAME}'
headers = {
    'PRIVATE-TOKEN': GITLAB_TOKEN,
}

# Получаем содержимое файла инвентаря из GitLab
response = requests.get(url, headers=headers)
# Получаем JSON-объект вместо текста
inventory_data = response.json()
# print(inventory_data)

# Декодируем содержимое файла из base64 в строку
# Получаем поле content из JSON-объекта
content = inventory_data["content"]
# Декодируем содержимое из base64
decoded = base64.b64decode(content)
# Преобразуем байты в строку с кодировкой utf-8
inventory_string = decoded.decode("utf-8")

def get_parent_changed_hosts(changed_hosts, inventory_string):
    # Инициализируем словарь, чтобы сохранить имя группы для каждого хоста
    host_groups = {}

    # Анализируем файл host.ini, чтобы найти имя группы для каждого хоста:
    group_name = None
    for line in inventory_string.splitlines():
        # Проверяем, является ли строка заголовком группы и не содержит ли она подстроку :children
        if line.startswith('[') and line.endswith(']') and ':children' not in line:
            # Извлекаем название группы
            group_name = line[1:-1]
            # print(group_name)
        else:
            # Извлекаем имя хоста из строки, используя регулярное выражение
            match = re.search(r'^(?<!#)\s*([\w\.-]+(?:\[[^\]]+\])?[\w\.-]*)(?:\s+ansible_host=\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:\s+\w+=\w+)*)?(?:\s*#.*)?\s*$', line)
            if match:
                host = match.group(1)
                # Проверем, находится ли этот хост в наборе changed_hosts
                if host in changed_hosts and group_name is not None:
                    # Сохраняем имя группы для этого хоста
                    host_groups[host] = group_name

    # Инициализируем словарь для хранения родительской группы для каждой группы
    parent_groups = {}

    # Анализируем файл инвентаризации
    parent_group_name = None
    for line in inventory_string.splitlines():
        # Проверяем, является ли строка заголовком родительской группы
        if line.startswith('[') and ':children' in line:
            # Извлекаем название родительской группы
            parent_group_name = line[1:line.index(':')]
        elif line.startswith('['):
            # Сбрасываем имя родительской группы для групп, не являющихся родительскими
            parent_group_name = None
        else:
            # Проверяем, есть ли какая-либо из групп в этой строке
            for group in set(host_groups.values()):
                if group == line.strip() and parent_group_name is not None:
                    # Сохраняем имя родительской группы для этой группы
                    parent_groups[group] = parent_group_name

    # Инициализируем словарь для хранения измененных хостов для каждой родительской группы
    parent_changed_hosts = {}

    # Группируем измененные хосты по их родительской группе
    for host in changed_hosts:
        # Получаем имя родительской группы для этого хоста
        parent_group = parent_groups.get(host_groups.get(host))
        if parent_group is not None:
            # Добавляем этот хост в список измененных хостов для этой родительской группы
            if parent_group not in parent_changed_hosts:
                parent_changed_hosts[parent_group] = []
            parent_changed_hosts[parent_group].append(host)

    return parent_changed_hosts

# Раскомментировать для теста
# Инициализируем переменную для хранения измененных хостов
# changed_hosts = set()

if not changed_hosts:
    # Ищем хосты в декодированной строке
    all_hosts = re.findall(r'^(?<!#)\s*([\w\.-]+(?:\[[^\]]+\])?[\w\.-]*)(?:\s+ansible_host=\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:\s+\w+=\w+)*)?(?:\s*#.*)?\s*$', inventory_string, re.MULTILINE)
    changed_hosts = set(all_hosts)
    # print(changed_hosts)
    parent_changed_hosts = get_parent_changed_hosts(changed_hosts, inventory_string)
else:
    parent_changed_hosts = get_parent_changed_hosts(changed_hosts, inventory_string)

# Обновляем данные динамической инвентаризации
inventory = {
    "_meta": {
        "hostvars": {}
    },
    "all": {
        "children": list(parent_changed_hosts.keys())
    }
}
for parent_group, hosts in parent_changed_hosts.items():
    inventory[parent_group] = {
        "hosts": hosts
    }

# Выводим данные в формате JSON
print(json.dumps(inventory))
