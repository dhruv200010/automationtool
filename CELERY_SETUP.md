# Celery with Redis Setup for Video Automation Pipeline

This document explains how to use the new Celery-based background task processing system to prevent HTTP timeouts.

## Overview

The video automation pipeline now uses Celery with Redis to handle video processing tasks in the background, preventing HTTP timeouts and providing better user experience with real-time status updates.

## Architecture

- **Flask App**: Handles file uploads and serves the web interface
- **Celery Worker**: Processes video files in the background
- **Redis**: Message broker and result backend for Celery
- **Web Interface**: Real-time status updates with progress tracking

## Quick Start

### Option 1: Full Service Manager (Recommended for Production)

```bash
# Install dependencies
pip install -r requirements.txt

# Start all services (Redis, Celery Worker, Flask App)
python start_services.py
```

### Option 2: Development Mode (For Local Testing)

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery Worker
python start_worker.py

# Terminal 3: Start Flask App
python dev_start.py
```

### Option 3: Docker (Production Deployment)

```bash
# Build and run with Docker
docker build -t video-automation .
docker run -p 8000:8080 video-automation
```

## Configuration

### Redis Configuration

The system uses Redis as the message broker. Configuration is in `config/master_config.json`:

```json
{
  "celery_config": {
    "broker_url": "redis://localhost:6379/0",
    "result_backend": "redis://localhost:6379/0",
    "task_time_limit": 1800,
    "task_soft_time_limit": 1500,
    "worker_concurrency": 1,
    "worker_pool": "solo"
  }
}
```

### Environment Variables

- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379/0`)
- `PORT`: Port for Flask app (default: 8000)

## API Endpoints

### Upload Video
```
POST /upload
Content-Type: multipart/form-data

Returns:
{
  "message": "Video upload successful! Processing started.",
  "task_id": "uuid-task-id",
  "status": "PROCESSING",
  "filename": "video.mp4"
}
```

### Check Task Status
```
GET /task/<task_id>

Returns:
{
  "state": "PROGRESS|SUCCESS|FAILURE|PENDING",
  "status": "Processing...",
  "progress": 50
}
```

### Get Task Result
```
GET /task/<task_id>/result

Returns:
{
  "status": "SUCCESS",
  "output_filename": "processed_video.mp4",
  "message": "Video processed successfully!"
}
```

### Cleanup Files
```
POST /task/<task_id>/cleanup

Returns:
{
  "message": "Cleanup task started"
}
```

## Web Interface Features

- **Real-time Progress**: Live updates every 2 seconds
- **Task Tracking**: Shows task ID and current status
- **Progress Bar**: Visual progress indicator
- **Error Handling**: Clear error messages and recovery options
- **Auto-redirect**: Automatically redirects to result page when complete

## Task States

- **PENDING**: Task is waiting to be processed
- **PROGRESS**: Task is currently being processed
- **SUCCESS**: Task completed successfully
- **FAILURE**: Task failed with error

## Error Handling

The system includes comprehensive error handling:

- **Upload Errors**: File validation and storage issues
- **Processing Errors**: Pipeline failures with detailed logging
- **Timeout Handling**: Graceful handling of long-running tasks
- **Cleanup**: Automatic cleanup of temporary files

## Monitoring and Logging

- **Real-time Logs**: Available at `/logs` endpoint
- **Task Logs**: Detailed logging in `pipeline.log`
- **Health Check**: Available at `/health` endpoint
- **Debug Info**: Available at `/debug` endpoint

## Performance Considerations

- **Single Worker**: Uses solo pool to avoid conflicts
- **Task Limits**: 30-minute time limit with 25-minute soft limit
- **Memory Management**: Worker restarts after each task
- **Resource Cleanup**: Automatic cleanup of temporary files

## Troubleshooting

### Common Issues

1. **Redis Connection Error**
   ```
   Solution: Ensure Redis is running on localhost:6379
   ```

2. **Celery Worker Not Starting**
   ```
   Solution: Check Python dependencies and Redis connection
   ```

3. **Task Timeout**
   ```
   Solution: Check video file size and processing complexity
   ```

4. **File Not Found**
   ```
   Solution: Ensure input/output directories exist and are writable
   ```

### Debug Commands

```bash
# Check Redis connection
redis-cli ping

# Check Celery worker status
celery -A celery_app inspect active

# View task results
celery -A celery_app inspect stats
```

## Development

### Adding New Tasks

1. Define task in `celery_app.py`:
```python
@celery_app.task(bind=True)
def my_new_task(self, param1, param2):
    # Task implementation
    return {'status': 'SUCCESS', 'result': 'data'}
```

2. Call task from Flask app:
```python
task = my_new_task.delay(param1, param2)
```

3. Check task status:
```python
result = my_new_task.AsyncResult(task.id)
```

### Testing

```bash
# Test Redis connection
python -c "import redis; r = redis.Redis(); print(r.ping())"

# Test Celery worker
python -c "from celery_app import process_video_task; print('Celery app loaded successfully')"
```

## Production Deployment

### Railway Deployment

The system is optimized for Railway deployment:

- Automatic Redis setup in Docker
- Optimized worker settings
- Health checks and monitoring
- Automatic scaling

### Environment Variables for Production

```bash
REDIS_URL=redis://your-redis-url:6379/0
PORT=8080
```

## Benefits

1. **No HTTP Timeouts**: Background processing prevents timeout issues
2. **Better UX**: Real-time progress updates and status tracking
3. **Scalability**: Can handle multiple concurrent tasks
4. **Reliability**: Task persistence and error recovery
5. **Monitoring**: Comprehensive logging and status tracking
6. **Resource Management**: Efficient memory and CPU usage

## Migration from Synchronous Processing

The new system is backward compatible. Existing code will continue to work, but new uploads will use the async processing system automatically.

## Support

For issues or questions:
1. Check the logs in `pipeline.log`
2. Use the `/debug` endpoint for system information
3. Monitor task status via the web interface
4. Check Redis and Celery worker status
