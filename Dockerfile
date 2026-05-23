# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory to /app
WORKDIR /app

# Create a non-root user (Hugging Face Spaces requirement)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
ENV PYTHONPATH="/app/backend"

# Copy the requirements file into the container
COPY --chown=user backend/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend and frontend code
COPY --chown=user backend/ backend/
COPY --chown=user frontend/ frontend/

# Make port 7860 available to the outside (Hugging Face expectation)
EXPOSE 7860

# Run uvicorn server from the root, pointing to backend.main:app
# and serving on port 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
