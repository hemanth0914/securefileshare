from django.urls import path
from .views import upload_file_to_ec2_view, download_file_from_ec2_view

urlpatterns = [
    path('upload/', upload_file_to_ec2_view, name='upload_file_to_ec2'),
    path('download/', download_file_from_ec2_view, name='download_file_from_ec2'),
]