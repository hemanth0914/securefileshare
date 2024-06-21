from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.files.storage import default_storage
import paramiko
import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

@method_decorator(csrf_exempt, name='dispatch')
def upload_file_to_ec2_view(request):
    if request.method == 'POST':
        try:
            local_file = request.FILES['file']
            remote_file_path = request.POST.get('remote_file_path')
            ec2_ip = request.POST.get('ec2_ip')
            ec2_user = request.POST.get('ec2_user')
            key_file_path = request.POST.get('key_file_path')

            # Save the uploaded file temporarily
            local_file_path = default_storage.save(local_file.name, local_file)
            local_file_full_path = os.path.join(default_storage.location, local_file_path)

            # Create an SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                # Connect to the EC2 instance
                ssh.connect(hostname=ec2_ip, username=ec2_user, key_filename=key_file_path)

                # Create an SFTP session
                sftp = ssh.open_sftp()

                # Upload the file to EC2
                sftp.put(local_file_full_path, remote_file_path)
                print(f"File {local_file_full_path} uploaded to {remote_file_path} on {ec2_ip}")

                # Upload the file from EC2 to S3
                upload_success = upload_file_to_s3_via_ec2(sftp, remote_file_path, 'easyfilesharebuckets')
                if upload_success:
                    # Delete the file from EC2 after successful upload to S3
                    sftp.remove(remote_file_path)
                    print(f"File {remote_file_path} deleted from EC2 instance {ec2_ip}")

                # Close the SFTP session
                sftp.close()

                # Clean up the local file
                default_storage.delete(local_file_path)

                return JsonResponse({'message': f"File uploaded to {remote_file_path} on {ec2_ip} and then to S3"})
            except Exception as e:
                print(f"Failed to upload file: {e}")
                return JsonResponse({'error': str(e)}, status=500)
            finally:
                # Close the SSH connection
                ssh.close()
        except KeyError as e:
            return JsonResponse({'error': f'Missing parameter: {e.args[0]}'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


def upload_file_to_s3_via_ec2(sftp, remote_file_path, bucket_name, object_name=None):
    """
    Upload a file to an AWS S3 bucket from an EC2 instance via SFTP.

    :param sftp: Active SFTP session
    :param remote_file_path: Path to the file on the EC2 instance
    :param bucket_name: S3 bucket to upload to
    :param object_name: S3 object name. If not specified, remote_file_path is used
    :return: True if file was uploaded, else False
    """
    if object_name is None:
        object_name = remote_file_path.split('/')[-1]

        # Read the file from EC2
    s3_client = boto3.client('s3')
    print(remote_file_path)
    session = boto3.Session()
    credentials = session.get_credentials()
    print(f"Using IAM Role credentials: {credentials}")

    try:
        # Read the file from EC2
        with sftp.file(remote_file_path, 'rb') as file:
            s3_client = boto3.client('s3')
            s3_client.upload_fileobj(file, bucket_name, object_name)
            print(f"File {remote_file_path} uploaded to {bucket_name} as {object_name}")
        return True
    except FileNotFoundError:
        print("The file was not found on EC2")
        return False
    except NoCredentialsError:
        print("Credentials not available")
        return False
    except ClientError as e:
        print(f"Failed to upload file to S3: {e}")
        return False


@method_decorator(csrf_exempt, name='dispatch')
def download_file_from_ec2_view(request):
    if request.method == 'POST':
        try:
            remote_file_path = request.POST.get('remote_file_path')
            ec2_ip = request.POST.get('ec2_ip')
            ec2_user = request.POST.get('ec2_user')
            key_file_path = request.POST.get('key_file_path')

            if not all([remote_file_path, ec2_ip, ec2_user, key_file_path]):
                return JsonResponse({'error': 'All parameters are required'}, status=400)

            # Create an SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                # Connect to the EC2 instance
                ssh.connect(hostname=ec2_ip, username=ec2_user, key_filename=key_file_path)

                # Create an SFTP session
                sftp = ssh.open_sftp()

                # Define local file path to save the downloaded file
                local_file_name = os.path.basename(remote_file_path)
                local_file_path = os.path.join('/tmp', local_file_name)  # Using /tmp directory to save the file

                # Download the file
                sftp.get(remote_file_path, local_file_path)
                print(f"File {remote_file_path} downloaded to {local_file_path} from {ec2_ip}")

                # Close the SFTP session
                sftp.close()

                # Read the downloaded file and send it as a response
                with open(local_file_path, 'rb') as file:
                    response = HttpResponse(file.read(), content_type='application/octet-stream')
                    response['Content-Disposition'] = f'attachment; filename={local_file_name}'
                    return response

            except Exception as e:
                print(f"Failed to download file: {e}")
                return JsonResponse({'error': str(e)}, status=500)
            finally:
                # Close the SSH connection
                ssh.close()
                # Clean up the local file
                if os.path.exists(local_file_path):
                    os.remove(local_file_path)

        except KeyError as e:
            return JsonResponse({'error': f'Missing parameter: {e.args[0]}'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)