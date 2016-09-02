Django Channels Load Testing Results
===============

The goal of these tests is to see how channels performs with normal HTTP traffic under heavy load with a control.

In order to control for variances, several measures were taken:

- the same testing tool was used across all tests, `loadtest <https://github.com/alexfernandez/loadtes/>`_.
- all target machines were identical
- all target code variances were separated into appropriate files in the dir of /testproject in this repo
- all target config variances necessary to the different setups were controlled by supervisord so that human error was limited
- inside each test, the same source machine was used
- inside each test, the same test approach was used
- across different test types, the same target machines were used, using the same target code and the same target config



Latency
~~~~~~~~~~~~

All target and sources machines were identical ec2 instances m3.2xlarge running Ubuntu 16.04.



Throughput
~~~~~~~~~~~~

The same source machine was used for all tests: ec2 instance m3.large running Ubuntu 16.04.
All target machines were identical ec2 instances m3.2xlarge running Ubuntu 16.04.
