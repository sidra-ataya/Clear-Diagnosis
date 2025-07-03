# Use an official Python runtime as a parent image
FROM python:3.9

# Define environment variable
ENV FLASK_APP=app.py

# Set the working directory in the container
WORKDIR /app

# Upgrade pip before installing dependencies
RUN pip install --upgrade pip

# Install any needed packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
