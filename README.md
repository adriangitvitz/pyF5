# PyF5

A Python client library for interacting with F5 BIG-IP load balancers. This tool provides comprehensive functionality to retrieve, analyze, and export F5 virtual server and pool configurations with built-in rate limiting, circuit breaker patterns, and robust error handling.

## Features

- **F5 BIG-IP API Integration**: Full REST API client for F5 load balancers
- **Rate Limiting**: Token bucket algorithm to prevent API overload
- **Circuit Breaker**: Automatic failure detection and recovery
- **Authentication Management**: Automatic token refresh and session handling
- **Data Export**: JSON and CSV export capabilities
- **Pool Analysis**: Detailed pool member health monitoring
- **Virtual Server Mapping**: Complete virtual server to pool relationships

## Installation

### Prerequisites

- Python 3.9 or higher
- Access to F5 BIG-IP management interface
- Valid F5 credentials with appropriate permissions

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd pyf5
```

2. Create a virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
uv sync
```

## Configuration

### Rate Limiting

The client includes configurable rate limiting to prevent overwhelming the F5 API:

```python
from client.ratelimit import RateLimitConfig

rate_config = RateLimitConfig(
    requests_per_second=5.0,  # Maximum requests per second
    burst_capacity=10,        # Burst capacity for sudden spikes
    cooldown_period=2.0       # Cooldown period in seconds
)
```

### Client Configuration

```python
from client.base import F5Client

f5_client = F5Client(
    host="your-f5-host.example.com",
    username="your-username",
    password="your-password",
    rate_limit_config=rate_config,
    timeout=30,
    max_retries=3
)
```

## Usage

### Basic Usage

#### Complete Analysis Pipeline

Run the main script to retrieve and process F5 data:

```python
# Run the script directly
python parse.py
```

Or use the functions programmatically:

```python
from parse import retrieve_data, summary_csv
from client.base import F5Client
from client.ratelimit import RateLimitConfig

# Configure rate limiting
rate_config = RateLimitConfig(
    requests_per_second=5.0,
    burst_capacity=10,
    cooldown_period=2.0
)

# Initialize client
f5_client = F5Client(
    host="<your-f5-host>",
    username="<your-username>",
    password="<your-password>",
    rate_limit_config=rate_config,
    timeout=30,
    max_retries=3
)

# Retrieve and process data
environment = "PRODUCTION"
retrieve_data(f5_client, environment)

# Generate summary CSV
summary_csv(f"{environment}_output.json", f"{environment}_summary.csv")
```

#### Individual API Calls

For direct API access:

```python
# Get virtual servers
virtual_servers = f5_client.get_vs()

# Get pools
pools = f5_client.get_pools()

# Get pool members
pool_members = f5_client.get_pool_members("pool-name")
```

#### Manual Data Processing

```python
import json

# Load and process virtual servers
with open('vs.json', 'r') as f:
    vs_data = json.load(f)

# Load and process pools
with open('pools.json', 'r') as f:
    pools_data = json.load(f)
```

## Project Structure

```
pyf5/
├── client/
│   ├── __init__.py
│   ├── base.py          # Main F5Client class
│   ├── breaker.py       # Circuit breaker implementation
│   ├── ratelimit.py     # Rate limiting functionality
│   └── tokenmanager.py  # Authentication token management
├── parse.py             # Main script and data processing functions
├── pyproject.toml       # Project configuration
└── README.md
```

### Core Components

#### F5Client (`client/base.py`)
The main client class that handles:
- HTTP communication with F5 API
- Authentication and token management
- Rate limiting and circuit breaker integration
- Retry logic with exponential backoff

#### Rate Limiting (`client/ratelimit.py`)
Token bucket implementation that:
- Controls request rate to prevent API overload
- Supports burst capacity for sudden spikes
- Thread-safe implementation

#### Circuit Breaker (`client/breaker.py`)
Fault tolerance mechanism that:
- Monitors API failures
- Automatically opens circuit on repeated failures
- Provides automatic recovery with half-open state

#### Token Manager (`client/tokenmanager.py`)
Authentication handling that:
- Manages F5 authentication tokens
- Automatic token refresh before expiration
- Thread-safe token operations

## Data Formats

### Output JSON Structure

The processed data includes comprehensive virtual server information:

```json
{
  "name": "virtual-server-name",
  "creationTime": "2023-01-01T00:00:00Z",
  "destination": "10.0.1.100:80",
  "disabled": false,
  "source": "0.0.0.0/0",
  "sourceAddressTranslation": "automap",
  "pool": {
    "name": "pool-name",
    "monitor": "http",
    "members": [
      {
        "name": "server1:80",
        "address": "10.0.2.10:80",
        "state": "up",
        "session": "user-enabled",
        "monitor": "up"
      }
    ]
  }
}
```

### CSV Summary Fields

The CSV export includes the following columns:
- `name`: Virtual server name
- `destination`: Virtual server destination IP:port
- `disabled`: Whether virtual server is disabled
- `pool_name`: Associated pool name
- `pool_monitor`: Pool health monitor
- `total_members`: Total number of pool members
- `up_members`: Number of healthy members
- `down_members`: Number of unhealthy members
- `health_percentage`: Pool health percentage
- `member_addresses`: Semicolon-separated member addresses
- `member_names`: Semicolon-separated member names

## Error Handling

The client implements comprehensive error handling:

- **Rate Limiting**: Automatic throttling when rate limits are exceeded
- **Circuit Breaker**: Automatic failure detection and recovery
- **Retry Logic**: Exponential backoff for transient failures
- **Authentication**: Automatic token refresh on expiration
- **HTTP Errors**: Proper handling of 4xx and 5xx responses

## Security Considerations

- **Credentials**: Never hardcode credentials in production code
- **HTTPS**: All communication uses HTTPS (certificate validation disabled for self-signed certs)
- **Token Management**: Automatic token refresh prevents long-lived sessions
- **Rate Limiting**: Prevents accidental API abuse

## Environment Variables

For production use, update the placeholders in `parse.py`:

```python
# Update these values in parse.py
environment = "PRODUCTION"  # or "QA", "DEV", etc.
f5_client = F5Client(
    host="your-f5-host.example.com",  # Replace with actual F5 host
    username="your-username",         # Replace with actual username
    password="your-password",         # Replace with actual password
    rate_limit_config=rate_config,
    timeout=30,
    max_retries=3
)
```

Or consider using environment variables:

```bash
export F5_HOST="your-f5-host.example.com"
export F5_USERNAME="your-username"
export F5_PASSWORD="your-password"
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify credentials are correct
   - Check F5 user permissions
   - Ensure management interface is accessible

2. **Rate Limiting**
   - Adjust `requests_per_second` in RateLimitConfig
   - Increase `cooldown_period` for busy systems

3. **Connection Timeouts**
   - Increase `timeout` parameter
   - Check network connectivity to F5 management interface

4. **SSL/Certificate Issues**
   - Client disables certificate verification by default
   - For production, consider enabling certificate validation

### Debug Logging

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
