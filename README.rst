Gallagher REST API Client
==========================

A Python client library for interacting with Gallagher Command Centre REST API.

This library was built based on the api documentation available at: https://gallaghersecurity.github.io/cc-rest-docs/ref/index.html 

To ensure full compatibility with the Gallagher Command Centre REST API, it is recommended to use the version 9.00 or newer of the Gallagher Command Centre software. This library covers most used endpoints and features of the API, but some advanced or less common functionalities may not be implemented (yet).

If you encounter any issues or have feature requests, please open an issue on the GitHub repository.

Installation
------------

Install using ``uv``:

.. code-block:: bash

   uv pip install gallagher-restapi

Or using ``pip``:

.. code-block:: bash

   pip install gallagher-restapi


Quick Start
-----------

Initialize the Client
~~~~~~~~~~~~~~~~~~~~~

**Local/On-Premise Server:**

.. code-block:: python

   from gallagher_restapi import Client

   client = Client(
       api_key="your-api-key",
       host="localhost",      # Your server hostname/IP
       port=8904,              # Default Gallagher REST API port
       token="integration-license-token"        # Optional integration license
   )
   
   # Initialize connection
   await client.initialize()

**Cloud Gateway Connection:**

.. code-block:: python

   from gallagher_restapi import Client, CloudGateway

   client = Client(
       api_key="your-api-key",
       cloud_gateway=CloudGateway.AU_GATEWAY  # or CloudGateway.US_GATEWAY
   )
   
   await client.initialize()

**Custom httpx Client:**

.. code-block:: python

   import httpx
   from gallagher_restapi import Client

   custom_httpx = httpx.AsyncClient()
   client = Client(api_key="your-api-key", httpx_client=custom_httpx)


Common Method Signature
~~~~~~~~~~~~~~~~~~~~~~~

Most retrieval methods share a common signature with these parameters:

- **id** *(str, optional)*: Fetch a single item by ID. Returns detailed information.
- **name** *(str, optional)*: Filter by name (substring match).
- **description** *(str, optional)*: Filter by description (substring match).
- **division** *(list[str], optional)*: Filter by division IDs.
- **sort** *(SortMethod, optional)*: Sort order for results.
- **top** *(int, optional)*: Maximum number of results to return.
- **response_fields** *(list[str], optional)*: Specify exact fields to include in response.

  - Pass ``['defaults']`` to include default fields plus additional requested fields
  - Common additional fields: ``['division', 'statusFlags', 'commands']``


Usage Examples
--------------

Retrieve Access Zones
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Get all access zones
   zones = await client.get_access_zone()
   
   # Get a specific access zone by ID
   zone = await client.get_access_zone(id="123")
   
   # Filter by name with additional fields
   zones = await client.get_access_zone(
       name="Main",
       response_fields=['defaults', 'division', 'doors', 'statusFlags'],
       top=5
   )


Retrieve Cardholders
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Get cardholders with default fields
   cardholders = await client.get_cardholder(name="John")
   
   # Get cardholder with personal data and access groups
   cardholders = await client.get_cardholder(
       id="456",
       response_fields=['defaults', 'personalDataFields', 'accessGroups', 'cards']
   )
   
   # Filter by personal data fields
   cardholders = await client.get_cardholder(
       pdfs={'EmployeeID': '12345'},
       response_fields=['defaults', 'personalDataFields']
   )
   
   # Iterate through all cardholders in batches
   async for batch in client.yield_cardholders(top=100):
       for cardholder in batch:
           print(f"{cardholder.name}")


Retrieve Doors
~~~~~~~~~~~~~~

.. code-block:: python

   # Get all doors
   doors = await client.get_door()
   
   # Get doors with additional fields
   doors = await client.get_door(
       division=["division-id-1"],
       response_fields=['defaults', 'statusFlags', 'commands'],
       sort="name"
   )



Retrieve Inputs
~~~~~~~~~~~~~~~

.. code-block:: python

   # Get all inputs
   inputs = await client.get_input()
   
   # Get a specific input by ID
   input_item = await client.get_input(id="input-id-123")
   
   # Filter by name, division and request additional fields
   inputs = await client.get_input(
       name="door sensor",
       division=["division-id-1"],
       response_fields=['defaults', 'statusFlags'],
   )


Retrieve Outputs
~~~~~~~~~~~~~~~~

.. code-block:: python

   # Get all outputs
   outputs = await client.get_output()
   
   # Get a specific output by ID
   output_item = await client.get_output(id="output-id-456")
   
   # Filter and request control/command related fields
   outputs = await client.get_output(
       name="door lock",
       response_fields=['defaults', 'commands', 'statusFlags'],
   )

Retrieve Items
~~~~~~~~~~~~~~

For item types without dedicated methods, use ``get_item()``:

.. code-block:: python

   # Get divisions
   divisions = await client.get_item(name="Root", item_types=['Division'])


Override Commands
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from datetime import datetime, timedelta, timezone

   # Get access zone with commands
   zones = await client.get_access_zone(
       id="123",
       response_fields=['defaults', 'commands']
   )
   
   # Execute override command
   if zones[0].commands:
       command = zones[0].commands[0]
       await client.override_access_zone(
           command_href=command.href,
           end_time=datetime.now(timezone.utc) + timedelta(hours=2)
       )


Manage Cardholders
~~~~~~~~~~~~~~~~~~

**Add New Cardholder:**

.. code-block:: python

   from gallagher_restapi.models import FTCardholder, FTItemReference

   # Create a new cardholder
   new_cardholder = FTCardholder(
       first_name="John",
       last_name="Doe",
       description="New employee",
       division=FTItemReference(href="https://server/api/divisions/123")
   )
   cardholder_ref = await client.add_cardholder(new_cardholder)

**Update Existing Cardholder:**

When updating a cardholder, construct an ``FTCardholder`` object with only the fields you want to modify. 
For collections like ``cards``, ``access_groups``, and ``lockers``, use the patch models:

.. code-block:: python

   from gallagher_restapi import models
   from datetime import datetime, timezone

   # Update basic fields
   updated_cardholder = FTCardholder(
       first_name="Jane",
       description="Updated description"
   )
   
   # Update with cards using FTCardholderCardsPatch
   updated_cardholder.cards = models.FTCardholderCardsPatch(
       add=[
           models.FTCardholderCard(
               number="123456",
               type=models.FTLinkItem(href="https://server/api/card_types/1"),
                   active_from=datetime.now(timezone.utc)
               )
           ],
           update=[
               models.FTCardholderCard(
                   href="https://server/api/cardholders/456/cards/789",
                   active_until=datetime(2026, 12, 31, tzinfo=timezone.utc)
               )
           ],
           remove=[
               models.FTCardholderCard(
                   href="https://server/api/cardholders/456/cards/999"
               )
           ]
       )
   
   # Update with access groups using FTCardholderAccessGroupsPatch
   updated_cardholder.access_groups = models.FTCardholderAccessGroupsPatch(
       add=[
           models.FTAccessGroupMembership(
               access_group=models.FTItemReference(href="https://server/api/access_groups/1"),
               active_from=datetime.now(timezone.utc)
               )
           ],
           update=[
               models.FTAccessGroupMembership(
                   href="https://server/api/cardholders/456/access_groups/789",
                   active_until=datetime(2026, 12, 31, tzinfo=timezone.utc)
               )
           ],
           remove=[
               models.FTAccessGroupMembership(
                   href="https://server/api/cardholders/456/access_groups/999"
               )
           ]
       )
   
   
   # Apply the update
   await client.update_cardholder(
       cardholder_href="https://server/api/cardholders/456",
       patched_cardholder=updated_cardholder
   )

**Remove Cardholder:**

.. code-block:: python

   # Remove a cardholder
   await client.remove_cardholder(
       cardholder_href="https://server/api/cardholders/456"
   )


Manage Access Groups
~~~~~~~~~~~~~~~~~~~~

**Add New Access Group:**

.. note::
   Supported on version **9.30** and newer.

.. code-block:: python

   from gallagher_restapi.models import FTAccessGroup, FTItemReference

   # Create a new access group  
   new_access_group = FTAccessGroup(
        name="New Access Group",
        description="This is a new access group",
        division=FTItemReference(href="/api/items/123"),          
    )
   access_group_ref = await client.create_access_group(new_access_group)


Event Monitoring
~~~~~~~~~~~~~~~~

**EventQuery Parameters:**

The ``EventQuery`` class accepts the following filter parameters:

- **event_types** *(list[str], optional)*: List of event type IDs to filter by. Get available event types from ``client.event_types`` dictionary.
- **event_groups** *(list[str], optional)*: List of event group IDs to filter by. Get available event groups from ``client.event_groups`` dictionary.
- **source** *(list[str], optional)*: List of source item IDs (e.g., door IDs, access zone IDs).
- **cardholders** *(list[str], optional)*: List of cardholder IDs to filter events by specific cardholders.
- **related_items** *(list[str], optional)*: List of related item IDs.
- **after** *(datetime, optional)*: Filter events after this timestamp.
- **before** *(datetime, optional)*: Filter events before this timestamp.
- **previous** *(bool, optional)*: Set to ``True`` to get events starting from the newest.
- **top** *(int, optional)*: Maximum number of results to return.

.. code-block:: python

   from gallagher_restapi.models import EventQuery

   # Get available event types first
   await client.get_event_types()
   
   # Find specific event type IDs
   access_granted_id = client.event_types["Door Access Granted"].id
   
   # Get historical events using event type IDs
   events = await client.get_events(
       event_filter=EventQuery(
           event_types=[access_granted_id, '20003'],  # Use event type IDs
           top=100
       )
   )
   
   # Monitor new events in real-time
   async for event_batch in client.yield_new_events(
       event_filter=EventQuery(
           event_types=[access_granted_id],
           source=['door-id-123'],
           cardholders=['cardholder-id-456']
       )
   ):
       for event in event_batch:
           print(f"Event: {event.type} at {event.time}")


Monitor Alarms
~~~~~~~~~~~~~~

.. code-block:: python

   # Get current alarms
   alarms = await client.get_alarms()
   
   # Monitor new alarms
   async for alarm_batch in client.yield_new_alarms():
       for alarm in alarm_batch:
           print(f"New alarm: {alarm.message}")
   
   # Acknowledge alarm
   if alarms[0].commands:
       await client.alarm_action(
           action_href=alarms[0].commands[0].href,
           comment="Investigating issue"
       )


Advanced Features
-----------------

Item Status Monitoring
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Subscribe to item status updates
   item_ids = ["door-id-1", "zone-id-2"]
   updates, next_ref = await client.get_item_status(item_ids=item_ids)
   
   # Poll for new updates
   updates, next_ref = await client.get_item_status(next_link=next_ref.href)


Cardholder Changes Tracking
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Set up change monitoring
   changes_ref = await client.get_cardholder_changes_href(
       filter=['name', 'cards', 'accessGroups'],
       cardholder_fields=['id', 'name', 'cards']
   )
   
   # Get changes
   changes, next_href = await client.get_cardholder_changes(
       changes_href=changes_ref.href
   )


API Reference
-------------

For complete API documentation, refer to:

- `Client Methods <src/gallagher_restapi/client.py>`_
- `Data Models <src/gallagher_restapi/models.py>`_
- `Exceptions <src/gallagher_restapi/exceptions.py>`_


License
-------

MIT License - see LICENSE file for details.
