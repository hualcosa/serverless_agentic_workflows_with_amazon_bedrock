import os
import sys
import subprocess
import shutil
import zipfile

def create_lambda_deployment(folder_path):
    # Validate input folder
    if not os.path.isdir(folder_path):
        print(f"Error: {folder_path} is not a valid directory")
        sys.exit(1)

    app_path = os.path.join(folder_path, "app.py")
    req_path = os.path.join(folder_path, "requirements.txt")

    if not os.path.isfile(app_path) or not os.path.isfile(req_path):
        print("Error: app.py or requirements.txt not found in the specified folder")
        sys.exit(1)

    # Get the folder name for the zip file
    folder_name = os.path.basename(os.path.normpath(folder_path))

    # Create a temporary directory for the deployment package
    temp_dir = os.path.join(folder_path, "deployment_package")
    os.makedirs(temp_dir, exist_ok=True)

    # Copy app.py to the deployment package
    shutil.copy2(app_path, temp_dir)

    # Install dependencies
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_path, "-t", temp_dir], check=True)

    # Create 'deployments' directory in the parent folder
    deployments_dir = os.path.join(os.path.dirname(folder_path), "deployments")
    os.makedirs(deployments_dir, exist_ok=True)

    # Create ZIP file with folder name in the deployments directory
    zip_filename = os.path.join(deployments_dir, f"lambda_deployment_{folder_name}.zip")
    print(f"Creating ZIP file: {zip_filename}")
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)

    # Clean up temporary directory
    shutil.rmtree(temp_dir)

    print(f"Deployment package created successfully: {zip_filename}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <folder_path>")
        sys.exit(1)

    folder_path = sys.argv[1]
    create_lambda_deployment(folder_path)