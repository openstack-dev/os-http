===============================
os-http
===============================

Simple HTTP CLI for OpenStack

A common problem I have in development is needing to make a request against an
authenticated request against an OpenStack API "correctly" (using the catalog,
real authentication, version discovery etc).

os-http is a httpie_ inspired wrapper around basic keystoneauth_ functionality
that can make and display the response to HTTP requests against openstack
services.

* Free software: Apache license
* Source: https://github.com/jamielennox/os-http

.. _httpie: http://httpie.org/
.. _keystoneauth: https://github.com/openstack/keystoneauth

Usage
-----

.. code-block:: bash

    source accrc  # load your cloud authentication
    os-http --os-service-type image \
            --os-api-version 2      \
            --os-interface public   \
            --os-region RegionTwo   \
            get /images
