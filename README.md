EBDMS - electronic biomedical data managment system

To start
```
pip install poetry
cd ebdms/
poetry install
```

To start app
```
poetry run python manage.py makemigrations
poetry run python manage.py migrate

poetry run python manage.py createsuperuser
poetry run python manage.py runserver
```