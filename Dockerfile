FROM python:3
RUN pip install django==3.2

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN python manage.py migrate
EXPOSE 8000
CMD ["python","manage.py","runserver","0.0.0.0:8000"]


