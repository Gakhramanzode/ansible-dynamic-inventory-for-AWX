# ansible-dynamic-inventory-for-AWX
Данный python-скрипт позволяет формировать `JSON` с перечнем групп, хостов и переменных, на которые необходимо производить какие-то действия в `AWX Playbook Run`. Например, необходимо раскатывать ansible роль не на все хосты из `hosts.ini`, а только на те, у которых были произведены какие-то изминения.
## Как это вообще работает?
1. Обращаемся к `API GitLab` для получения списка коммитов. 
2. В последнем коммите ищем правки в директории `host_vars`.
3. С помощью модуля `configparser` парсим файл `hosts.ini`.
4. Если в `host_vars` были правки, берем эти конкретные хосты и в функции `get_parent_changed_hosts` определяем родительские и дочерние группы. Если правок не было, тогда уже работаем со всеми хостами из `hosts.ini`.
5. Получаем переменные для хостов из папки `group_vars`.
6. Формируем и выводим`JSON`.
## Как запустить синхронизацию в AWX?
1. Во вкладке Resources перейти в `Projects`. Нажать `Add`, чтобы создать проект. Заполнить такие поля как:
  - `Name`
  - `Organization`
  - `Source Control Type`
  - `Source Control URL`
  - `Source Control Branch/Tag/Commit`
  - `Source Control Credential`
  - `Update Revision on Launch`
2. Во вкладке Resources перейти в `Inventories`. Нажать `Add` и `Add inventory`, чтобы создать инвентарь. Заполнить такие поля как:
  - `Name`
  - `Organization`

Перейти в раздел `Sources`. Нажать `Add`, чтобы создать источник для инвентаря. Заполнить такие поля как:
  - `Name`
  - `Source` (выбрать `Sourced from a Project`)
  - `Project` (выбрать свой из первого пнутка)
  - `Inventory file` (указать путь к python-скрипту в ansible репозитории, например, `inventories/my-project/dynamic-inventory.py`)
  - `Overwrite`, `Overwrite variables`, `Update on launch`
3. Нажать `Sync`

Таким образом `AWX` берет скрипт из репозитория, исполняет его в своей среде, получает `JSON`, который переносит все группы, хосты и переменные из `group_vars` в свой раздел инвентаря `Groups` и `Hosts` соответственно. Эту информацию `AWX` будет использовать для исполнения, например, `Playbook Run`.
