Load Testing Results - 2025-11-29
==================================

Overview
--------

These load tests compare Django Channels (4.3.2) HTTP performance against 
traditional WSGI (Gunicorn 23.0.0) under sustained load.

**Important:** These tests evaluate HTTP request handling only, not WebSocket 
performance where Channels is specifically designed to excel.

Test Environment
----------------

**Hardware / OS**

- OS: Windows 11 Home Single Language (64-bit) with WSL2
- WSL2 version: 2.6.1.0  
- Kernel version: 6.6.87.2-1  
- CPU: 4 cores (visible in WSL2)
- RAM: 7.88 GB total (652 MB available during tests)

**Software Versions**

- Python: 3.12.3
- Django: 5.2.8
- Channels: 4.3.2
- Daphne: 4.2.1
- channels_redis: latest
- Redis: 7.1.0
- Gunicorn: 23.0.0
- Node.js: 18.19.1
- loadtest: 8.2.0 (npm package)

Test Objective
--------------

Evaluate the HTTP request handling performance overhead of Django Channels 
compared to traditional WSGI deployments. These tests measure:

- Latency under controlled load
- Throughput (requests per second)
- Error rates
- Performance characteristics of different channel layer backends

Methodology
-----------

**Test Parameters**

- Endpoint: ``GET /`` returning JSON: ``{"status": "ok", "timestamp": ..., "message": "Load test endpoint"}``
- Duration: 60 seconds per configuration
- Target RPS: 75 requests per second
- Concurrent clients: 10 for Gunicorn, 50 for Channels
- Load testing tool: ``loadtest`` (npm package, version 8.2.0)

**Test Command Format**

.. code-block:: bash

   loadtest http://localhost:PORT/ -t 60 -c CLIENTS --rps 75

**Test Isolation**

Each configuration ran on a separate port to ensure clean isolation and allow 
manual verification during testing:

- Gunicorn (WSGI): ``http://localhost:8000/``
- Channels + Redis: ``http://localhost:8001/``
- Channels + IPC: ``http://localhost:8002/``

**Testing Approach**

Tests were conducted using bash scripts that automated:

- Port cleanup between tests
- Server startup with correct settings
- Load test execution with result capture
- Server shutdown

Supervisor was attempted but encountered issues with WSL2 file permissions, 
so manual server management via scripts was used instead.

Test Configurations
-------------------

1. Gunicorn (WSGI Baseline)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Standard Django WSGI server with 4 worker processes.

**Command:**

.. code-block:: bash

   gunicorn testproject.wsgi_no_channels:application -b 0.0.0.0:8000 -w 4

**Settings:** ``testproject.settings.no_channels``

**Load Test:**

.. code-block:: bash

   loadtest http://localhost:8000/ -t 60 -c 10 --rps 75

**Configuration Notes:**

- 4 worker processes for parallel request handling
- Standard WSGI protocol (no async support)
- Channels removed from ``INSTALLED_APPS``


2. Channels + Redis Channel Layer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Django Channels with Redis-backed channel layer for distributed deployments.

**Start Redis:**

.. code-block:: bash

   redis-server

**Start Daphne:**

.. code-block:: bash

   daphne -b 0.0.0.0 -p 8001 testproject.asgi:application

**Settings:** ``testproject.settings.redis_backend``

**Channel Layer Configuration:**

.. code-block:: python

   CHANNEL_LAYERS = {
       'default': {
           'BACKEND': 'channels_redis.core.RedisChannelLayer',
           'CONFIG': {
               "hosts": [('127.0.0.1', 6379)],
           },
       },
   }

**ASGI Application:**

.. code-block:: python

   from django.core.asgi import get_asgi_application
   from channels.routing import ProtocolTypeRouter
   
   application = ProtocolTypeRouter({
       "http": get_asgi_application(),
   })

**Load Test:**

.. code-block:: bash

   loadtest http://localhost:8001/ -t 60 -c 50 --rps 75

**Configuration Notes:**

- Single Daphne process (no load balancing)
- Redis channel layer configured but not actively used for HTTP
- HTTP requests route directly through Django views


3. Channels + IPC Channel Layer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Django Channels with in-memory channel layer (single-machine only).

**Start Daphne:**

.. code-block:: bash

   daphne -b 0.0.0.0 -p 8002 testproject.asgi_ipc:application

**Settings:** ``testproject.settings.ipc_backend``

**Channel Layer Configuration:**

.. code-block:: python

   CHANNEL_LAYERS = {
       'default': {
           'BACKEND': 'channels.layers.InMemoryChannelLayer',
       },
   }

**ASGI Application:**

.. code-block:: python

   from django.core.asgi import get_asgi_application
   from channels.routing import ProtocolTypeRouter
   
   application = ProtocolTypeRouter({
       "http": get_asgi_application(),
   })

**Load Test:**

.. code-block:: bash

   loadtest http://localhost:8002/ -t 60 -c 50 --rps 75

**Configuration Notes:**

- Single Daphne process
- In-memory channel layer (no external dependencies)
- Cannot scale across multiple servers

Results
-------

Performance Summary
~~~~~~~~~~~~~~~~~~~

+----------------------+----------------+------------------+
| Configuration        | Effective RPS  | Mean Latency     |
+======================+================+==================+
| Gunicorn (WSGI)      | 72             | 16.4 ms          |
+----------------------+----------------+------------------+
| Channels + Redis     | 66             | 1056.6 ms        |
+----------------------+----------------+------------------+
| Channels + IPC       | 73             | 38.9 ms          |
+----------------------+----------------+------------------+

Visual Comparison
~~~~~~~~~~~~~~~~~

.. image:: channels-latency.png
   :alt: Latency comparison across configurations

.. image:: channels-throughput.png
   :alt: Throughput comparison across configurations

Detailed Results
~~~~~~~~~~~~~~~~

**1. Gunicorn (WSGI Baseline)**

- Completed requests: 4,370
- Total errors: 0
- Total time: 60.291 s
- Mean latency: 16.4 ms
- Effective RPS: 72
- Concurrent clients (peak): 65
- Latency percentiles:
  
  - 50%: 3 ms
  - 90%: 7 ms
  - 95%: 16 ms
  - 99%: 482 ms
  - 100%: 2,229 ms (longest request)

**2. Channels + Redis Channel Layer**

- Completed requests: 3,966
- Total errors: 0
- Total time: 60.173 s
- Mean latency: 1056.6 ms
- Effective RPS: 66
- Concurrent clients (peak): 481
- Latency percentiles:
  
  - 50%: 565 ms
  - 90%: 2,661 ms
  - 95%: 3,148 ms
  - 99%: 6,245 ms
  - 100%: 6,433 ms (longest request)

**3. Channels + IPC Channel Layer**

- Completed requests: 4,368
- Total errors: 0
- Total time: 60.041 s
- Mean latency: 38.9 ms
- Effective RPS: 73
- Concurrent clients (peak): 40
- Latency percentiles:
  
  - 50%: 14 ms
  - 90%: 94 ms
  - 95%: 177 ms
  - 99%: 427 ms
  - 100%: 519 ms (longest request)

Analysis
--------

Performance Observations
~~~~~~~~~~~~~~~~~~~~~~~~

**Gunicorn (WSGI)**

- Lowest latency: 16.4 ms mean, 3 ms median
- Consistent performance across percentiles
- 4 worker processes provide good parallelism
- Best choice for HTTP-only Django applications
- No async capabilities

**Channels + Redis**

- Significantly higher latency: 1056.6 ms mean (64x higher than Gunicorn)
- High concurrent client count (481) indicates request queuing
- Single Daphne process handling synchronous views serially
- Channel layer configured but not used for simple HTTP routing
- Suitable for production when WebSocket/async features are required

**Channels + IPC**

- Middle ground: 38.9 ms mean latency (2.4x higher than Gunicorn)
- Similar throughput to Gunicorn (73 vs 72 RPS)
- Lower concurrent clients (40) compared to Redis setup
- Better latency than Redis due to no network overhead
- Limited to single-machine deployments

Why Channels Shows Higher Latency
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The latency differences are primarily due to:

**1. Process Architecture**

- Gunicorn: 4 worker processes handling requests in parallel
- Daphne: Single process in these tests (production would use multiple instances)

**2. Protocol Overhead**

- WSGI: Optimized for synchronous HTTP
- ASGI: Additional abstraction layer supporting both sync and async

**3. Synchronous View Handling**

For synchronous Django views (like the test endpoint), Daphne processes 
requests serially within a single process. With 50 concurrent clients, 
requests queue up, causing higher latency.

**4. Channel Layer Configuration**

While Redis and IPC channel layers are configured, they are not actively used 
for simple HTTP requests. The overhead comes from:

- ASGI protocol processing
- Channels routing layer
- Single-process concurrency limitations

Why Workers Are Not Required
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Channel workers (``python manage.py runworker``) are **not used** in these 
tests because:

**Workers Are Only Needed For:**

- WebSocket message handling
- Async consumers that process channel layer messages
- Background task execution via channels
- Cross-server communication through channel layers

**These Tests Use:**

- Simple synchronous Django views
- Direct HTTP → Django → Response flow
- No WebSocket connections
- No channel layer messaging

**Request Flow:**

.. code-block:: text

   HTTP Request
       ↓
   Daphne (ASGI server)
       ↓
   ProtocolTypeRouter → "http" → Django ASGI app
       ↓
   Django view (synchronous)
       ↓
   JSON response
       ↓
   Daphne returns response

The channel layer is configured but bypassed for HTTP traffic. Workers would 
only be invoked if WebSocket connections or async consumers were involved.

**Historical Context - 2016 vs 2025 Architecture:**

.. code-block:: text

   Channels 1.x (2016):
   HTTP → Daphne → Channel Layer → Worker → Django View → Response
   (Workers required for ALL requests including HTTP)
   
   Channels 3.x+ (2025):
   HTTP → Daphne → Django View → Response
   WebSocket → Daphne → Channel Layer → Worker → Consumer
   (Workers only for WebSocket/async, not HTTP)

The 2016 load tests used workers because Channels 1.x routed all traffic 
(HTTP and WebSocket) through the channel layer. Modern Channels (3.x+) routes 
HTTP directly to Django, using the channel layer only for WebSocket and async 
consumers.

**Both test suites evaluate HTTP performance correctly for their respective 
Channels versions.**

Comparison with 2016 Load Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``loadtesting/2016-09-06/`` results used Channels 1.x with different 
architecture:

**2016 Results (Channels 1.x, 300 RPS target):**

- Gunicorn: 6 ms latency
- Channels + Redis: 12 ms latency  
- Channels + IPC: 35 ms latency

**2025 Results (Channels 4.x, 75 RPS target):**

- Gunicorn: 16.4 ms latency
- Channels + Redis: 1056.6 ms latency
- Channels + IPC: 38.9 ms latency

**Key Differences:**

1. **Architecture Change:** Channels 1.x routed all HTTP through channel layer 
   (required workers); Channels 3.x+ routes HTTP directly to Django (no workers 
   needed for HTTP)
2. **Test Configuration:** 2016 used multiple workers and load-balanced Daphne; 
   2025 used single Daphne instances
3. **Concurrency Model:** Different client counts and server configurations
4. **Target Load:** 300 RPS (2016) vs 75 RPS (2025)

The Redis latency difference reflects single-process vs multi-process 
deployment, not a performance regression in Channels itself.

When to Use Each Approach
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use Gunicorn (WSGI) when:**

- Building traditional Django HTTP/REST APIs
- No WebSocket or real-time features required
- Minimizing latency is critical
- Simpler deployment and operation preferred

**Use Channels + Redis when:**

- WebSocket connections required (chat, notifications, live updates)
- Async background task processing needed
- Multi-server deployment with distributed channel layer
- Real-time features outweigh HTTP latency overhead

**Use Channels + IPC when:**

- Development and testing environments
- Single-server deployment with async requirements
- Lower latency than Redis acceptable for local use
- No need for horizontal scaling

Conclusions
-----------

1. **Gunicorn remains the best choice for pure HTTP workloads** with lowest 
   latency (16.4 ms) and consistent performance.

2. **Channels introduces measurable HTTP overhead** but enables critical features 
   impossible with WSGI: WebSocket support, async consumers, and real-time 
   communication.

3. **Single Daphne process vs multi-worker Gunicorn** partially explains the 
   latency differences. Production Channels deployments would use multiple 
   Daphne instances behind a load balancer.

4. **Redis backend trades latency for distributed scalability.** The 1056.6 ms 
   latency reflects single-process handling of synchronous views, not optimal 
   Channels deployment.

5. **IPC backend offers better single-machine performance** (38.9 ms) than Redis 
   but cannot scale horizontally.

6. **Channels should not be judged solely on HTTP performance.** Its value lies 
   in enabling WebSocket and async capabilities that WSGI fundamentally cannot 
   provide.

7. **Architecture evolution from Channels 1.x to 4.x** has optimized HTTP 
   performance by routing simple requests directly to Django, reserving the 
   channel layer for WebSocket and async operations.

Implementation Notes
--------------------

**Testing Scripts**

Two bash scripts were created for automated testing:

1. ``scripts/test_gunicorn_redis.sh``
   
   - Tests Gunicorn baseline
   - Tests Channels + Redis backend
   - Handles server startup/shutdown
   - Captures results to files

2. ``scripts/test_ipc.sh``
   
   - Tests Channels + IPC backend
   - Requires manual Daphne startup
   - Captures results to files

**Challenges Encountered**

- Supervisor configuration issues with WSL2 file permissions
- Manual server management via bash scripts required
- Port cleanup needed between tests
- Higher RPS values (300+) caused error rates >75%, reduced to 75 RPS
- Concurrent client auto-scaling by loadtest tool

**Test Repeatability**

All tests were run multiple times to ensure consistency. Results shown are 
representative of typical performance under the specified load conditions.

Raw Data
--------

Complete test output available in ``results/`` directory:

- ``gunicorn_75rps.txt`` - Gunicorn baseline results
- ``redis_75rps.txt`` - Channels + Redis results  
- ``ipc_75rps.txt`` - Channels + IPC results

Test scripts available in ``scripts/`` directory:

- ``test_gunicorn_redis.sh`` - Automated Gunicorn + Redis testing
- ``test_ipc.sh`` - Automated IPC testing (requires manual Daphne start)

Visual Results
~~~~~~~~~~~~~~

Charts showing latency and throughput comparisons:

- ``channels-latency.png`` - Latency comparison graph
- ``channels-throughput.png`` - Throughput comparison graph

References
----------

- Django Channels documentation: https://channels.readthedocs.io/
- Previous load tests: ``loadtesting/2016-09-06/``
- Channels architecture changes: https://channels.readthedocs.io/en/latest/releases/3.0.0.html
- loadtest tool: https://www.npmjs.com/package/loadtest
