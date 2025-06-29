# Use a specific, compatible Python version
FROM python:3.11-bullseye

# Copy requirements first for better layer caching
COPY requirements.txt .
# Install Python dependencies efficiently
RUN pip install --no-cache-dir -r requirements.txt

# Copy cookies.txt for gdown
COPY cookies.txt /root/.cache/gdown/

# Copy the rest of the application code
COPY . .

# Set the command to run the application
CMD ["python3", "-m", "floodcast.main"]