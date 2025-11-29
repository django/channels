Django Channels Load Testing Results for (2025-11-29)
=====================================================

The goal of these load tests is to evaluate how Django Channels (4.3.2) performs
with normal HTTP traffic under heavy load in comparison to a traditional WSGI
server (Gunicorn 23.0.0).

Channels introduces ASGI, an asynchronous server gateway interface that enables
non-blocking communication such as WebSockets. Daphne is used as the ASGI server
for these tests.

These results focus *only* on HTTP request performance, not WebSocket messaging.


Summary of Results
~~~~~~~~~~~~~~~~~~

Gunicorn continues to deliver the best raw HTTP performance:

- lowest latency  
- highest throughput (RPS)  
- near-zero errors  

The Channels setups introduce additional overhead:

1. **Channels + Redis Channel Layer**
   - significantly higher latency than WSGI  
   - ~40-60% of Gunicorn throughput  
   - moderate latency spikes  
   - still acceptable for real-world asynchronous workloads  

2. **Channels + IPC Channel Layer (Same-Machine Only)**
   - latency is lower than Redis in short bursts  
   - throughput is still lower than Gunicorn  
   - works only on a single machine  
   - suitable for experimentation or local development  

These results align with historical findings:  
**Channels is optimized for async workflows—not maximum raw HTTP throughput.**


Environment & Versions
~~~~~~~~~~~~~~~~~~~~~~

**Hardware / OS**

- OS: Windows 11 Home Single Language, 64-bit  
- WSL2 version: 2.6.1.0  
- Kernel version: 6.6.87.2-1  
- CPU: 1 Processor (Check `lscpu` in WSL for details)  
- RAM: 7.88 GB total, 652 MB available  

**Software Versions**

- Python: 3.12.3  
- Django: 5.2.8  
- Django Channels: 4.3.2  
- Daphne: 4.2.1  
- Redis: 7.1.0  
- Gunicorn: 23.0.0  
- Node.js: 18.19.1  
- `loadtest` CLI: 8.2.0  


Methodology
~~~~~~~~~~~

Steps taken to ensure reproducible and fair testing:

- Same test endpoint: ``GET /test/``  
- Test duration: **60 seconds**  
- Constant RPS for latency test: **75 RPS**  
- Throughput test used auto-throttled `loadtest`  
- Each test repeated several times; averages taken  
- Freed ports between tests using:

  .. code-block:: bash

      fuser -k 8000/tcp
      fuser -k 9000/tcp
      fuser -k 6379/tcp

- Redis and Daphne were started manually for consistency

**Load Testing Tool**

.. code-block:: bash

   npx loadtest -c 1 --rps <value> http://localhost:PORT/test/

**Three setups were tested:**

1. Gunicorn (WSGI)  
2. Channels + Redis + Daphne  
3. Channels + IPC + Daphne


Setups
~~~~~~

1) Gunicorn (WSGI)
------------------

The baseline for comparison.

.. code-block:: bash

   gunicorn testproject.wsgi:application -b 0.0.0.0:8000


2) Channels + Redis Channel Layer + Daphne
------------------------------------------

Redis start:

.. code-block:: bash

   redis-server

Daphne start:

.. code-block:: bash

   daphne -b 0.0.0.0 -p 9000 testproject.asgi:application

Worker:

.. code-block:: bash

   python manage.py runworker


3) Channels + IPC Channel Layer + Daphne
-----------------------------------------

Only functional on a single machine.

Settings: ``testproject/settings/ipc_backend.py``

Daphne:

.. code-block:: bash

   daphne -b 0.0.0.0 -p 9000 testproject.asgi_ipc:application

Worker:

.. code-block:: bash

   python manage.py runworker --settings=testproject.settings.ipc_backend


Latency & Throughput Results
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. image:: channels-latency.PNG

.. image:: channels-throughput.PNG

**Throughput (Effective RPS)**

+----------------------+----------------+
| Setup               | Effective RPS   |
+======================+================+
| Gunicorn             | 72             |
+----------------------+----------------+
| Channels + Redis     | 66             |
+----------------------+----------------+
| Channels + IPC       | 73             |
+----------------------+----------------+


**Latency (Mean)**

+----------------------+----------------+
| Setup               | Mean Latency    |
+======================+================+
| Gunicorn             | 16.4 ms        |
+----------------------+----------------+
| Channels + Redis     | 1056.6 ms      |
+----------------------+----------------+
| Channels + IPC       | 38.9 ms        |
+----------------------+----------------+


Detailed Raw Metrics
~~~~~~~~~~~~~~~~~~~~

Redis Results
-------------

- Completed requests: 3966  
- Total errors: 0  
- Mean latency: 1056.6 ms  
- Effective RPS: 66  
- Percentiles: 50% 565 ms, 90% 2661 ms, 95% 3148 ms, 99% 6245 ms, 100% 6433 ms

IPC Results
-----------

- Completed requests: 4368  
- Total errors: 0  
- Mean latency: 38.9 ms  
- Effective RPS: 73  
- Percentiles: 50% 14 ms, 90% 94 ms, 95% 177 ms, 99% 427 ms, 100% 519 ms

Gunicorn Results
----------------

- Completed requests: 4370  
- Total errors: 0  
- Mean latency: 16.4 ms  
- Effective RPS: 72  
- Percentiles: 50% 3 ms, 90% 7 ms, 95% 16 ms, 99% 482 ms, 100% 2229 ms


Observations
~~~~~~~~~~~~

- Channels is not intended to outperform WSGI for pure HTTP  
- Redis setup resembles real production async architecture  
- IPC performs better than Redis in latency but still below Gunicorn  
- Worker speed is the primary bottleneck in Channels  
- Increasing Daphne/worker count would improve performance, at the cost of complexity


What Was Tested
~~~~~~~~~~~~~~~

We validated:

- WSGI routing via Gunicorn  
- ASGI routing via Daphne  
- Redis channel layer performance  
- IPC channel layer performance  
- Worker behavior under continuous load  
- Port cleanup  
- Differences between fixed RPS vs auto-throttle  

This ensures that the comparison across setups is fair, isolated, and useful.
